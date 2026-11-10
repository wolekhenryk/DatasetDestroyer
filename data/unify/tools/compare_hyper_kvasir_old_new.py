"""Compare the unified-table rows of Hyper-Kvasir with the OLD table `merge/merged-labels.csv`, column by column.

    cd data_to_merge
    ../.venv/bin/python -m unify --only hyper-kvasir --out /tmp/hk.csv --no-validate
    ../.venv/bin/python -m unify.tools.compare_hyper_kvasir_old_new --new /tmp/hk.csv [--old ../merge/merged-labels.csv]

Old -> new mapping of the 76 old columns (documented in docs/reviews/reader1-schema-review.md, 1.1.2):
  * 61 columns keep name, definition and value  -> must be IDENTICAL;
  * `source_dataset` is renamed to `source_subset` (same strings);
  * ids / paths change mechanically:   sample_id, parent_image_sample_id, mask_sample_id (`image:<uuid>` -> `image:hyper-kvasir:<uuid>` ...),
    file_path, image_path, segmented_image_path, mask_path (`out/...` -> `hyper-kvasir/...`), label_source, annotation_source (text);
  * redefined:  image_md5 (now filled for every image row), finding_in_image_vocab (video_frame rows only), bboxes_json (items gain `finding`),
    mask_corner_pixel_removed (boolean) -> mask_noise_pixels_removed (Int64, 0 / 1);
  * box edges that equal the image width / height are clipped to the last pixel in the new table (inclusive convention): bbox_xmax / bbox_ymax,
    bboxes_json and mask_json_bbox_max_diff_px may differ ONLY on rows where this clipping applies (checked against the old JSON values).
Exit code 0 = every column behaves as documented, 1 = unexpected difference.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

DATA_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OLD = DATA_ROOT.parent / "merge" / "merged-labels.csv"
DS = "hyper-kvasir"

IDENTICAL = [
    "source_type", "label_level", "row_description", "item_id", "video_id", "frame_index", "timestamp_s", "seg_stem", "file_ext", "file_exists",
    "file_size_bytes", "region", "organ_raw", "category", "category_raw", "finding", "finding_raw", "finding_harmonized", "finding_harmonization",
    "finding_2", "finding_2_harmonized", "finding_2_raw", "category_2", "category_2_raw", "n_labels", "description", "bbps_score", "bbps_range",
    "dir_region", "dir_category", "dir_finding", "label_category_mismatch", "label_finding_mismatch", "label_folder_mismatch", "width", "height",
    "n_frames_total", "fps", "fps_effective", "duration_s", "codec", "frames_suspect", "timestamp_note", "frame_rank", "frames_sampled_in_video",
    "frame_selection", "has_mask", "has_bbox", "n_boxes", "bbox_label", "bbox_xmin", "bbox_ymin", "mask_foreground_pixels",
    "mask_foreground_fraction", "mask_tight_xmin", "mask_tight_ymin", "mask_tight_xmax", "mask_tight_ymax", "mask_in_bbox_fraction",
]
CLIP_DEPENDENT = ["bbox_xmax", "bbox_ymax", "mask_json_bbox_max_diff_px"]       # differ only where a box edge was clipped
PATH_COLS = ["file_path", "image_path", "segmented_image_path", "mask_path"]
ID_COLS = ["sample_id", "parent_image_sample_id", "mask_sample_id"]
NUMERIC = {"frame_index", "timestamp_s", "file_size_bytes", "bbps_score", "width", "height", "n_frames_total", "fps", "fps_effective", "duration_s",
           "frame_rank", "frames_sampled_in_video", "n_boxes", "n_labels", "bbox_xmin", "bbox_ymin", "bbox_xmax", "bbox_ymax", "mask_foreground_pixels",
           "mask_foreground_fraction", "mask_tight_xmin", "mask_tight_ymin", "mask_tight_xmax", "mask_tight_ymax", "mask_in_bbox_fraction",
           "mask_json_bbox_max_diff_px"}
BOOLS = {"file_exists", "label_category_mismatch", "label_finding_mismatch", "label_folder_mismatch", "frames_suspect", "has_mask", "has_bbox"}


def read(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""], encoding="utf-8")


def new_id(s: pd.Series) -> pd.Series:
    return s.str.replace(r"^(image|mask|frame):", lambda m: f"{m.group(1)}:{DS}:", regex=True)


def new_path(s: pd.Series) -> pd.Series:
    return s.str.replace(r"^out/", f"{DS}/", regex=True)


def same(a: pd.Series, b: pd.Series, col: str) -> pd.Series:
    """Cell-wise equality with both-null = equal; numeric columns compare as floats, booleans as lower-case text."""
    if col in NUMERIC:
        x, y = pd.to_numeric(a), pd.to_numeric(b)
        eq = (x - y).abs() <= 1e-9
    else:
        x, y = (a.str.lower(), b.str.lower()) if col in BOOLS else (a, b)
        eq = x == y
    return eq.fillna(False) | (a.isna() & b.isna())


def clip_union(old_json: str, w: int, h: int):
    """Union box (inclusive, clipped to the image) of the old JSON boxes, and whether any edge had to be clipped."""
    items = json.loads(old_json)
    clipped, boxes = False, []
    for b in items:
        x1, y1 = min(b["xmax"], w - 1), min(b["ymax"], h - 1)
        clipped |= (x1, y1) != (b["xmax"], b["ymax"])
        boxes.append((b["xmin"], b["ymin"], max(b["xmin"], x1), max(b["ymin"], y1)))
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)), clipped, items


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--old", type=Path, default=DEFAULT_OLD)
    ap.add_argument("--new", type=Path, required=True, help="output of `python -m unify --only hyper-kvasir`")
    a = ap.parse_args(argv)
    old, new = read(a.old), read(a.new)
    new = new[new["dataset"] == DS].copy()
    print(f"old: {a.old} {old.shape}   new: {a.new} {new.shape} (dataset == {DS})")
    problems: list[str] = []

    # ---- 1:1 row join through the mechanically transformed sample_id
    old["key"] = new_id(old["sample_id"])
    assert old["key"].is_unique and new["sample_id"].is_unique
    only_old, only_new = set(old["key"]) - set(new["sample_id"]), set(new["sample_id"]) - set(old["key"])
    print(f"rows: old {len(old):,}  new {len(new):,}  only in old {len(only_old)}  only in new {len(only_new)}")
    if only_old or only_new:
        problems.append("row sets differ (k = FRAMES_PER_VIDEO of the old table is 20; pass --param FRAMES_PER_VIDEO=<k> to the build)")
    j = old.merge(new, left_on="key", right_on="sample_id", how="inner", suffixes=("_o", "_n"))
    print(f"joined rows: {len(j):,}; by source_type: {j['source_type_o'].value_counts().to_dict()}")
    O = lambda c: j[f"{c}_o"] if f"{c}_o" in j else j[c]         # noqa: E731  (old column)
    N = lambda c: j[f"{c}_n"] if f"{c}_n" in j else j[c]         # noqa: E731  (new column)

    results: list[tuple[str, str, int, str]] = []                 # (old column, new column, n differing, verdict)

    def record(oc, nc, bad, expected_note=""):
        verdict = "IDENTICAL" if bad == 0 else (f"CHANGED as documented: {expected_note}" if expected_note else "UNEXPECTED DIFFERENCE")
        if bad and not expected_note:
            problems.append(f"{oc} -> {nc}: {bad} differing cells")
        results.append((oc, nc, bad, verdict))

    # ---- identical columns
    for col in IDENTICAL:
        record(col, col, int((~same(O(col), N(col), col)).sum()))
    # ---- renamed
    record("source_dataset", "source_subset", int((O("source_dataset") != N("source_subset")).sum()))
    # ---- ids
    results.append(("sample_id", "sample_id", 0, "MECHANICAL: image|mask|frame:<id> -> image|mask|frame:hyper-kvasir:<id> (join key, 1:1)"))
    for col in ["parent_image_sample_id", "mask_sample_id"]:
        record(col, col, int((~same(new_id(O(col)), N(col), col)).sum()), "")
    # ---- paths
    for col in PATH_COLS:
        record(col, col, int((~same(new_path(O(col)), N(col), col)).sum()))
    lab_old = O("label_source").str.replace(r"^out/", f"{DS}/", regex=True).str.replace(r" \+ video-metadata\.csv$", " + unify/data/hyper-kvasir-video-metadata.csv", regex=True)
    record("label_source", "label_source", int((~same(lab_old, N("label_source"), "label_source")).sum()))
    ann_old = O("annotation_source").str.replace("out/", f"{DS}/", regex=False)
    record("annotation_source", "annotation_source", int((~same(ann_old, N("annotation_source"), "annotation_source")).sum()))

    # ---- redefined columns
    old_md5 = O("image_md5")
    has = old_md5.notna()
    record("image_md5", "image_md5", int((old_md5[has] != N("image_md5")[has]).sum()))
    results[-1] = (*results[-1][:3], f"IDENTICAL where the old table has a value ({int(has.sum()):,} rows); the new table fills {int(N('image_md5').notna().sum()):,} rows "
                                      f"(all image rows + their mask rows) instead of {int(has.sum()):,}" if results[-1][2] == 0 else results[-1][3])
    vf = j["source_type_o"] == "video_frame"
    record("finding_in_image_vocab", "finding_in_image_vocab", int((~same(O("finding_in_image_vocab")[vf], N("finding_in_image_vocab")[vf], "finding_in_image_vocab")).sum()))
    n_old_nonvf = int(O("finding_in_image_vocab")[~vf].notna().sum())
    n_new_nonvf = int(N("finding_in_image_vocab")[~vf].notna().sum())
    results[-1] = (*results[-1][:3], results[-1][3] + f"; on video_frame rows only (old table also had True on {n_old_nonvf:,} image/mask rows, new: {n_new_nonvf})")
    if n_new_nonvf:
        problems.append("finding_in_image_vocab is set outside video_frame rows")
    noise = (pd.to_numeric(O("mask_corner_pixel_removed").str.lower().map({"true": 1, "false": 0})) ==
             pd.to_numeric(N("mask_noise_pixels_removed")))
    mrow = O("mask_corner_pixel_removed").notna()
    record("mask_corner_pixel_removed", "mask_noise_pixels_removed", int((~noise[mrow]).sum()))
    results[-1] = (*results[-1][:3], results[-1][3] + f"; boolean -> 0/1 ({int((N('mask_noise_pixels_removed') == '1').sum())} rows with a removed corner pixel)")

    # ---- boxes: new = old clipped to the image + `finding` key; the three clip-dependent columns differ only where clipping applied
    rows_b = j[O("bboxes_json").notna()]
    bad_json = bad_union = n_clip_rows = bad_diff = 0
    for i in rows_b.index:
        w, h = int(N("width")[i]), int(N("height")[i])
        (u, clipped, old_items) = clip_union(O("bboxes_json")[i], w, h)
        n_clip_rows += clipped
        new_items = json.loads(N("bboxes_json")[i])
        want = [{"label": b["label"], "xmin": b["xmin"], "ymin": b["ymin"], "xmax": min(b["xmax"], w - 1), "ymax": min(b["ymax"], h - 1)} for b in old_items]
        got = [{k: v for k, v in b.items() if k != "finding"} for b in new_items]
        if got != want or any(b.get("finding") != "polyps" for b in new_items):
            bad_json += 1
        if (int(N("bbox_xmin")[i]), int(N("bbox_ymin")[i]), int(N("bbox_xmax")[i]), int(N("bbox_ymax")[i])) != u:
            bad_union += 1
        tight = tuple(int(O(c)[i]) for c in ("mask_tight_xmin", "mask_tight_ymin", "mask_tight_xmax", "mask_tight_ymax"))
        if int(N("mask_json_bbox_max_diff_px")[i]) != max(abs(a_ - b_) for a_, b_ in zip(tight, u)):
            bad_diff += 1
    changed = {c: int((~same(O(c), N(c), c)).sum()) for c in CLIP_DEPENDENT[:2]}      # max_diff is compared above against the clipped union
    note = f"only on rows with a box edge equal to W / H (clipped to W-1 / H-1): {n_clip_rows} of {len(rows_b)} box rows"
    results.append(("bboxes_json", "bboxes_json", bad_json, f"items = old items clipped + `finding`: {'OK' if not bad_json else 'MISMATCH'}"))
    results.append(("bbox_xmax,bbox_ymax", "bbox_xmax,bbox_ymax", bad_union, f"= clipped union of the old boxes: {'OK' if not bad_union else 'MISMATCH'}"))
    results.append(("mask_json_bbox_max_diff_px", "mask_json_bbox_max_diff_px", bad_diff, f"= recomputed against the clipped union: {'OK' if not bad_diff else 'MISMATCH'}"))
    for c_, nb in changed.items():
        results.append((c_, c_, nb, f"CHANGED as documented: differs on {nb} cells ({note})" if nb else "IDENTICAL"))
        if nb > n_clip_rows * 2:           # 2 mask/image rows per box image
            problems.append(f"{c_}: {nb} differing cells exceeds the clipped rows")
    if bad_json or bad_union or bad_diff:
        problems.append("box columns do not equal the clipped old boxes")

    # ---- report (every old column must have been looked at)
    print()
    w = max(len(r[0]) for r in results)
    for oc, nc, bad, verdict in results:
        ok = "MISMATCH" not in verdict and "UNEXPECTED" not in verdict
        print(f"{'OK  ' if ok else 'DIFF'}  {oc.ljust(w)}  -> {nc.ljust(w)}  {bad:>6} differing  {verdict}")
    old_cols = set(old.columns) - {"key"}
    seen = {c for r in results for c in re.split(r"[,]", r[0])} | {"bbox_xmax", "bbox_ymax"}
    missing = sorted(old_cols - seen)
    if missing:
        print("old columns not compared:", missing)
        problems.append(f"old columns not compared: {missing}")
    new_only = [c for c in new.columns if c not in old_cols and c not in {"source_subset", "mask_noise_pixels_removed"}]
    filled = {c: int(new[c].notna().sum()) for c in new_only if new[c].notna().any()}
    print(f"\nnew columns (not in the old table) with values: {len(filled)} of {len(new_only)} -> {filled}")
    n_ident = sum(1 for oc, nc, bad, v in results if bad == 0)
    n_doc = sum(1 for oc, nc, bad, v in results if bad and "CHANGED" in v)
    print(f"\n{n_ident} column mappings identical (incl. the mechanical / redefined ones that agree), {n_doc} columns differ as documented, {len(problems)} problem(s)")
    for p in problems:
        print("PROBLEM:", p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
