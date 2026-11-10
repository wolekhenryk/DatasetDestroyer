"""polypgen-ninja: Dataset Ninja (Supervisely) export of PolypGen - 8,037 colonoscopy frames, 3,121 of them with polyp masks.

Layout used: img/<name>.jpg + ann/<name>.jpg.json (1:1 by name). Each JSON has image-level tags (`institute` C1-C6, `sequence` seq1-seq23,
`positive` / `negative`) and `objects`: one Supervisely `bitmap` per polyp instance = base64(zlib(PNG crop, mode P, values {0,1})) plus
`origin [x, y]` (top-left of the crop in the image). Verified (docs/reports/polypgen-ninja.md): every crop is tight, instances never touch,
each is one connected component -> the per-instance box is the extent of the decoded foreground (inclusive pixels) and the union of the
instances is the semantic mask.

Rows: 8,037 `image` rows + 3,121 `segmentation_mask` rows (one per image with >= 1 bitmap; `file_path` = `mask_path` = the annotation JSON,
`mask_format` = supervisely-bitmap-in-json). Decisions (docs/datasets/polypgen-ninja.md):
* positive tag without any bitmap (641): image row only, class label kept, no geometry listed (`annotation_types` = class, n_boxes empty,
  qa flag annotation-missing);
* negative tag (4,275): category background / finding no-polyp-annotated (derived), judged an ANNOTATED-EMPTY mask: the dataset explicitly
  ships these frames as polyp-free (`annotation_types` = class|mask, `n_boxes` = 0, `has_mask` False, no mask row).
"""
from __future__ import annotations

import base64
import io
import json
import re
import zlib

import numpy as np
from PIL import Image

from .. import common as c

META = dict(
    dataset="polypgen-ninja",
    folder="polypgen-ninja",
    license="unknown",                      # no licence / README shipped with the export
    procedure="colonoscopy",
    imaging="unknown",                      # white light and NBI frames are not distinguished anywhere in the files
    region="lower-gi-tract",
    site="colon",
    location_source="dataset-constant",
    citation="Ali S. et al., A multi-centre polyp detection and segmentation dataset for generalisability assessment, Scientific Data 2023 "
             "(PolypGen); export: Dataset Ninja",
    expected={"image": 8037, "segmentation_mask": 3121},
)

_C1_CASE = re.compile(r"^C1_(\d+)OLCV1_")             # C1_<NNN>OLCV1_100H<k> : NNN looks like a case / polyp id (158 values)
_C4_CASE = re.compile(r"^C4_(\d+)_endocv2021_")       # C4_<k>_endocv2021_positive_<n> : k = constant image size, 31 values
_SEQ_NAME = re.compile(r"^(seq\d+)_(.*)$")
_TRAILING_NUMBER = re.compile(r"_?\d+$")


def _decode_bitmap(b: dict) -> np.ndarray:
    """Supervisely bitmap -> bool array (h, w) of the crop. data = base64(zlib(PNG)), palette PNG with values {0, 1}; 1 = polyp."""
    raw = zlib.decompress(base64.b64decode(b["data"]))
    with Image.open(io.BytesIO(raw)) as im:
        return np.asarray(im) != 0


def _group(name: str, seq: str | None, centre: str | None) -> dict:
    """Strongest grouping id: sequence tag (exact) > C1/C4 case id (proxy: meaning unverified) > centre (coarse)."""
    if seq:
        return dict(group_id=f"{META['dataset']}:{seq}", group_kind="sequence", group_quality="exact", video_id=seq)
    for rx, tag in ((_C1_CASE, "C1"), (_C4_CASE, "C4")):
        m = rx.match(name)
        if m:
            return dict(group_id=f"{META['dataset']}:{tag}-case-{int(m.group(1))}", group_kind="case", group_quality="proxy")
    if centre:
        return dict(group_id=f"{META['dataset']}:centre-{centre}", group_kind="centre", group_quality="coarse")
    return {}


