"""ETIS-LaribPolypDB adapter (196 colonoscopy frames with a binary polyp mask each).

Layout: `ETIS-LaribPolypDB/images/<n>.png` (RGB 1225x966) and `ETIS-LaribPolypDB/masks/<n>.png` (mode L, values exactly {0, 255},
white = polyp), n = 1..196. No label file: every image is polyp-positive (min foreground 0.11 %), no negatives, no sequence / patient ids.

Rows: 196 `image` + 196 `segmentation_mask` (one per image, linked both ways). Boxes are NOT shipped: they are derived from the mask
(8-connected components of at least 10 px; `bbox_source = mask-derived`), so `annotation_types` lists only `mask`.
Group: the whole dataset is one group (`dataset` / `coarse`): no sequence info exists, a block proxy would be wrong (docs/datasets/etis-laribpolypdb.md).
Byte-identical image pairs (20/22, 127/131, 172/175) carry different masks -> flagged by the runner (`dup_group_id`, `dup-box-conflict`).
"""
from __future__ import annotations

import numpy as np
from PIL import Image

from .. import common as c

META = dict(
    dataset="etis-laribpolypdb",
    folder="ETIS-LaribPolypDB",
    license="unknown",                    # no licence file shipped
    procedure="colonoscopy",
    imaging="white-light",
    region="lower-gi-tract",
    site="colon",
    location_source="dataset-constant",
    citation="Silva et al., Toward embedded detection of polyps in WCE images for early diagnosis of colorectal cancer, IJCARS 9 (2014)",
    expected={"image": 196, "segmentation_mask": 196},
)

MIN_AREA = 10
NATIVE_CLASS = "polyp"


def build(ctx):
    img_dir, msk_dir = ctx.root / "images", ctx.root / "masks"
    imgs = {p.stem: p for p in img_dir.glob("*.png")}
    msks = {p.stem: p for p in msk_dir.glob("*.png")}
    if set(imgs) - set(msks):
        ctx.warn(f"images without mask (no rows created): {sorted(set(imgs) - set(msks), key=c.natural_key)}")
    if set(msks) - set(imgs):
        ctx.warn(f"masks without image (no rows created): {sorted(set(msks) - set(imgs), key=c.natural_key)}")
    stems = sorted(set(imgs) & set(msks), key=c.natural_key)
    lab = ctx.label(NATIVE_CLASS)
    shared = dict(lab, finding_raw=NATIVE_CLASS, n_labels=1,
                  group_id=f"{META['dataset']}:all", group_kind="dataset", group_quality="coarse")

    image_rows, mask_rows = [], []
    for stem in stems:
        m = c.load_mask(msks[stem], threshold=127)
        with Image.open(msks[stem]) as im:
            raw = np.asarray(im)                                    # exact value check (lossless PNG)
        assert set(np.unique(raw).tolist()) <= {0, 255}, f"{stem}: mask values are not exactly 0/255"
        comps = c.connected_components_boxes(m, min_area=1)
        small = [x for x in comps if x[4] < MIN_AREA]
        assert not small, f"{stem}: {len(small)} component(s) below {MIN_AREA} px (would be dropped)"
        assert comps, f"{stem}: empty mask - ETIS is expected to be polyp-positive everywhere"
        boxes = [{"label": "polyp", "finding": lab["finding_harmonized"], "xmin": x0, "ymin": y0, "xmax": x1, "ymax": y1}
                 for x0, y0, x1, y1, _ in comps]
        stats = c.mask_columns(m, boxes=None, noise_removed=0)       # clean lossless mask: nothing removed, no annotator box for the QA columns
        geometry = {**c.box_columns(boxes, "mask-derived"), **stats,
                    "class_counts_json": c.compact_json({lab["finding_harmonized"]: len(boxes)}),
                    "mask_format": "png-gray", "mask_encoding": "value==255 white=polyp (png mode L, values exactly 0/255)",
                    "annotation_source": f"{ctx.rel(msk_dir)} (boxes derived: 8-connected components of at least {MIN_AREA} px; not shipped)",
                    "extra_json": c.compact_json({"component_px": [x[4] for x in comps]})}
        img_id = c.make_sample_id("image", META["dataset"], stem)
        msk_id = c.make_sample_id("segmentation_mask", META["dataset"], stem)
        pct = 100 * stats["mask_foreground_fraction"]
        common = dict(shared, label_source=f"dataset-constant (every image is polyp-positive); geometry from {ctx.rel(msk_dir)}",
                      annotation_types="mask", annotation_format="mask-png", has_mask=True,
                      image_path=ctx.rel(imgs[stem]), mask_path=ctx.rel(msks[stem]), **geometry)
        image_rows.append(ctx.row(
            "image", **common, item_id=stem, file_path=ctx.rel(imgs[stem]), label_level="image", mask_sample_id=msk_id,
            row_description=f"Colonoscopy still {stem} (ETIS-Larib, white light) with a polyp mask: {len(boxes)} polyp region(s), {pct:.1f}% of the pixels"))
        mask_rows.append(ctx.row(
            "segmentation_mask", **common, item_id=stem, file_path=ctx.rel(msks[stem]), label_level="mask", parent_image_sample_id=img_id,
            width=m.shape[1], height=m.shape[0],
            row_description=f"Binary polyp mask of ETIS-Larib image {stem}: {len(boxes)} polyp region(s), {pct:.1f}% of the pixels (white = polyp)"))
    return image_rows + mask_rows
