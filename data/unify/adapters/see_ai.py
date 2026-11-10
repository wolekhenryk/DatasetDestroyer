"""SEE-AI (small-bowel capsule endoscopy, PillCam SB3, YOLO boxes): 18,481 stills, 12 lesion classes, empty label file = negative.

Layout used:   SEE_AI_project_all_images/SEE_AI_project_all_images/imageNNNNN.jpg   (18,481 JPEG, 576x576)
               SEE_AI_project_all_txt/SEE_AI_project_all_txt/imageNNNNN.txt         (YOLO `class cx cy w h`, normalised; THE annotation)
               all_annotation.csv   only the class id -> name table (header rows 1-2) and a count cross-check (per-image box counts per class)
Ignored:       detected_samplevideo_short/*.mp4 = predictions of a detector with class + confidence burned into the frames, NOT ground truth.
Row unit:      `image` only (boxes live in bboxes_json; no masks).
Location:      small bowel (PillCam SB3 capsule, dataset concept); segment unknown. location_source `dataset-constant`: there is no README,
               the knowledge comes from the burned-in "PillCam SB3" text and the dataset's purpose, not from a per-image field.
Boxes:         continuous convention (edges are real coordinates, not integer pixels).
Groups:        no patient / exam id -> blocks of 500 consecutive image numbers (the numbering follows the capsule videos: label agreement of
               frames k apart decays to chance at k ~ 500), blocks joined by byte-identical image pairs (union-find). block-proxy / proxy.
Facts and decisions: docs/datasets/see-ai.md.
"""
from __future__ import annotations

import csv
import re

from PIL import Image

from .. import common as c

META = dict(
    dataset="see-ai",
    folder="see-ai",
    license="unknown",                    # no README / LICENSE in the folder
    procedure="capsule-small-bowel",
    imaging="white-light",
    region="small-bowel",
    site="small-bowel",
    location_source="dataset-constant",
    device="PillCam SB3",                 # burned into the bottom-left of every frame
    citation="SEE-AI project dataset (Yokote A. et al., DEN Open 2024 - from memory, not stated in the folder)",
    expected={"image": 18481},
)

BLOCK = 500
EMPTY_KEY = "(empty txt)"
CONF_ORDER = {"low": 0, "medium": 1, "high": 2}
IMG_SUB = "SEE_AI_project_all_images"
TXT_SUB = "SEE_AI_project_all_txt"


def _read_class_table(csv_path):
    """class id -> native name from the two header rows of all_annotation.csv; also the per-image counts and the sum row."""
    rows = list(csv.reader(csv_path.read_text(encoding="utf-8-sig").splitlines()))
    hdr, num = rows[0], rows[1]
    assert hdr[0] == "annotation_class_name" and hdr[1] == "image_number" and hdr[-1] == "annotation_number", hdr
    assert num[0] == "annotation_class_number", num[:2]
    names = hdr[2:-1]
    ids = [int(x) for x in num[2:-1]]
    assert ids == list(range(len(names))), ids
    sum_row = rows[-1]
    assert sum_row[0] == "annotation_sum", sum_row[:2]
    counts = {int(r[1]): [int(x) for x in r[2:-1]] for r in rows[2:-1]}
    return {i: n for i, n in zip(ids, names)}, counts, [int(x) for x in sum_row[2:-1]]


