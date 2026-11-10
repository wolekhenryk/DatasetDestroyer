"""EAD2020 (Endoscopy Artefact Detection challenge 2020, training release): ARTEFACT / image-quality annotations, NO pathology labels.

The folder holds the same 2,531 pictures several times (overlapping sub-folders, byte-identical, some renamed):
  USED      allDetection_training/bbox_images/   2,531 jpg + YOLO txt  (= framesOnly/frames 2,200 + 99Frames 99 + sequence Detection 232) -> image rows
  USED      masks (643 multi-page TIFF, one page per class): framesOnly/segmentation/masks_ead2020 (474, 5 pages, images renamed
            EAD2020_semantic_NNNNN = byte-identical copies of frameOnly frames -> linked by md5), 99Frames/semanticMasks (99, 6 pages),
            Phase-II sequence masks 1445-01 / 1445-02 (70, 6 pages)              -> segmentation_mask rows
  IGNORED   every other copy: framesOnly/frames + gt_bbox, 99Frames/originalImages + bbox, sequence Detection/*, *_bbox, sequence_onlyData_Detection,
            segmentation image copies (kept only as `segmented_image_path`). Their equality with the canonical copy is asserted (md5 / stems).
Boxes:         class_id cx cy w h normalised, convention `one-based-inclusive` (measured against the Phase-II masks, assumed for the rest).
Masks:         page > 127; framesOnly pages use an all-255 last pixel row as an "empty" marker -> zeroed (5-page set only).
Location:      NOT annotated (upper-GI-like, colon-like and bladder frames occur) -> region unknown.
Groups:        sequences exact; 99 independent Phase-II frames one proxy group; framesOnly (no ids) blocks of 100 frame numbers (proxy, still leaks).
Facts and decisions: docs/datasets/ead2020-train.md.
"""
from __future__ import annotations

import re

import numpy as np
from PIL import Image, ImageSequence

from .. import common as c

META = dict(
    dataset="ead2020-train",
    folder="EAD2020_train",
    license="CC BY-NC-SA 4.0",
    procedure="unknown",              # mixed within the dataset; a single frame's procedure is not recorded
    imaging="unknown",
    region="unknown",
    site="unknown",
    location_source="unknown",
    citation="Ali S. et al., An objective comparison of detection and segmentation algorithms for artefacts in clinical endoscopy, Sci Rep 10 (2020)",
    expected={"image": 2531, "segmentation_mask": 643},
)

CANON = "allDetection_training/bbox_images"
FRAMES_DIR = "EAD2020_dataType_framesOnly/frames"
F99_DIR = "EAD2020-Phase-II-Detection_Segmentation-99Frames"
SEQ_DIR = "EAD2020-Phase-II_dataType_sequence"
EXPECTED_CLASSES = ["specularity", "saturation", "artifact", "blur", "contrast", "bubbles", "instrument", "blood"]
PAGES6 = ["instrument", "specularity", "artifact", "bubbles", "saturation", "blood"]    # = class_list_semantic.txt (Instrument, Specularity, Artefact, ...)
BOX_CONVENTION = "one-based-inclusive"
BLOCK = 100
CONF_ORDER = {"low": 0, "medium": 1, "high": 2}
SEQ_FRAME = {"1445-01": r"EDD2020_SA14451(\d{4})", "1445-02": r"EDD2020_M14452(\d{4})", "1445-03": r"1445-03_clipSB_avi_(\d+)",
             "PYL-02": r"Pylseg2_(\d+)", "PYL-N-02": r"Pylseg4_(\d+)"}
MASKED_SEQ = ("1445-01", "1445-02")


def _stems(folder, ext):
    return sorted((p.stem for p in folder.glob(f"*.{ext}")), key=c.natural_key)


def _read_boxes(txt, W, H, names):
    """YOLO txt -> box dicts (inclusive pixels, one-based-inclusive convention) + per-class counts/areas in class-id order."""
    boxes = []
    for line in txt.read_text(encoding="ascii").splitlines():
        if not line.strip():
            continue
        k, cx, cy, w, h = line.split()
        cid = int(k)
        x0, y0, x1, y1 = c.yolo_to_box(float(cx), float(cy), float(w), float(h), W, H, convention=BOX_CONVENTION)
        boxes.append({"label": c.slugify(names[cid]), "finding": None, "xmin": x0, "ymin": y0, "xmax": x1, "ymax": y1, "_cid": cid})
    return boxes