def build(ctx):
    ann_dir, img_dir = ctx.root / "ann", ctx.root / "img"
    ann_files = {p.name[:-len(".json")]: p for p in ann_dir.glob("*.json")}
    img_files = {p.name: p for p in img_dir.glob("*.jpg")}
    only_ann, only_img = sorted(set(ann_files) - set(img_files), key=c.natural_key), sorted(set(img_files) - set(ann_files), key=c.natural_key)
    if only_ann:
        ctx.warn(f"{len(only_ann)} annotation JSON file(s) have no image (no rows): {only_ann[:3]}")
    if only_img:
        ctx.warn(f"{len(only_img)} image(s) have no annotation JSON (no rows): {only_img[:3]}")
    names = sorted(set(ann_files) & set(img_files), key=c.natural_key)
    sizes = dict(zip(names, c.image_sizes([img_files[n] for n in names])))   # header only

    lab_polyp, lab_pos, lab_neg = ctx.label("polyp"), ctx.label("positive"), ctx.label("negative")
    rows, n_size_mismatch, n_bad_tags = [], 0, 0
    for name in names:
        ann_p, img_p = ann_files[name], img_files[name]
        j = json.loads(ann_p.read_text(encoding="utf-8"))
        tags = {t["name"]: t["value"] for t in j["tags"]}
        W, H = sizes[name]
        if (j["size"]["width"], j["size"]["height"]) != (W, H):
            n_size_mismatch += 1
        positive, negative = "positive" in tags, "negative" in tags
        if positive == negative:                       # neither or both: undecidable, never invent a label
            n_bad_tags += 1
            ctx.warn(f"{name}: needs exactly one of the tags positive/negative, has {sorted(tags)} (no rows)")
            continue
        seq, centre = tags.get("sequence"), tags.get("institute")
        stem = name[:-len(".jpg")]
        item = stem
        ann_rel, img_rel = ctx.rel(ann_p), ctx.rel(img_p)
        img_id, mask_id = c.make_sample_id("image", META["dataset"], item), c.make_sample_id("segmentation_mask", META["dataset"], item)

        # ---- decode the instances
        boxes, areas, union = [], [], None
        for o in j["objects"]:
            crop = _decode_bitmap(o["bitmap"])
            ox, oy = o["bitmap"]["origin"]
            h, w = crop.shape
            ys, xs = np.nonzero(crop)
            if len(xs) == 0 or ox < 0 or oy < 0 or ox + w > W or oy + h > H:
                ctx.warn(f"{name}: instance {o['id']} is empty or outside the image (skipped)")
                continue
            if union is None:
                union = np.zeros((H, W), dtype=bool)
            union[oy:oy + h, ox:ox + w] |= crop
            lab_o = ctx.label(o["classTitle"])
            boxes.append({"label": c.slugify(o["classTitle"]), "finding": lab_o["finding_harmonized"],
                          "xmin": int(ox + xs.min()), "ymin": int(oy + ys.min()), "xmax": int(ox + xs.max()), "ymax": int(oy + ys.max())})
            areas.append(int(len(xs)))

        extra = {"orig_name": _SEQ_NAME.sub(r"\2", stem) if seq else stem[len(centre) + 1:] if centre and stem.startswith(centre + "_") else stem,
                 "name_prefix": seq or centre}
        if seq:
            extra["sub_sequence"] = _TRAILING_NUMBER.sub("", _SEQ_NAME.sub(r"\2", stem))
        m1, m4 = _C1_CASE.match(stem), _C4_CASE.match(stem)
        if m1 or m4:
            extra["case_number"] = int((m1 or m4).group(1))
        shared = dict(
            source_subset="sequence" if seq else "single-frame", label_source=ann_rel, annotation_format="supervisely-bitmap-json",
            annotation_path=ann_rel, image_path=img_rel, centre=centre, width=W, height=H,
            **_group(stem, seq, centre),
        )

        if negative:                                     # explicit polyp-free frame; empty ann JSON = annotated-empty mask
            rows.append(ctx.row(
                "image", item_id=item, file_path=img_rel, label_level="image", annotation_types="class|mask", finding_raw="negative",
                class_counts_json="{}", extra_json=c.compact_json({**extra, "negative_basis": "image tag negative"}),
                row_description=f"PolypGen frame ({'sequence ' + seq if seq else 'single frame'}, tag negative): no polyp; the annotation JSON has no mask object.",
                **shared, **c.box_columns([], "mask-derived"), **lab_neg))
            continue

        if not boxes:                                    # positive tag but not a single bitmap (641 frames in the export)
            rows.append(ctx.row(
                "image", item_id=item, file_path=img_rel, label_level="image", annotation_types="class", finding_raw="positive",
                qa_flags="annotation-missing", extra_json=c.compact_json(extra),
                row_description=f"PolypGen frame ({'sequence ' + seq if seq else 'single frame'}, tag positive) WITHOUT any mask object in the export: "
                                "positive per tag, geometry missing.",
                **shared, **lab_pos))
            continue

        # ---- positive with >= 1 instance: image row + mask row
        stats = c.mask_columns(union, boxes=None, noise_removed=0)          # bitmaps are clean; boxes derived -> no independent box for QA
        box_cols = c.box_columns(boxes, "mask-derived")
        ann_cols = dict(
            finding_raw="polyp", class_counts_json=c.compact_json({lab_polyp["finding_harmonized"]: len(boxes)}),
            extra_json=c.compact_json({**extra, "instance_areas_px": areas}),
            mask_path=ann_rel, has_mask=True, mask_format="supervisely-bitmap-in-json",
            mask_encoding="bitmap PNG value==1, crop pasted at origin (x,y), OR over instances",
            annotation_source="Dataset Ninja export of PolypGen (Supervisely bitmap objects in ann/*.json); boxes derived from the instance bitmaps",
            seg_stem=item, **box_cols, **stats)
        what = (f"{len(boxes)} polyp instance(s), {stats['mask_foreground_pixels']} px, "
                f"{'sequence ' + seq if seq else 'single frame'}{', centre ' + centre if centre else ''}")
        rows.append(ctx.row("image", item_id=item, file_path=img_rel, label_level="image", annotation_types="class|mask", mask_sample_id=mask_id,
                            row_description=f"PolypGen frame with {what}.", **ann_cols, **shared, **lab_polyp))
        rows.append(ctx.row("segmentation_mask", item_id=item, file_path=ann_rel, label_level="mask", annotation_types="class|mask",
                            parent_image_sample_id=img_id,
                            row_description=f"PolypGen segmentation mask (Supervisely bitmaps inside the annotation JSON) of a frame with {what}.",
                            **ann_cols, **shared, **lab_polyp))
    if n_size_mismatch:
        ctx.warn(f"{n_size_mismatch} annotation JSON(s) state an image size different from the real JPEG (real size used)")
    return rows