def build(ctx):
    img_dir = ctx.root / IMG_SUB / IMG_SUB
    txt_dir = ctx.root / TXT_SUB / TXT_SUB
    cls_name, csv_counts, csv_sums = _read_class_table(ctx.root / "all_annotation.csv")

    imgs = sorted(img_dir.glob("image*.jpg"), key=lambda p: c.natural_key(p.name))
    txts = {p.stem: p for p in txt_dir.glob("image*.txt")}
    if orphan_img := [p.name for p in imgs if p.stem not in txts]:
        ctx.warn(f"{len(orphan_img)} images without a .txt (skipped): {orphan_img[:5]}")
    if orphan_txt := sorted(set(txts) - {p.stem for p in imgs}):
        ctx.warn(f"{len(orphan_txt)} .txt files without an image (ignored): {orphan_txt[:5]}")
    imgs = [p for p in imgs if p.stem in txts]

    # byte-identical pairs -> merge their blocks (needs the md5 of every image; cached, shared with the runner)
    rels = [ctx.rel(p) for p in imgs]
    md5 = ctx.md5(rels)
    nums = [int(re.fullmatch(r"image(\d{5})", p.stem).group(1)) for p in imgs]
    n_blocks = (max(nums) - 1) // BLOCK + 1
    parent = list(range(n_blocks + 1))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    by_md5: dict[str, list[int]] = {}
    for n, rp in zip(nums, rels):
        by_md5.setdefault(md5[rp], []).append(n)
    n_pairs = 0
    for members in by_md5.values():
        if len(members) > 1:
            n_pairs += 1
            roots = sorted({find((n - 1) // BLOCK + 1) for n in members})
            for r in roots[1:]:
                parent[r] = roots[0]                       # root = lowest block number
    ctx.log(f"   {n_pairs} byte-identical image groups merged into block groups")

    harm = {}
    for name in cls_name.values():
        lab = ctx.label(name)
        harm[name] = lab.get("finding_harmonized") or lab["finding"]
    id_of = {n: i for i, n in cls_name.items()}

    rows, mism, zero_area = [], [], []
    for p, rp, num in zip(imgs, rels, nums):
        with Image.open(p) as im:
            W, H = im.size
            export_batch = 1 if im.info.get("comment") else 2      # batch 1 = frames re-encoded by libavcodec (comment 'Lavc..'), black level 16
        txt = txts[p.stem]
        counts: dict[str, int] = {}
        areas: dict[str, float] = {}
        boxes, cid_seen, has_zero = [], set(), False
        for line in txt.read_text(encoding="ascii").splitlines():
            if not line.strip():
                continue
            k, cx, cy, w, h = line.split()
            cid, cx, cy, w, h = int(k), float(cx), float(cy), float(w), float(h)
            name = cls_name[cid]
            x0, y0, x1, y1 = c.yolo_to_box(cx, cy, w, h, W, H, convention="continuous")
            has_zero |= (w == 0 or h == 0)
            boxes.append({"label": c.slugify(name), "finding": harm[name], "xmin": x0, "ymin": y0, "xmax": x1, "ymax": y1, "_cid": cid})
            cid_seen.add(cid)
        for cid in sorted(cid_seen):                                # class-id order (multi_label_fields tie-break)
            name = cls_name[cid]
            counts[name] = sum(1 for b in boxes if b["_cid"] == cid)
            areas[name] = sum((b["xmax"] - b["xmin"] + 1) * (b["ymax"] - b["ymin"] + 1) for b in boxes if b["_cid"] == cid)
        got = [counts.get(cls_name[i], 0) for i in sorted(cls_name)]
        if csv_counts.get(num) != got:
            mism.append(p.stem)
        if has_zero:
            zero_area.append(p.stem)
        box_items = [{k_: v for k_, v in b.items() if k_ != "_cid"} for b in boxes]

        if boxes:
            lab = ctx.multi_label_fields(counts, raw={n: n for n in counts}, areas=areas)
            lab["label_confidence"] = min((ctx.label(n).get("label_confidence", "high") for n in counts), key=CONF_ORDER.get)
            desc_boxes = ", ".join(f"{n_} {name}" for name, n_ in counts.items())
            desc = f"SEE-AI small-bowel capsule frame {p.stem} (PillCam SB3, {W}x{H}) with {len(boxes)} YOLO boxes: {desc_boxes}"
        else:
            lab = ctx.label(EMPTY_KEY)
            lab["finding_raw"] = EMPTY_KEY
            desc = f"SEE-AI small-bowel capsule frame {p.stem} (PillCam SB3, {W}x{H}) with an empty label file: none of the 12 lesion classes annotated"
        extra = {"export_batch": export_batch, "image_number": num}
        if counts:
            extra["native_class_ids"] = {n: id_of[n] for n in counts}
        if has_zero:
            extra["zero_area_box"] = True
        block = find((num - 1) // BLOCK + 1)
        row = dict(
            item_id=p.stem,
            source_subset=IMG_SUB,
            file_path=rp,
            label_source=ctx.rel(txt),
            label_level="image",
            row_description=desc,
            annotation_types="bbox",                     # class labels are derived from the boxes (no native image-level label)
            annotation_format="yolo-txt",
            annotation_path=ctx.rel(txt),
            width=W, height=H,
            group_id=f"{META['dataset']}:b{BLOCK}-{block:03d}", group_kind="block-proxy", group_quality="proxy",
            extra_json=c.compact_json(extra),
            annotation_source=ctx.rel(txt),
        )
        row.update(lab)
        row.update(c.box_columns(box_items, "annotator"))
        rows.append(ctx.row("image", **row))

    if mism:
        ctx.warn(f"{len(mism)} images whose per-class box counts differ between the .txt and all_annotation.csv: {mism[:5]}")
    real = [sum(csv_counts[n][i] for n in csv_counts) for i in range(len(cls_name))]
    if real != csv_sums:
        ctx.warn(f"all_annotation.csv 'annotation_sum' row is wrong by the class id (e.g. {csv_sums[:4]} vs real {real[:4]}): it summed the class-number row too; not used")
    if zero_area:
        ctx.warn(f"zero-area YOLO box kept as the 1-pixel box yolo_to_box returns: {zero_area}")
    return rows
