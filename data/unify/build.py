"""Run the adapters and do the generic post-processing that is identical for every dataset.

    python -m unify                      # all datasets -> merged-labels.csv
    python -m unify --only cvc-clinicdb --out dev.csv --no-validate   # one dataset while developing an adapter
    python -m unify --param FRAMES_PER_VIDEO=10
"""
from __future__ import annotations

import argparse
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

from . import common as c
from . import registry, schema
from .context import Ctx

DATA_ROOT = Path(__file__).resolve().parent.parent          # .../data_to_merge
CACHE_FILE = Path(__file__).resolve().parent / "cache" / "md5-cache.csv"
DEFAULT_PARAMS = {"FRAMES_PER_VIDEO": 20, "FRAME_STRIDE": None}   # Hyper-Kvasir video sampling (same defaults as merge/merge_labels.ipynb)
META_DEFAULT_COLS = ["license", "procedure", "imaging", "region", "site", "location_source", "device"]   # device is optional in META


# --------------------------------------------------------------------------------------
# run adapters
# --------------------------------------------------------------------------------------
def build_all(data_root: Path = DATA_ROOT, only: list[str] | None = None, params: dict | None = None,
              compute_md5: bool = True, log=print, adapters: dict | None = None):
    """Returns (DataFrame in schema order, report dict). The report holds per-dataset rows, seconds, warnings, unused vocabulary rows."""
    data_root = Path(data_root)
    params = {**DEFAULT_PARAMS, **(params or {})}
    adapters = adapters if adapters is not None else registry.discover(only)
    cache = c.Md5Cache(CACHE_FILE, data_root)
    # a folder without adapter is only meaningful when ALL adapters were loaded
    unreg = registry.unregistered_folders(data_root, adapters) if not only else []
    frames, report = [], {"datasets": {}, "warnings": [], "unregistered_folders": unreg, "adapters": adapters, "params": params}
    for f in report["unregistered_folders"]:
        msg = f"folder {f!r} has no adapter - see docs/ADD_A_DATASET.md"
        report["warnings"].append(msg)
        log(f"WARNING {msg}")
    for name, mod in adapters.items():
        t0 = time.time()
        log(f"== {name}")
        ctx = Ctx(data_root=data_root, meta=mod.META, params=params, vocab=registry.load_vocab(mod.META), md5_cache=cache, log=log)
        out = mod.build(ctx)
        df = out if isinstance(out, pd.DataFrame) else pd.DataFrame(out)
        if "dataset" in df.columns and not (df["dataset"] == name).all():
            raise ValueError(f"{name}: adapter wrote a different value into `dataset`")
        df["dataset"] = name
        df = schema.coerce(df)
        counts = df["source_type"].value_counts().to_dict()
        report["datasets"][name] = {
            "rows": len(df), "by_source_type": counts, "seconds": round(time.time() - t0, 1),
            "warnings": ctx.warnings, "vocab_unused": ctx.vocab.unused() if ctx.vocab else [],
        }
        report["warnings"] += ctx.warnings
        log(f"   {len(df):,} rows {counts} in {report['datasets'][name]['seconds']} s")
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    df = postprocess(df, data_root, adapters, cache, compute_md5, log)
    cache.save()
    return df, report


# --------------------------------------------------------------------------------------
# generic post-processing (identical for every dataset)
# --------------------------------------------------------------------------------------
def _iou(a, b) -> float:
    """IoU of two inclusive pixel boxes (xmin, ymin, xmax, ymax)."""
    iw, ih = min(a[2], b[2]) - max(a[0], b[0]) + 1, min(a[3], b[3]) - max(a[1], b[1]) + 1
    inter = max(iw, 0) * max(ih, 0)
    area = lambda r: (r[2] - r[0] + 1) * (r[3] - r[1] + 1)  # noqa: E731
    return inter / (area(a) + area(b) - inter)


def _boxes_disagree(grp: pd.DataFrame, min_iou: float = 0.5) -> bool:
    """Members of a byte-identical group annotate different boxes: box counts differ, or the union boxes overlap with IoU < min_iou.
    Slightly different outlines of the same object (IoU >= 0.5) are annotation noise, not a conflict."""
    n = grp["n_boxes"].fillna(0).astype(int)
    if n.nunique() > 1:
        return True
    if (n == 0).all():
        return False
    boxes = [tuple(int(x) for x in r) for r in grp[["bbox_xmin", "bbox_ymin", "bbox_xmax", "bbox_ymax"]].itertuples(index=False)]
    return any(_iou(boxes[0], bx) < min_iou for bx in boxes[1:])


