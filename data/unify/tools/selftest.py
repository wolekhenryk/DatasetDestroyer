"""End-to-end self-test of the framework on a tiny synthetic dataset (no real data needed, ~2 s).

    cd data_to_merge && ../.venv/bin/python -m unify.tools.selftest

It builds a fake dataset folder in a temp dir (class folders + one mask + a byte-identical duplicate), registers an in-memory
adapter, runs build_all() -> validate() -> write_csv() -> validate_roundtrip() and asserts the generic columns the runner must fill.
It is also the smallest complete example of an adapter that uses labels + masks + groups + duplicates.
"""
from __future__ import annotations

import tempfile
import types
from pathlib import Path

import numpy as np
from PIL import Image

from unify import common as c
from unify import registry
from unify.build import build_all, read_csv, write_csv
from unify.context import Vocab
from unify.validate import validate, validate_roundtrip

VOCAB = """native_key,region,site,category,finding,finding_harmonized,finding_parent,finding_subtype,finding_harmonization,label_confidence,note
Polyp,lower-gi-tract,colon,pathological-findings,polyps,polyps,,,identity,high,
Normal,lower-gi-tract,colon,normal,normal-mucosa,normal-mucosa,,,identity,high,
"""


def make_fake_dataset(root: Path):
    rng = np.random.default_rng(0)
    for cls, n in (("Polyp", 3), ("Normal", 2)):
        (root / "FakeSet" / cls).mkdir(parents=True)
        for i in range(n):
            Image.fromarray(rng.integers(0, 255, (48, 64, 3), dtype=np.uint8)).save(root / "FakeSet" / cls / f"{cls.lower()}_{i}.jpg")
    # byte-identical duplicate of polyp_0 inside the Normal class -> label conflict across classes
    (root / "FakeSet" / "Normal" / "dup_of_polyp_0.jpg").write_bytes((root / "FakeSet" / "Polyp" / "polyp_0.jpg").read_bytes())
    (root / "FakeSet" / "masks").mkdir()
    m = np.zeros((48, 64), np.uint8)
    m[10:20, 5:15] = 255
    m[30:40, 40:60] = 255
    Image.fromarray(m).save(root / "FakeSet" / "masks" / "polyp_1.png")


META = dict(dataset="selftest", folder="FakeSet", license="unknown", procedure="colonoscopy", imaging="white-light",
            region="lower-gi-tract", site="colon", location_source="dataset-constant",
            expected={"image": 6, "segmentation_mask": 1})


def build(ctx):
    rows = []
    for img in sorted(ctx.root.glob("*/*.jpg"), key=lambda p: c.natural_key(p.name)):
        cls = img.parent.name
        row = ctx.row("image", item_id=img.stem, source_subset=cls, file_path=ctx.rel(img), label_source="folder-name", label_level="image",
                      annotation_types="class", annotation_format="folder-name", finding_raw=cls, dir_finding=cls,
                      group_id=f"selftest:{cls}", group_kind="case", group_quality="exact", **ctx.label(cls))
        mask_file = ctx.root / "masks" / f"{img.stem}.png"
        if mask_file.exists():
            m, removed = c.clean_mask(c.load_mask(mask_file), min_component_px=10)
            boxes = c.mask_derived_boxes(m, "polyp", "polyps")
            img_id, mask_id = c.make_sample_id("image", "selftest", img.stem), c.make_sample_id("segmentation_mask", "selftest", img.stem)
            stats = c.mask_columns(m, noise_removed=removed)
            common = dict(mask_path=ctx.rel(mask_file), mask_format="png-gray", mask_encoding="gray>127 white=polyp")
            row.update(annotation_types="class|mask", has_mask=True, mask_sample_id=mask_id, **common, **stats, **c.box_columns(boxes, "mask-derived"))
            rows.append(row)
            rows.append({**row, "source_type": "segmentation_mask", "sample_id": None, "label_level": "mask", "annotation_types": "mask",
                         "file_path": ctx.rel(mask_file), "image_path": row["file_path"], "parent_image_sample_id": img_id, "mask_sample_id": None})
            continue
        rows.append(row)
    return rows


def main():
    tmp = Path(tempfile.mkdtemp(prefix="unify-selftest-"))
    make_fake_dataset(tmp)
    mod = types.ModuleType("selftest_adapter")
    mod.META, mod.build = META, build
    registry.check_adapter(mod)
    orig = registry.load_vocab
    vocab_file = tmp / "selftest.csv"
    vocab_file.write_text(VOCAB, encoding="utf-8")
    registry.load_vocab = lambda meta: Vocab(vocab_file)
    try:
        df, report = build_all(tmp, adapters={"selftest": mod}, log=lambda *_: None)
    finally:
        registry.load_vocab = orig
    validate(df, tmp, {"selftest": mod}, show=False)

    img = df[df.source_type == "image"].set_index("item_id")
    assert len(df) == 7 and df.source_type.value_counts().to_dict() == {"image": 6, "segmentation_mask": 1}
    assert img.loc["polyp_1", "has_mask"] and img.loc["polyp_1", "n_boxes"] == 2 and img.loc["polyp_1", "bbox_source"] == "mask-derived"
    assert (img.loc["polyp_1", ["bbox_xmin", "bbox_ymin", "bbox_xmax", "bbox_ymax"]].astype(int).tolist() == [5, 10, 59, 39])
    assert img.loc["polyp_1", "mask_foreground_pixels"] == 100 + 200 and img.loc["polyp_1", "mask_noise_pixels_removed"] == 0
    # duplicate bytes across classes: same dup group, label conflict flagged on both, mask row never gets a dup group
    a, b = img.loc["polyp_0"], img.loc["dup_of_polyp_0"]
    assert a.dup_group_id == b.dup_group_id and a.dup_group_id.startswith("dup:")
    assert "dup-label-conflict" in a.qa_flags and "dup-label-conflict" in b.qa_flags and pd_isna(img.loc["polyp_2", "qa_flags"])
    assert df[df.source_type == "segmentation_mask"].dup_group_id.isna().all()
    # derived columns
    assert img.loc["normal_0", "is_negative"] and img.loc["polyp_2", "is_negative"] is not None and not img.loc["polyp_2", "is_negative"]
    assert img.loc["polyp_0", "findings_all"] == "polyps" and img.loc["polyp_0", "n_labels"] == 1 and img.loc["polyp_0", "license"] == "unknown"
    assert df.loc[df.source_type == "segmentation_mask", "image_md5"].notna().all()      # inherited from the parent
    assert df.sample_id.is_unique and df.finding_in_image_vocab.isna().all()
    out = tmp / "out.csv"
    write_csv(df, out)
    validate_roundtrip(df, out)
    assert read_csv(out).shape == df.shape
    print("selftest OK:", len(df), "rows x", len(df.columns), "columns")


def pd_isna(x):
    import pandas as pd  # noqa: PLC0415
    return bool(pd.isna(x))


if __name__ == "__main__":
    main()
