"""CVC-ClinicDB: 612 colonoscopy frames (384x288) of 29 sequences with a polyp ground-truth mask each.

Rows: one `image` row per PNG/Original frame + one linked `segmentation_mask` row per PNG/Ground Truth mask (612 + 612).
Only PNG/ is used: TIF/ holds pixel-identical copies (checked in docs/reports/CVC-ClinicDB.md) that Pillow cannot even open, and
metadata.csv writes its TIF paths as `TIFF/...` although the folder is `TIF/` - so NO path is taken from metadata.csv, only the
frame_id -> sequence_id relation.
Masks are RGB PNGs, polyp = white, with grey noise in 138 of them -> binarise gray > 127, then drop 8-connected components < 10 px
(24 specks of 1-6 px in total; the smallest real component is 190 px). Boxes are mask-derived (one per remaining component).
"""
from __future__ import annotations

import numpy as np
from PIL import Image

from .. import common as c

META = dict(
    dataset="cvc-clinicdb",
    folder="CVC-ClinicDB",
    license="research and educational use only (Hospital Clinic Barcelona / CVC)",   # from the Copyright tag inside the TIFF files
    procedure="colonoscopy",
    imaging="white-light",
    region="lower-gi-tract",
    site="colon",
    location_source="dataset-constant",
    citation="Bernal J. et al., WM-DOVA maps for accurate polyp highlighting in colonoscopy: validation vs. saliency maps from physicians, "
             "Comput Med Imaging Graph 2015",
    expected={"image": 612, "segmentation_mask": 612},
)

MIN_COMPONENT_PX = 10          # smaller 8-connected mask components are noise (see module docstring)
THRESHOLD = 127                # mask binarisation: gray > 127 (white = polyp, per class_dict.csv)


def _sequence_ids(ctx) -> dict[int, int]:
    """frame_id -> sequence_id from metadata.csv (only these two columns are used)."""
    df = c.read_csv_safe(ctx.root / "metadata.csv")
    out: dict[int, int] = {}
    for r in df.to_dict("records"):
        out[int(r["frame_id"])] = int(r["sequence_id"])
    return out


def build(ctx):
    # the class name behind the white pixels comes from class_dict.csv; the adapter relies on 'polyp' = 255
    cd = c.read_csv_safe(ctx.root / "class_dict.csv")
    classes = {r["class_names"]: (int(r["r"]), int(r["g"]), int(r["b"])) for r in cd.to_dict("records")}
    if classes.get("polyp") != (255, 255, 255) or classes.get("background") != (0, 0, 0):
        raise ValueError(f"class_dict.csv changed: {classes}; the mask polarity assumption (polyp = white) must be re-checked")
    lab = ctx.label("polyp")

    seq_of = _sequence_ids(ctx)
    img_dir, mask_dir = ctx.root / "PNG" / "Original", ctx.root / "PNG" / "Ground Truth"
    tif_img, tif_mask = ctx.root / "TIF" / "Original", ctx.root / "TIF" / "Ground Truth"
    imgs = {int(p.stem): p for p in img_dir.glob("*.png")}
    masks = {int(p.stem): p for p in mask_dir.glob("*.png")}
    for what, only_in, other in (("image", set(imgs) - set(masks), "mask"), ("mask", set(masks) - set(imgs), "image")):
        if only_in:
            ctx.warn(f"{len(only_in)} {what} file(s) have no {other} file (no rows): ids {sorted(only_in)[:5]}")
    no_meta = sorted((set(imgs) & set(masks)) - set(seq_of))
    if no_meta:
        ctx.warn(f"{len(no_meta)} frame(s) are not listed in metadata.csv (no sequence -> no group): ids {no_meta[:5]}")
    unused_meta = sorted(set(seq_of) - set(imgs))
    if unused_meta:
        ctx.warn(f"{len(unused_meta)} metadata.csv row(s) have no image file (no rows): ids {unused_meta[:5]}")

    rows = []
    for fid in sorted(set(imgs) & set(masks)):
        img_p, mask_p = imgs[fid], masks[fid]
        item = str(fid)
        img_id, mask_id = c.make_sample_id("image", META["dataset"], item), c.make_sample_id("segmentation_mask", META["dataset"], item)

        with Image.open(mask_p) as im:
            mode = im.mode
            gray = np.asarray(im.convert("L"))
        grey_px = int(((gray > 0) & (gray < 255)).sum())          # anti-aliasing / noise levels between 0 and 255
        m, removed = c.clean_mask(gray > THRESHOLD, min_component_px=MIN_COMPONENT_PX)
        if not m.any():
            ctx.warn(f"mask of frame {fid} is empty after thresholding; frame skipped (no rows)")
            continue
        stats = c.mask_columns(m, boxes=None, noise_removed=removed)       # derived boxes -> no independent box to compare with
        boxes = c.mask_derived_boxes(m, "polyp", lab["finding_harmonized"], min_area=MIN_COMPONENT_PX)
        box_cols = c.box_columns(boxes, "mask-derived")

        seq = seq_of.get(fid)
        group = {} if seq is None else dict(group_id=f"{META['dataset']}:seq-{seq:02d}", group_kind="sequence", group_quality="exact",
                                            video_id=f"seq-{seq:02d}")
        extra = {"frame_id": fid, "sequence_id": seq, "mask_grey_pixels": grey_px,
                 "tif_image_path": ctx.rel(tif_img / f"{fid}.tif") if (tif_img / f"{fid}.tif").is_file() else None,
                 "tif_mask_path": ctx.rel(tif_mask / f"{fid}.tif") if (tif_mask / f"{fid}.tif").is_file() else None}
        shared = dict(
            source_subset=None,
            label_source=f"{ctx.rel(ctx.root / 'class_dict.csv')};{ctx.rel(mask_p)}",
            annotation_types="mask", annotation_format="mask-png",
            finding_raw="polyp", class_counts_json=c.compact_json({lab["finding_harmonized"]: len(boxes)}),
            extra_json=c.compact_json({k: v for k, v in extra.items() if v is not None}),
            image_path=ctx.rel(img_p), mask_path=ctx.rel(mask_p),
            has_mask=True, mask_format="png-rgb" if mode == "RGB" else f"png-{mode.lower()}",
            mask_encoding=f"gray>{THRESHOLD} white=polyp; 8-connected components < {MIN_COMPONENT_PX} px removed",
            annotation_source="PNG/Ground Truth masks of CVC-ClinicDB (Hospital Clinic Barcelona / CVC); boxes derived from the mask",
            seg_stem=item, **group, **box_cols, **stats, **lab,
        )
        what = (f"frame {fid} of sequence {seq}: polyp ground-truth mask of {stats['mask_foreground_pixels']} px, "
                f"{len(boxes)} component box(es)")
        rows.append(ctx.row("image", item_id=item, file_path=ctx.rel(img_p), label_level="image", mask_sample_id=mask_id,
                            row_description=f"CVC-ClinicDB colonoscopy image, {what}.", **shared))
        rows.append(ctx.row("segmentation_mask", item_id=item, file_path=ctx.rel(mask_p), label_level="mask", parent_image_sample_id=img_id,
                            row_description=f"CVC-ClinicDB segmentation mask (white = polyp) of {what}.", **shared))
    return rows