def _add_flag(df: pd.DataFrame, mask, flag: str) -> None:
    cur = df.loc[mask, "qa_flags"].fillna("")
    df.loc[mask, "qa_flags"] = cur.map(lambda s: "|".join(sorted({*[x for x in s.split("|") if x], flag})))


def postprocess(df: pd.DataFrame, data_root: Path, adapters: dict, cache: c.Md5Cache, compute_md5: bool = True, log=print) -> pd.DataFrame:
    df = df.copy()

    # 1. dataset META defaults (licence, procedure, imaging, region, site, location_source)
    for name, mod in adapters.items():
        idx = df["dataset"] == name
        if not idx.any():
            continue
        for col in META_DEFAULT_COLS:
            if col in mod.META:
                m = idx & df[col].isna()
                df.loc[m, col] = mod.META[col]

    # 2. sample_id
    m = df["sample_id"].isna()
    if m.any():
        sub = df[m]
        ids = [c.make_sample_id(r.source_type, r.dataset, r.item_id, r.video_id, None if pd.isna(r.frame_index) else r.frame_index)
               for r in sub.itertuples()]
        df.loc[m, "sample_id"] = ids

    # 3. file facts: extension, existence, size (one stat per unique path)
    paths = df["file_path"].dropna().unique().tolist()
    def _stat(p):
        try:
            return os.stat(data_root / p).st_size
        except OSError:
            return None
    with ThreadPoolExecutor(8) as ex:
        sizes = dict(zip(paths, ex.map(_stat, paths)))
    df["file_ext"] = df["file_ext"].fillna(df["file_path"].str.rsplit(".", n=1).str[-1].str.lower())
    ex_ = df["file_path"].map(lambda p: sizes.get(p) is not None).astype("boolean")
    df["file_exists"] = df["file_exists"].fillna(ex_)
    df["file_size_bytes"] = df["file_size_bytes"].fillna(df["file_path"].map(lambda p: sizes.get(p)).astype("Int64"))

    # 4. width / height from the file header where the adapter did not know them (never for video frames)
    m = (df["width"].isna() | df["height"].isna()) & (df["source_type"] != "video_frame") & df["file_exists"].astype(bool)
    if m.any():
        todo = df.loc[m, "file_path"].unique().tolist()
        log(f"   reading {len(todo):,} image headers")
        dims = dict(zip(todo, c.image_sizes([data_root / p for p in todo])))
        df.loc[m, "width"] = df.loc[m, "file_path"].map(lambda p: dims[p][0]).astype("Int64")
        df.loc[m, "height"] = df.loc[m, "file_path"].map(lambda p: dims[p][1]).astype("Int64")

    # 5. md5 of every image row (cached); mask rows inherit the md5 of their parent image
    if compute_md5:
        m = (df["source_type"] == "image") & df["image_md5"].isna() & df["file_exists"].astype(bool)
        if m.any():
            todo = df.loc[m, "file_path"].unique().tolist()
            log(f"   md5 of {len(todo):,} images (cached ones are skipped)")
            md5 = cache.get(todo)
            df.loc[m, "image_md5"] = df.loc[m, "file_path"].map(md5)
        by_id = df.loc[df["source_type"] == "image"].set_index("sample_id")["image_md5"]
        m = (df["source_type"] == "segmentation_mask") & df["image_md5"].isna() & df["parent_image_sample_id"].notna()
        df.loc[m, "image_md5"] = df.loc[m, "parent_image_sample_id"].map(by_id)

    # 6. label defaults
    df["finding_harmonized"] = df["finding_harmonized"].fillna(df["finding"])
    m = df["finding_harmonization"].isna()
    df.loc[m, "finding_harmonization"] = (df.loc[m, "finding_harmonized"] != df.loc[m, "finding"]).map({True: "mapped", False: "identity"})
    df["finding_parent"] = df["finding_parent"].fillna(df["finding_harmonized"])
    df["finding_raw"] = df["finding_raw"].fillna(df["finding"])
    df["finding_2_harmonized"] = df["finding_2_harmonized"].fillna(df["finding_2"])
    m = df["findings_all"].isna()
    both = m & df["finding_2_harmonized"].notna() & (df["finding_2_harmonized"] != df["finding_harmonized"])
    df.loc[m, "findings_all"] = df.loc[m, "finding_harmonized"]
    df.loc[both, "findings_all"] = [c.pipe_join([a, b]) for a, b in zip(df.loc[both, "finding_harmonized"], df.loc[both, "finding_2_harmonized"])]
    df["n_labels"] = df["n_labels"].fillna(df["findings_all"].str.count(r"\|") + 1)
    df["label_confidence"] = df["label_confidence"].fillna("high")
    df["is_negative"] = pd.array([True if cat in schema.NEGATIVE_CATEGORIES else False if cat == "pathological-findings" else pd.NA
                                  for cat in df["category"]], dtype="boolean")
    df["has_mask"] = df["has_mask"].fillna(False)
    df["has_bbox"] = df["has_bbox"].fillna(False)

    # 7. finding_in_image_vocab (video_frame rows only): (region, category, finding_harmonized) also occurs among the image rows of the table
    key = df["region"] + "|" + df["category"] + "|" + df["finding_harmonized"]
    inv = key.isin(set(key[df["source_type"] == "image"])).astype("boolean")
    df["finding_in_image_vocab"] = inv.where(df["source_type"] == "video_frame", pd.NA)

    # 8. grouping defaults
    nogroup = df["group_id"].isna()
    df.loc[nogroup, "group_kind"] = df.loc[nogroup, "group_kind"].fillna("none")
    df.loc[nogroup, "group_quality"] = df.loc[nogroup, "group_quality"].fillna("none")

    # 9. exact duplicates over the whole table (image rows, identical bytes) + label conflicts inside a duplicate group
    img = df["source_type"] == "image"
    md5 = df["image_md5"].where(img)
    dup = md5.notna() & md5.duplicated(keep=False)
    df.loc[dup, "dup_group_id"] = "dup:" + md5[dup].str[:12]
    if dup.any():
        d_ = df[dup]
        by = md5[dup]
        label_conflict = d_["findings_all"].groupby(by).transform("nunique") > 1
        box_conflict = pd.Series(False, index=d_.index)
        for _, grp in d_.groupby(by):
            if grp["findings_all"].nunique() == 1 and _boxes_disagree(grp):
                box_conflict.loc[grp.index] = True
        _add_flag(df, label_conflict.reindex(df.index, fill_value=False), "dup-label-conflict")
        _add_flag(df, box_conflict.reindex(df.index, fill_value=False), "dup-box-conflict")

    # 10. row description default
    kind = df["source_type"].map({"image": "Endoscopic image", "video_frame": "Video frame", "segmentation_mask": "Segmentation mask"})
    default_desc = kind + " (" + df["dataset"] + ") — " + df["region"] + " / " + df["category"] + " / " + df["finding_harmonized"]
    df["row_description"] = df["row_description"].fillna(default_desc)

    return schema.coerce(df)


