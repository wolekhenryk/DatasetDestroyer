"""TEMPLATE adapter - copy to `unify/adapters/<my_dataset>.py` and edit. Files starting with '_' are ignored by the registry.

What this file must do (and nothing more):
  1. META: dataset-wide constants (name, folder, licence, procedure, imaging, region/site, expected row counts).
  2. build(ctx): list the dataset's files, look every native class up in the vocabulary CSV, and return one row per
     image (+ one per mask file / video frame, if the dataset has them) with only the columns the dataset really knows.

What it must NOT do: compute sizes, md5, duplicates, sample_id, findings_all, is_negative, file_exists, column order or dtypes -
build.py does all of that identically for every dataset (see unify/build.py::postprocess). Leave unknown columns out.

The worked example below handles the most common layout - `<folder>/<class name>/<image>.jpg` (class = folder name), exactly like
Kvasir-Capsule. Recipes for other layouts are in the RECIPES comments at the bottom of the file; the full checklist is in
docs/ADD_A_DATASET.md.
"""
from __future__ import annotations

from .. import common as c

META = dict(
    dataset="my-dataset",              # registry name -> column `dataset`; also the vocabulary file unify/vocab/my-dataset.csv
    folder="MyDataset",                # folder name inside data_to_merge/
    license="unknown",                 # copy from the dataset's README / paper; 'unknown' if none is shipped (never leave a guess)
    procedure="colonoscopy",           # colonoscopy | gastroscopy | capsule-small-bowel | capsule-whole-gi | mixed | unknown
    imaging="white-light",             # white-light | nbi | chromoscopy | mixed | unknown
    region="lower-gi-tract",           # lower-gi-tract | upper-gi-tract | small-bowel | unknown   (default; the vocabulary may override per class)
    site="colon",                      # colon, cecum, stomach, small-bowel, unknown, ...        (default; the vocabulary may override)
    location_source="dataset-constant",  # how the region is known: dataset-constant | folder | label-column | class-name | readme | unknown
    device=None,                       # optional: endoscope / capsule model if the dataset states it (e.g. "PillCam SB3")
    citation="Author et al., Journal Year",
    # row counts the adapter must produce. The build FAILS when they differ, so a changed dataset is noticed, not absorbed.
    expected={"image": 0},             # e.g. {"image": 612, "segmentation_mask": 612}
)


def build(ctx):
    rows = []
    for img in sorted(ctx.root.glob("*/*.jpg"), key=lambda p: c.natural_key(p.name)):
        cls = img.parent.name                      # native class = folder name
        lab = ctx.label(cls)                       # <- row of unify/vocab/my-dataset.csv; raises UnmappedClass for a new class
        rows.append(ctx.row(
            "image",
            item_id=img.stem,
            source_subset=None,
            file_path=ctx.rel(img),                # relative to data_to_merge/
            label_source="folder-name",            # or the CSV / annotation file the label came from
            label_level="image",
            annotation_types="class",              # subset of class | clip-class | bbox | mask  that the dataset PROVIDES for this row
            annotation_format="folder-name",
            finding_raw=cls,                       # the original class text
            category_raw=None,
            dir_finding=cls,
            # group_id = the key to split by. Use the strongest id the dataset gives (video > sequence > case > block-proxy):
            group_id=None, group_kind="none", group_quality="none",
            **lab,                                 # region, site, category, finding, finding_harmonized, finding_parent, label_confidence...
                                                   # (to OVERRIDE a vocabulary field merge first: **{**lab, 'finding_harmonization': 'native'}; a duplicate keyword raises)
        ))
    return rows


# ------------------------------------------------------------------------------------------------------------------------------
# RECIPES (copy the lines you need into build())
# ------------------------------------------------------------------------------------------------------------------------------
# Labels in a CSV (read it with c.read_csv_safe: keeps 'NA'/'null' as text, strips BOM/CRLF/blanks):
#     df = c.read_csv_safe(ctx.root / "labels.csv")
#     for r in df.to_dict("records"):  lab = ctx.label(r["Label"]);  file = ctx.root / "imgs" / r["Frame name"]
#     Rows in the CSV without a file / files without a CSV row: do NOT invent rows - ctx.warn("14 images have no CSV row: ...").
#
# One native class that needs several lookup parts (region|category|finding):   ctx.label(f"{organ}|{classification}|{finding}")
#
# YOLO txt boxes (class cx cy w h, normalised):
#     W, H = size;  boxes = []
#     for line in txt.read_text().split():  ... cls, cx, cy, w, h
#         x0, y0, x1, y1 = c.yolo_to_box(cx, cy, w, h, W, H)
#         boxes.append({"label": c.slugify(name), "finding": ctx.label(key)["finding_harmonized"], "xmin": x0, "ymin": y0, "xmax": x1, "ymax": y1})
#     row.update(c.box_columns(boxes, "annotator"))          # empty list -> n_boxes = 0 (annotated negative)
#     multi-class image:  row.update(ctx.multi_label_fields({"erosion": 2, "bleeding": 1}, raw={...}))   # findings_all, class_counts_json, n_labels
#   Empty txt = annotated negative:  category 'background', finding 'no-lesion-annotated' (finding_harmonization='derived').
#
# Pascal-VOC XML boxes: c.voc_to_box(xmin, ymin, xmax, ymax, W, H) assumes HALF-OPEN max edges (verified for PolypsSet). Verify on your
#   data: count boxes with xmax == W (half-open) vs xmax == W-1 (inclusive). Strip the numbers (` 113`) before int().
#
# Standalone mask files (one `segmentation_mask` row per image with a mask, linked both ways):
#     m = c.load_mask(mask_path, threshold=127);  m, removed = c.clean_mask(m, min_component_px=10)   # drop_corner_pixel=True for HK-style JPEG masks
#     stats = c.mask_columns(m, boxes=None, noise_removed=removed)
#     boxes = c.mask_derived_boxes(m, "polyp", "polyps");  image_row.update(c.box_columns(boxes, "mask-derived"))
#     image_row.update(has_mask=True, mask_path=ctx.rel(mask_path), mask_sample_id=mask_id, mask_format="png-gray", mask_encoding="gray>127 white=polyp", **stats)
#     mask_row = ctx.row("segmentation_mask", item_id=stem, file_path=ctx.rel(mask_path), parent_image_sample_id=image_id,
#                        label_level="mask", **same label columns as the image row, **stats)
#   Embedded masks (JSON/XML): still emit the mask row, file_path = the annotation file, mask_format says how to decode it.
#   ids to link rows:  c.make_sample_id("image", META["dataset"], item_id)
#
# Groups for leakage-safe splits (group_id = f"{META['dataset']}:{group}"):
#     exact  = all frames of one video / sequence / case share the id (group_kind video|sequence|case, group_quality exact)
#     proxy  = contiguous blocks of file numbers when frames are numbered chronologically (block-proxy, proxy)
#     none   = nothing is known; leave group_id empty and say so in docs/datasets/<dataset>.md
#   Shipped train/val/test: split_official='train'|'val'|'test'.   Acquisition site: centre='C1'.
#
# Datasets that contain the same image several times (overlapping folders): ingest the canonical copy only and document it.
# Odd extras that have no column: extra_json=c.compact_json({"sub_source": "...", ...}) and document the keys.
