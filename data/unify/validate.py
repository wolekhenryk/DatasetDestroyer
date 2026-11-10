"""Generic validation of the unified table. Runs after every build; the notebook prints the PASS/FAIL table.

Dataset-specific expectations are NOT hard-coded here: each adapter declares them in META["expected"]
({source_type: row count}) so the build fails loudly when a dataset changes and the number must be updated consciously.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from . import schema as S

# exactly the strings pandas.read_csv turns into NaN by default (case-sensitive: the legal slug `none` is fine)
NA_LIKE = {"#N/A", "#N/A N/A", "#NA", "-1.#IND", "-1.#QNAN", "-NaN", "-nan", "1.#IND", "1.#QNAN", "<NA>", "N/A", "NA", "NULL", "NaN", "None", "n/a", "nan", "null"}
ID_PATTERN = {
    "image": r"^image:[^:]+:.+$",
    "segmentation_mask": r"^mask:[^:]+:.+$",
    "video_frame": r"^frame:[^:]+:.+:\d{6,}$",
}
LABEL_LEVEL = {"image": "image", "video_frame": "clip", "segmentation_mask": "mask"}


class _Checks:
    def __init__(self):
        self.rows: list[tuple[str, bool, str]] = []

    def __call__(self, name: str, cond, df: pd.DataFrame | None = None, detail: str = ""):
        """cond: bool, or a boolean Series that must be all True (offending sample_ids are listed on failure)."""
        if isinstance(cond, pd.Series):
            bad = ~cond.fillna(False).astype(bool)
            ok = not bool(bad.any())
            if not ok and df is not None:
                ids = df.loc[bad[bad].index, "sample_id"].head(5).tolist()
                detail = f"{int(bad.sum())} offending rows, e.g. {ids}. {detail}"
        else:
            ok = bool(cond)
        self.rows.append((name, ok, detail if not ok else ""))

    def report(self) -> str:
        w = max(len(n) for n, _, _ in self.rows)
        lines = [f"{'PASS' if ok else 'FAIL'}  {n.ljust(w)}  {d}".rstrip() for n, ok, d in self.rows]
        n_fail = sum(not ok for _, ok, _ in self.rows)
        lines.append(f"\n{len(self.rows) - n_fail}/{len(self.rows)} checks passed" + ("" if not n_fail else f", {n_fail} FAILED"))
        return "\n".join(lines)


def validate(df: pd.DataFrame, data_root: Path, adapters: dict, only: list[str] | None = None, md5_checked: bool = True,
             show: bool = True, check_files: bool = True, params: dict | None = None) -> _Checks:
    chk = _Checks()
    data_root = Path(data_root)
    ran = sorted(df["dataset"].unique())

    # ---- structure
    chk("columns equal SCHEMA_SPEC (names and order)", list(df.columns) == S.COLUMNS)
    chk("dtypes equal SCHEMA_SPEC", all(str(df[c].dtype) == S.DTYPES[c] for c in S.COLUMNS))
    chk("sample_id never null", df["sample_id"].notna())
    chk("sample_id unique", not df["sample_id"].duplicated().any(), detail=str(df.loc[df["sample_id"].duplicated(), "sample_id"].head(3).tolist()))
    chk("source_type in allowed set", df["source_type"].isin(S.SOURCE_TYPES), df)
    chk("dataset is a registered adapter", df["dataset"].isin(adapters.keys()), df)
    chk("label_level matches source_type", df["label_level"] == df["source_type"].map(LABEL_LEVEL), df)
    for st, pat in ID_PATTERN.items():
        sub = df[df["source_type"] == st]
        chk(f"sample_id pattern for {st}", sub["sample_id"].str.match(pat).all() if len(sub) else True)
    fr = df[df["source_type"] == "video_frame"]
    chk("(dataset, video_id, frame_index) unique for video frames", not fr.duplicated(["dataset", "video_id", "frame_index"]).any())
    chk("frame_index within [0, n_frames_total-1]", ((fr["frame_index"] >= 0) & (fr["frame_index"] < fr["n_frames_total"])).all() if len(fr) else True)
    chk("sample_id of frames = frame:<dataset>:<video_id>:<frame_index:06d>",
        (fr["sample_id"] == "frame:" + fr["dataset"] + ":" + fr["video_id"] + ":" + fr["frame_index"].astype("string").str.zfill(6)).all() if len(fr) else True)
    for col in S.VIDEO_ONLY:
        chk(f"{col} empty outside video_frame", df.loc[df["source_type"] != "video_frame", col].isna().all())

    # ---- controlled vocabularies
    for col, allowed in [("region", S.REGIONS), ("category", S.CATEGORIES), ("procedure", S.PROCEDURES), ("imaging", S.IMAGING),
                         ("location_source", S.LOCATION_SOURCES), ("group_kind", S.GROUP_KINDS), ("group_quality", S.GROUP_QUALITIES),
                         ("label_confidence", S.LABEL_CONFIDENCE), ("finding_harmonization", S.FINDING_HARMONIZATION)]:
        chk(f"{col} in controlled vocabulary", df[col].isin(allowed), df, detail=f"allowed {allowed}")
    chk("bbox_source in vocabulary where set", df["bbox_source"].dropna().isin(S.BBOX_SOURCES).all())
    toks = df["annotation_types"].dropna().str.split("|").explode()
    chk("annotation_types tokens in vocabulary", toks.isin(S.ANNOTATION_TYPES).all(), detail=str(sorted(set(toks) - set(S.ANNOTATION_TYPES))))
    flags = df["qa_flags"].dropna().str.split("|").explode()
    unknown_flags = sorted(set(flags) - set(S.QA_FLAGS))
    chk("qa_flags are documented flags", not unknown_flags, detail=f"undocumented: {unknown_flags} (add to schema.QA_FLAGS)")
    for col in S.REQUIRED_NON_NULL:
        chk(f"{col} never null", df[col].notna(), df)

    # ---- labels
    chk("findings_all contains finding_harmonized", df.apply(lambda r: r["finding_harmonized"] in r["findings_all"].split("|"), axis=1) if False else
        pd.Series([a in b.split("|") for a, b in zip(df["finding_harmonized"], df["findings_all"])], index=df.index), df)
    chk("n_labels >= 1", df["n_labels"] >= 1, df)
    chk("is_negative: True <=> normal/background, False <=> pathological-findings, null otherwise",
        (df["is_negative"].fillna(False) == df["category"].isin(S.NEGATIVE_CATEGORIES)) &
        (df["is_negative"].notna() == df["category"].isin(S.NEGATIVE_CATEGORIES + ["pathological-findings"])), df)
    chk("negative rows carry no box", ~(df["is_negative"].fillna(False) & (df["n_boxes"].fillna(0) > 0)), df)
    chk("finding_in_image_vocab set on video_frame rows only", df["finding_in_image_vocab"].notna() == (df["source_type"] == "video_frame"), df)
    chk("region_derived in vocabulary where set", df["region_derived"].dropna().isin(S.REGION_DERIVED).all())
    chk("finding_2_harmonized only with finding_2", df["finding_2_harmonized"].isna() | df["finding_2"].notna(), df)
    chk("class_counts_json parses and sums to n_boxes where present",
        pd.Series([True if pd.isna(j) else sum(json.loads(j).values()) == n for j, n in zip(df["class_counts_json"], df["n_boxes"])], index=df.index), df)

    # ---- grouping
    has_g = df["group_id"].notna()
    chk("group_id <=> group_kind != none", has_g == (df["group_kind"] != "none"), df)
    chk("group_id <=> group_quality != none", has_g == (df["group_quality"] != "none"), df)
    chk("group_id starts with '<dataset>:'", (~has_g) | pd.Series([g.startswith(d + ":") if isinstance(g, str) else True for g, d in zip(df["group_id"], df["dataset"])], index=df.index), df)

    # ---- paths and files
    pathcols = ["file_path", "image_path", "segmented_image_path", "mask_path", "annotation_path"]
    for col in pathcols:
        v = df[col].dropna()
        chk(f"{col} is a relative POSIX path", (~v.str.startswith("/") & ~v.str.contains(r"\\", regex=True) & ~v.str.contains(r"(?:^|/)\.\.(?:/|$)", regex=True)).all())
    chk("file_exists is True everywhere", df["file_exists"], df)
    chk("file_ext matches file_path", df["file_path"].str.rsplit(".", n=1).str[-1].str.lower() == df["file_ext"], df)
    if check_files:
        for col in pathcols:
            uniq = df[col].dropna().unique()
            missing = [p for p in uniq if not (data_root / p).is_file()]
            chk(f"every unique {col} exists on disk ({len(uniq):,})", not missing, detail=str(missing[:3]))
    text_cols = [c for c in S.COLUMNS if S.DTYPES[c] == "string"]
    chk("no absolute home paths / user names in any text column",
        not any(df[c].str.contains(r"/Users/|/home/|krushipatel|mfathan", regex=True, na=False).any() for c in text_cols))
    chk("no CR/LF inside string cells", not any(df[c].str.contains(r"[\r\n]", regex=True, na=False).any() for c in text_cols))
    chk("no NA-like strings in text columns", not any(df[c].dropna().isin(NA_LIKE).any() for c in text_cols))
    chk("no leading/trailing whitespace in text columns", not any((df[c].dropna() != df[c].dropna().str.strip()).any() for c in text_cols))

    # ---- boxes
    b = df[df["n_boxes"].notna()]
    chk("has_bbox <=> n_boxes > 0", b["has_bbox"] == (b["n_boxes"] > 0), b)
    chk("has_bbox rows have bboxes_json and union box", df.loc[df["has_bbox"], ["bboxes_json", "bbox_xmin", "bbox_ymin", "bbox_xmax", "bbox_ymax", "bbox_source"]].notna().all(axis=1), df)
    chk("rows without bbox have no box columns", df.loc[~df["has_bbox"], ["bboxes_json", "bbox_xmin", "bbox_label"]].isna().all(axis=1), df)
    bad = []
    for sid, j, n, x0, y0, x1, y1, w, h in df.loc[df["has_bbox"], ["sample_id", "bboxes_json", "n_boxes", "bbox_xmin", "bbox_ymin", "bbox_xmax", "bbox_ymax", "width", "height"]].itertuples(index=False):
        items = json.loads(j)
        ok = (len(items) == n and min(i["xmin"] for i in items) == x0 and min(i["ymin"] for i in items) == y0
              and max(i["xmax"] for i in items) == x1 and max(i["ymax"] for i in items) == y1
              and all(0 <= i["xmin"] <= i["xmax"] < w and 0 <= i["ymin"] <= i["ymax"] < h for i in items))
        if not ok:
            bad.append(sid)
    chk("bboxes_json parses, matches n_boxes + union box, boxes inside the image (inclusive)", not bad, detail=str(bad[:3]))

    # ---- masks and links
    m = df[df["has_mask"]]
    chk("has_mask rows have mask statistics", m["mask_foreground_pixels"].notna() & m["mask_foreground_fraction"].between(0, 1), m)
    chk("mask tight box inside the image", ((m["mask_tight_xmax"] < m["width"]) & (m["mask_tight_ymax"] < m["height"]) &
                                            (m["mask_tight_xmin"] <= m["mask_tight_xmax"])).where(m["mask_tight_xmin"].notna(), True), m)
    masks = df[df["source_type"] == "segmentation_mask"]
    imgs = df[df["source_type"] == "image"].set_index("sample_id")
    chk("every mask row has a parent image row", masks["parent_image_sample_id"].isin(imgs.index), masks)
    chk("one mask row per parent image (1:1)", not masks["parent_image_sample_id"].duplicated().any())
    back = imgs["mask_sample_id"].dropna()
    chk("image.mask_sample_id <-> mask.parent_image_sample_id agree",
        bool(back.isin(masks["sample_id"]).all()) and set(back.index) == set(masks["parent_image_sample_id"]))
    par = masks.join(imgs[["category", "finding_harmonized", "region", "width", "height"]], on="parent_image_sample_id", rsuffix="_img")
    chk("mask rows inherit region and category of the parent image",
        (par["region"] == par["region_img"]) & (par["category"] == par["category_img"]), par)
    same = par["dataset"] != "ead2020-train"   # EAD2020 mask rows take their classes from the non-empty mask pages, not from the boxes
    chk("mask rows inherit the finding of the parent image (except multi-page class masks)",
        (par["finding_harmonized"] == par["finding_harmonized_img"]) | ~same, par)
    chk("mask size equals parent image size", (par["width"] == par["width_img"]) & (par["height"] == par["height_img"]), par)

    # ---- duplicates
    if md5_checked:
        d = df[df["dup_group_id"].notna()]
        chk("dup_group_id only on image rows", (d["source_type"] == "image").all())
        chk("dup groups share one md5 and have >= 2 members", (d.groupby("dup_group_id")["image_md5"].nunique() == 1).all() and (d.groupby("dup_group_id").size() >= 2).all())
        chk("every image row has an md5", df.loc[df["source_type"] == "image", "image_md5"].notna().all())

    # ---- per-dataset expected counts (declared by the adapter)
    for name in ran:
        exp = adapters[name].META["expected"]
        exp = exp(params or {}) if callable(exp) else exp   # META["expected"] may be a function of the build parameters
        got = df.loc[df["dataset"] == name, "source_type"].value_counts().to_dict()
        for st in S.SOURCE_TYPES:
            if (only is None or name in only) and exp.get(st, 0) != got.get(st, 0):
                chk(f"{name}: expected {st} rows", False, detail=f"expected {exp.get(st, 0)}, got {got.get(st, 0)} - update META['expected'] only if the change is understood")
        else:
            chk(f"{name}: row counts equal META['expected']", all(exp.get(st, 0) == got.get(st, 0) for st in S.SOURCE_TYPES) if (only is None or name in only) else True)

    text = chk.report()
    if show:
        print(text)
    failed = [n for n, ok, _ in chk.rows if not ok]
    if failed:
        raise AssertionError(f"{len(failed)} validation check(s) failed:\n" + text)
    return chk


def validate_roundtrip(df: pd.DataFrame, path: Path) -> None:
    """The written CSV re-read with the schema dtypes must equal the in-memory table; LF only; one header line."""
    from .build import read_csv  # noqa: PLC0415

    raw = Path(path).read_bytes()
    assert b"\r" not in raw, "CR found in the CSV"
    assert not raw.startswith(b"\xef\xbb\xbf"), "BOM in the CSV"
    back = read_csv(path)
    pd.testing.assert_frame_equal(back, df.reset_index(drop=True), check_dtype=True)
    print(f"round trip OK: {len(back):,} rows x {len(back.columns)} columns, LF only, no BOM")