# --------------------------------------------------------------------------------------
# output
# --------------------------------------------------------------------------------------
def write_csv(df: pd.DataFrame, path: Path) -> None:
    """UTF-8, LF, header, no index, empty cell = not applicable. Byte-for-byte reproducible for the same inputs."""
    df.to_csv(path, index=False, lineterminator="\n", encoding="utf-8", na_rep="")


def read_csv(path: Path) -> pd.DataFrame:
    """Read the table back with the schema dtypes (what every consumer should do)."""
    return pd.read_csv(path, dtype={c_: t for c_, t in schema.DTYPES.items()}, keep_default_na=False, na_values=[""], encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m unify")
    ap.add_argument("--only", nargs="*", help="dataset names (adapter META['dataset']); default: all")
    ap.add_argument("--out", type=Path, default=DATA_ROOT / "merged-labels.csv")
    ap.add_argument("--param", action="append", default=[], metavar="KEY=VALUE")
    ap.add_argument("--no-md5", action="store_true", help="skip image md5 / duplicate detection (fast development runs)")
    ap.add_argument("--no-validate", action="store_true")
    a = ap.parse_args(argv)
    params = {}
    for kv in a.param:
        k, v = kv.split("=", 1)
        params[k] = None if v == "None" else int(v) if v.lstrip("-").isdigit() else v
    df, report = build_all(only=a.only, params=params, compute_md5=not a.no_md5)
    if not a.no_validate:
        from .validate import validate  # noqa: PLC0415
        validate(df, DATA_ROOT, report["adapters"], only=a.only, md5_checked=not a.no_md5, params=report["params"])
    write_csv(df, a.out)
    print(f"wrote {len(df):,} rows x {len(df.columns)} columns -> {a.out}")


if __name__ == "__main__":
    main()