def _mask_pages(path, five_page_sentinel):
    """Binarised pages (list of bool arrays), size, number of sentinel pixels zeroed, names of pages whose last row was a sentinel."""
    with Image.open(path) as im:
        size = im.size
        pages = [np.asarray(fr) > 127 for fr in ImageSequence.Iterator(im)]
    zeroed, sentinel = 0, []
    for i, p in enumerate(pages):
        if p[-1].all():
            if five_page_sentinel:
                zeroed += int(p[-1].sum())
                p[-1] = False
                sentinel.append(i)
            else:
                raise ValueError(f"{path.name}: page {i} has an all-255 last row in a set without sentinel rows (re-check the mask rule)")
    return pages, size, zeroed, sentinel


def build(ctx):
    root = ctx.root
    canon = root / CANON
    names = [ln.strip() for ln in (root / "class_list.txt").read_text(encoding="utf-8").splitlines() if ln.strip()]
    if names != EXPECTED_CLASSES:
        raise ValueError(f"class_list.txt changed: {names}")
    sem = [ln.strip().lower().replace("artefact", "artifact") for ln in (root / F99_DIR / "class_list_semantic.txt").read_text(encoding="utf-8").splitlines() if ln.strip()]
    if sem != PAGES6:
        raise ValueError(f"class_list_semantic.txt changed: {sem}")
    pages5 = PAGES6[:5]
    id_of = {n: i for i, n in enumerate(names)}
    harm = {n: ctx.label(n).get("finding_harmonized") or ctx.label(n)["finding"] for n in names}

    # ---- canonical images and where each one originates
    stems = _stems(canon, "jpg")
    if set(stems) != set(_stems(canon, "txt")):
        raise ValueError("allDetection_training/bbox_images: jpg and txt stems differ")
    origin: dict[str, str] = {}
    for s in _stems(root / FRAMES_DIR, "jpg"):
        origin[s] = "framesOnly"
    for s in _stems(root / F99_DIR / "originalImages", "jpg"):
        origin[s] = "99Frames"
    seq_of: dict[str, str] = {}
    det = root / SEQ_DIR / "Detection"
    for d in sorted(p for p in det.iterdir() if p.is_dir() and "bbox" not in p.name):
        for s in _stems(d, "jpg"):
            origin[s] = f"sequence-{d.name}"
            seq_of[s] = d.name
    if set(origin) != set(stems) or len(origin) != len(stems):
        raise ValueError(f"the three source sub-folders do not partition allDetection_training/bbox_images "
                         f"({len(set(stems) - set(origin))} canonical stems without origin, {len(set(origin) - set(stems))} origins not canonical)")

    # ---- masks: (mask stem, mask path, image path of the renamed/original copy, pages, canonical stem, set name)
    canon_rel = {s: ctx.rel(canon / f"{s}.jpg") for s in stems}
    md5 = ctx.md5(canon_rel.values())
    stem_of_md5 = {md5[canon_rel[s]]: s for s in stems}
    if len(stem_of_md5) != len(stems):
        raise ValueError("duplicate bytes inside allDetection_training/bbox_images")
    mask_specs = []                                    # dicts
    seg_dir = root / "EAD2020_dataType_framesOnly/segmentation"
    seg_imgs = {p.stem: p for p in (seg_dir / "images_ead2020").glob("*.jpg")}
    seg_md5 = ctx.md5([ctx.rel(p) for p in seg_imgs.values()])
    for m in sorted((seg_dir / "masks_ead2020").glob("*.tif"), key=lambda p: c.natural_key(p.name)):
        img = seg_imgs.get(m.stem)
        if img is None:
            ctx.warn(f"mask {m.name} has no image copy (skipped)")
            continue
        canon_stem = stem_of_md5.get(seg_md5[ctx.rel(img)])
        if canon_stem is None:
            ctx.warn(f"segmentation image {img.name} is not byte-identical to any canonical image (mask skipped)")
            continue
        mask_specs.append(dict(stem=m.stem, path=m, copy=img, canon=canon_stem, pages=pages5, set="framesOnly/segmentation", sentinel=True))
    f99_imgs = {p.stem: p for p in (root / F99_DIR / "originalImages").glob("*.jpg")}
    for m in sorted((root / F99_DIR / "semanticMasks").glob("*_mask.tif"), key=lambda p: c.natural_key(p.name)):
        s = m.stem[:-5]
        mask_specs.append(dict(stem=m.stem, path=m, copy=f99_imgs[s], canon=s, pages=PAGES6, set="99Frames", sentinel=False))
    for seq in MASKED_SEQ:
        d_img = root / SEQ_DIR / "SemanticSegmentation_Sequence" / seq
        for m in sorted((root / SEQ_DIR / "SemanticSegmentation_Sequence" / f"{seq}_masks").glob("*_mask.tif"), key=lambda p: c.natural_key(p.name)):
            s = m.stem[:-5]
            mask_specs.append(dict(stem=m.stem, path=m, copy=d_img / f"{s}.jpg", canon=s, pages=PAGES6, set=f"sequence-{seq}", sentinel=False))
    mask_by_canon = {}
    for sp in mask_specs:
        if sp["canon"] in mask_by_canon:
            raise ValueError(f"two masks for the image {sp['canon']}")
        if sp["canon"] not in origin or not sp["copy"].is_file():
            raise ValueError(f"mask {sp['stem']}: canonical image / image copy missing ({sp['canon']})")
        mask_by_canon[sp["canon"]] = sp

    # ---- build rows
    img_rows, mask_rows = [], []
    for s in stems:
        jpg = canon / f"{s}.jpg"
        txt = canon / f"{s}.txt"
        with Image.open(jpg) as im:
            W, H = im.size
        boxes = _read_boxes(txt, W, H, names)
        if not boxes:
            raise ValueError(f"{s}: empty box file (the dataset has no artefact-free frames)")
        counts, areas = {}, {}
        for cid in sorted({b["_cid"] for b in boxes}):
            n_ = names[cid]
            counts[n_] = sum(1 for b in boxes if b["_cid"] == cid)
            areas[n_] = sum((b["xmax"] - b["xmin"] + 1) * (b["ymax"] - b["ymin"] + 1) for b in boxes if b["_cid"] == cid)
        for b in boxes:
            b["finding"] = harm[names[b["_cid"]]]
        items = [{k: v for k, v in b.items() if k != "_cid"} for b in boxes]
        lab = ctx.multi_label_fields(counts, raw={n_: n_ for n_ in counts}, areas=areas)
        lab["label_confidence"] = min((ctx.label(n_).get("label_confidence", "high") for n_ in counts), key=CONF_ORDER.get)
        org = origin[s]
        seq = seq_of.get(s)
        num = int(s.rsplit("_", 1)[1][-5:]) if org == "framesOnly" else None
        extra = {"bbox_convention": BOX_CONVENTION,
                 "bbox_convention_verified": "phase2-masks" if (org == "99Frames" or seq in MASKED_SEQ) else "assumed",
                 "native_class_ids": {n_: id_of[n_] for n_ in counts}}
        row = dict(
            item_id=s, source_subset=org, file_path=canon_rel[s], label_source=ctx.rel(txt), label_level="image",
            annotation_types="bbox", annotation_format="yolo-txt", annotation_path=ctx.rel(txt),
            width=W, height=H,
            row_description=(f"EAD2020 artefact-annotated endoscopic frame {s} ({W}x{H}, origin {org}) with {len(boxes)} artefact boxes: "
                             + ", ".join(f"{n_} {k}" for k, n_ in counts.items()) + "; no pathology label"),
            annotation_source=ctx.rel(txt),
        )
        if seq:
            fm = re.fullmatch(SEQ_FRAME[seq], s) or re.fullmatch(r".*?" + SEQ_FRAME[seq], s)
            if not fm:
                raise ValueError(f"{s}: cannot read the frame number of sequence {seq}")
            row.update(video_id=seq, frame_index=int(fm.group(1)), group_id=f"{META['dataset']}:{seq}", group_kind="sequence", group_quality="exact")
        elif org == "99Frames":
            row.update(group_id=f"{META['dataset']}:99frames", group_kind="block-proxy", group_quality="proxy")
        else:
            row.update(group_id=f"{META['dataset']}:frames-b{BLOCK}-{(num - 1) // BLOCK + 1:02d}", group_kind="block-proxy", group_quality="proxy")
        row.update(lab)
        row.update(c.box_columns(items, "annotator"))
        grp = {k: row[k] for k in ("group_id", "group_kind", "group_quality") if k in row}
        vid = {k: row[k] for k in ("video_id", "frame_index") if k in row}

        sp = mask_by_canon.get(s)
        if sp:
            pages, (mw, mh), zeroed, sentinel = _mask_pages(sp["path"], sp["sentinel"])
            if (mw, mh) != (W, H):
                raise ValueError(f"{sp['stem']}: mask size {(mw, mh)} != image size {(W, H)}")
            if len(pages) != len(sp["pages"]):
                raise ValueError(f"{sp['stem']}: {len(pages)} pages, expected {len(sp['pages'])}")
            union = np.logical_or.reduce(pages)
            stats = c.mask_columns(union, boxes=None, noise_removed=zeroed)
            page_px, page_tight, inside_px, fg_px, diffs = {}, {}, 0, 0, []
            for name, pg in zip(sp["pages"], pages):
                if not pg.any():
                    continue
                ys, xs = np.nonzero(pg)
                tight = (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))
                page_px[name], page_tight[name] = int(pg.sum()), list(tight)
                fg_px += int(pg.sum())
                same = [(b["xmin"], b["ymin"], b["xmax"], b["ymax"]) for b in boxes if names[b["_cid"]] == name]
                if same:
                    box_mask = np.zeros_like(pg)
                    for x0, y0, x1, y1 in same:
                        box_mask[y0:y1 + 1, x0:x1 + 1] = True
                    inside_px += int((pg & box_mask).sum())
                    diffs.append(max(abs(a - b) for a, b in zip(tight, c.union_box(same))))
            if fg_px:
                stats["mask_in_bbox_fraction"] = round(inside_px / fg_px, 6)         # page k vs boxes of the SAME class
            if diffs:
                stats["mask_json_bbox_max_diff_px"] = max(diffs)                       # tight page box vs union of the same-class boxes
            mask_id = c.make_sample_id("segmentation_mask", META["dataset"], sp["stem"])
            mask_fmt = dict(mask_format="tif-multipage-class-pages", annotation_source=ctx.rel(sp["path"]),
                            mask_encoding=("tif-page>127; pages " + ",".join(sp["pages"]) + ("; all-255 last row zeroed (empty-page marker)" if sp["sentinel"] else "")))
            row.update(annotation_types="bbox|mask", annotation_format="yolo-txt|mask-multipage-tif", has_mask=True, mask_path=ctx.rel(sp["path"]),
                       mask_sample_id=mask_id, seg_stem=sp["stem"], segmented_image_path=ctx.rel(sp["copy"]), **stats)
            row.update({k: v for k, v in mask_fmt.items() if k != "annotation_source"}, annotation_source=f"{ctx.rel(txt)}|{ctx.rel(sp['path'])}")
            extra_m = {"mask_set": sp["set"], "mask_pages": sp["pages"], "mask_page_px": page_px, "mask_page_tight": page_tight,
                       "canonical_image_stem": s}
            if sentinel:
                extra_m["mask_sentinel_pages"] = [sp["pages"][i] for i in sentinel]
            # mask row: classes = non-empty pages (largest foreground wins), NOT the box classes of the image
            if page_px:
                pcounts = {n_: 1 for n_ in sp["pages"] if n_ in page_px}
                pcounts = {n_: 1 for n_ in sorted(pcounts, key=id_of.get)}
                mlab = ctx.multi_label_fields(pcounts, raw={n_: n_ for n_ in pcounts}, areas={n_: float(v) for n_, v in page_px.items()})
                mlab["label_confidence"] = min((ctx.label(n_).get("label_confidence", "high") for n_ in pcounts), key=CONF_ORDER.get)
                mlab["class_counts_json"] = None                       # pixels, not boxes
            else:
                mlab = dict(lab)                                      # no foreground in any page: inherit the image's classes
                mlab["class_counts_json"] = None
                extra_m["mask_empty"] = True
                ctx.warn(f"mask {sp['stem']} has no foreground in any page (labels inherited from the image boxes)")
            mrow = dict(
                item_id=sp["stem"], source_subset=org, file_path=ctx.rel(sp["path"]), label_source=ctx.rel(sp["path"]), label_level="mask",
                annotation_types="mask", annotation_format="mask-multipage-tif",
                row_description=(f"EAD2020 multi-class artefact mask {sp['stem']} ({mw}x{mh}, {len(sp['pages'])} class pages, origin {org}); "
                                 f"non-empty pages: {', '.join(page_px) or 'none'}"),
                width=mw, height=mh, image_path=canon_rel[s], segmented_image_path=ctx.rel(sp["copy"]), mask_path=ctx.rel(sp["path"]),
                parent_image_sample_id=c.make_sample_id("image", META["dataset"], s), seg_stem=sp["stem"],
                has_mask=True, extra_json=c.compact_json(extra_m), **grp, **vid, **stats, **mask_fmt,
            )
            mrow.update(mlab)
            mask_rows.append(ctx.row("segmentation_mask", **mrow))
        row["extra_json"] = c.compact_json(extra)
        img_rows.append(ctx.row("image", **row))
    return img_rows + mask_rows
