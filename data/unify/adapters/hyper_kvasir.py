"""Hyper-Kvasir adapter (labelled part: 10,662 still images, 374 labelled videos, 1,000 segmented polyp images).

Port of `merge/merge_labels.ipynb` to the unified schema; the old semantics are kept (raw + normalised labels, folder provenance and mismatch
flags, BBPS, fps_effective / timestamp notes of the 9 suspect clips, MD5 link of the segmented images, JPEG corner-noise removal).
Compared cell by cell with the old table by `unify/tools/compare_hyper_kvasir_old_new.py`.

Layout used (all under `hyper-kvasir/`):
  labeled-images/image-labels.csv + <region>/<classification>/<finding>/<uuid>.jpg      -> `image` rows (10,662)
  labeled-videos/video-labels.csv + <tract>/<category>/<finding>/<uuid>.avi             -> `video_frame` rows (374 clips x FRAMES_PER_VIDEO)
  segmented-images/{images,masks}/<cju...>.jpg + bounding-boxes.json                    -> `segmentation_mask` rows (1,000) + mask/box columns on the linked image rows
Video technical metadata (fps, frames, size, codec; ffprobe) comes from `unify/data/hyper-kvasir-video-metadata.csv` (snapshot of the project-root
`video-metadata.csv`). Not ingested: `unlabeled-images` (not part of this folder).
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

from .. import common as c

META = dict(
    dataset="hyper-kvasir",
    folder="hyper-kvasir",
    license="CC BY 4.0",
    procedure="mixed",              # colonoscopy (Lower GI) + gastroscopy (Upper GI); the vocabulary sets it per class
    imaging="white-light",          # dataset-level assumption (not verified per image); the vocabulary sets chromoscopy for dyed-* classes
    region="unknown",               # the vocabulary sets region / site for every class
    site="unknown",
    location_source="label-column",
    citation="Borgli et al., HyperKvasir, a comprehensive multi-class image and video dataset for gastrointestinal endoscopy, Scientific Data 7, 283 (2020)",
    # image / mask rows are fixed; frame rows follow the sampling parameters (see _expected_frames)
    expected=lambda p: {"image": 10662, "segmentation_mask": 1000, "video_frame": _expected_frames(p)},
)

VIDEO_META_CSV = Path(__file__).resolve().parent.parent / "data" / "hyper-kvasir-video-metadata.csv"


def _expected_frames(params: dict) -> int:
    """video_frame row count for the sampling parameters: sum over the 374 clips of min(k, frames) (midpoints) or ceil(frames / stride)."""
    frames = pd.read_csv(VIDEO_META_CSV, usecols=["frames"])["frames"]
    stride = params.get("FRAME_STRIDE")
    if stride:
        return int(((frames + stride - 1) // stride).sum())
    return int(np.minimum(frames, params.get("FRAMES_PER_VIDEO", 20)).sum())

REGION_BY_ORGAN = {"Lower GI": "lower-gi-tract", "Upper GI": "upper-gi-tract"}
CATEGORY_DIR_ALIASES = {"quality-of-mucosal-view": "quality-of-mucosal-views"}   # lower-GI videos use the singular folder
IMAGE_COLUMNS = ["Video file", "Organ", "Finding", "Classification"]            # `Video file` is the image UUID (misnomer)
VIDEO_COLUMNS = ["Video file", "Organ", "Finding 1", "Classification 1", "Detailed description of finding", "Finding 2", "Classification 2"]

# The 9 videos whose stored frame count disagrees with duration*fps (all 374 files were fully decoded with ffprobe: `frames` in the metadata is
# exact, what is off is the AVI container header).
FPS_OVERRIDE = {   # fps used for timestamp_s (packets of the two mpeg1video clips are 0.04 s apart -> 25 fps; the metadata says 50)
    "05a868ca-4a74-49d6-8769-b0d62d828d95": 25.0,
    "8120fd0a-929a-4e76-8ffa-110111675154": 25.0,
}
TIMESTAMP_NOTES = {
    "05a868ca-4a74-49d6-8769-b0d62d828d95": "mpeg1video: metadata fps=50 is wrong, 500 frames are 0.04 s apart over 20 s (25 fps); timestamp_s uses 25 fps",
    "8120fd0a-929a-4e76-8ffa-110111675154": "mpeg1video: metadata fps=50 is wrong, 500 frames are 0.04 s apart over 20 s (25 fps); timestamp_s uses 25 fps",
    "478400dc-ae29-473a-b464-2b8cfac7c663": "video stream truncated to the first 336 frames (13.44 s); duration_s (120.24 s) is the longer container/audio length; timestamp_s = index/25 is right for the 336 frames",
    "4c0cae22-4945-4f17-a60b-23688b485d91": "slightly short (776 frames = 31.04 s vs duration_s 31.52); contiguous 25 fps; frame count trusted",
    "4f809023-fb71-4bf3-94de-8ed7b2d59e46": "slightly short (1233 frames = 49.32 s vs duration_s 50.56); contiguous 25 fps; frame count trusted",
    "29170a58-50d8-452b-ab39-5e9c641f5ae9": "video slightly longer than the header duration (3565 frames = 142.6 s vs 141.8 s); frame count trusted",
    "92240a44-8174-4aa7-9011-f8a896cd307e": "video slightly longer than the header duration (2683 frames = 107.3 s vs 106.48 s); frame count trusted",
    "ef31f827-0525-4325-aa67-5c5bd4354c26": "rawvideo with variable frame rate (dropped frames, gaps up to ~1 s): timestamp_s = index/nominal fps is only approximate; use packet pts for exact times",
    "6aa30b9a-8061-4328-9677-5d1509b19ad2": "rawvideo with variable frame rate (dropped frames, gaps up to ~1 s): timestamp_s = index/nominal fps is only approximate; use packet pts for exact times",
}

# label columns copied from an image row to its mask row (masks inherit the labels of the MD5-linked image)
INHERIT = ["region", "site", "category", "finding", "finding_harmonized", "finding_parent", "finding_subtype", "finding_harmonization",
           "label_confidence", "imaging", "procedure", "location_source", "organ_raw", "category_raw", "finding_raw", "n_labels", "bbps_range",
           "dir_region", "dir_category", "dir_finding", "label_category_mismatch", "label_finding_mismatch", "label_folder_mismatch"]


def select_frame_indices(n_frames: int, per_video: int = 20, stride: int | None = None) -> list[int]:
    """Deterministic frame indices of a clip: stride -> 0, s, 2s, ...; else the midpoints of k = min(per_video, n) equal segments
    floor((i + 0.5) * n / k) (never the first / last frame, strictly increasing, always <= n - 1)."""
    n = int(n_frames)
    if n <= 0:
        return []
    if stride is not None:
        return list(range(0, n, int(stride)))
    k = min(int(per_video), n)
    return [((2 * i + 1) * n) // (2 * k) for i in range(k)]


def _none(x):
    return c.blank_to_none(x)


def build(ctx):
    root = ctx.root
    img_dir, vid_dir, seg_dir = root / "labeled-images", root / "labeled-videos", root / "segmented-images"
    seg_img_dir, seg_mask_dir, seg_json = seg_dir / "images", seg_dir / "masks", seg_dir / "bounding-boxes.json"
    image_label_source = ctx.rel(img_dir / "image-labels.csv")
    video_label_source = ctx.rel(vid_dir / "video-labels.csv") + " + " + ctx.rel(VIDEO_META_CSV)
    seg_annotation_source = f"{ctx.rel(seg_json)} + {ctx.rel(seg_mask_dir)} (linked to the labelled image by MD5)"
    ds = META["dataset"]

    # ================================================================= images
    il = c.read_csv_safe(img_dir / "image-labels.csv")
    assert list(il.columns) == IMAGE_COLUMNS, il.columns.tolist()
    assert (il != "").all().all(), "unexpected empty cells in image-labels.csv"
    assert il["Video file"].is_unique and set(il["Organ"]) <= set(REGION_BY_ORGAN)
    image_files = {}
    for p in sorted(img_dir.rglob("*.jpg")):
        assert p.stem not in image_files, f"duplicate image stem {p.stem}"
        image_files[p.stem] = p
    only_disk, only_csv = sorted(set(image_files) - set(il["Video file"])), sorted(set(il["Video file"]) - set(image_files))
    if only_disk:
        ctx.warn(f"{len(only_disk)} image file(s) without a row in image-labels.csv (no rows created): {only_disk[:3]}")
    if only_csv:
        ctx.warn(f"{len(only_csv)} row(s) of image-labels.csv without a file (no rows created): {only_csv[:3]}")

    img_info: dict[str, dict] = {}
    for uuid, organ, finding, classification in zip(il["Video file"], il["Organ"], il["Finding"], il["Classification"]):
        if uuid not in image_files:
            continue
        parts = image_files[uuid].relative_to(img_dir).parts
        assert len(parts) == 4, f"expected <region>/<classification>/<finding>/<uuid>.jpg: {parts}"
        region, category, finding_slug = REGION_BY_ORGAN[organ], c.slugify(classification), c.slugify(finding)
        assert category == classification and finding_slug == finding, "image labels were expected to be slugs already"
        lab = ctx.label(f"{region}|{category}|{finding_slug}")
        assert (lab["region"], lab["category"], lab["finding"]) == (region, category, finding_slug), (uuid, lab)
        fh = lab["finding_harmonized"]
        cat_mismatch = category != CATEGORY_DIR_ALIASES.get(parts[1], parts[1])
        find_mismatch = (fh != parts[2].lower()) or (region != parts[0])
        img_info[uuid] = {
            **lab, "finding_harmonization": "native", "organ_raw": organ, "category_raw": classification, "finding_raw": finding, "n_labels": 1,
            "bbps_range": {"bbps-0-1": "0-1", "bbps-2-3": "2-3"}.get(fh),
            "dir_region": parts[0], "dir_category": parts[1], "dir_finding": parts[2],
            "label_category_mismatch": cat_mismatch, "label_finding_mismatch": find_mismatch, "label_folder_mismatch": cat_mismatch or find_mismatch,
            "path": image_files[uuid],
        }

    # ================================================================= segmentation (JSON + masks + md5 link)
    boxes_raw = json.loads(seg_json.read_text(encoding="utf-8"))
    seg_images = {p.stem: p for p in sorted(seg_img_dir.glob("*.jpg"))}
    seg_masks = {p.stem: p for p in sorted(seg_mask_dir.glob("*.jpg"))}
    assert set(seg_images) == set(seg_masks) == set(boxes_raw), "segmentation images / masks / json keys differ"
    for stem, e in boxes_raw.items():
        assert set(e) == {"height", "width", "bbox"} and type(e["width"]) is int and type(e["height"]) is int, stem
        assert isinstance(e["bbox"], list) and e["bbox"], f"{stem}: no boxes"
        for b in e["bbox"]:
            assert set(b) == {"label", "xmin", "ymin", "xmax", "ymax"} and all(type(b[k]) is int for k in ("xmin", "ymin", "xmax", "ymax")), (stem, b)
            assert 0 <= b["xmin"] < b["xmax"] <= e["width"] and 0 <= b["ymin"] < b["ymax"] <= e["height"], (stem, b)

    # link: the segmented images are byte-identical, renamed copies of labelled images -> size pre-filter, then md5 (cached)
    wanted = {p.stat().st_size for p in seg_images.values()}
    cands = [u for u, i in img_info.items() if i["path"].stat().st_size in wanted]
    cand_md5 = ctx.md5([ctx.rel(img_info[u]["path"]) for u in cands])
    lab_md5 = {u: cand_md5[ctx.rel(img_info[u]["path"])] for u in cands}
    seg_md5_by_rel = ctx.md5([ctx.rel(p) for p in seg_images.values()])
    md5_to_uuid = defaultdict(list)
    for u, m in lab_md5.items():
        md5_to_uuid[m].append(u)
    link: dict[str, str] = {}          # seg stem -> labelled uuid
    for stem, p in seg_images.items():
        twins = md5_to_uuid.get(seg_md5_by_rel[ctx.rel(p)], [])
        assert len(twins) == 1, f"{stem}: {len(twins)} labelled twins"
        link[stem] = twins[0]
    assert len(set(link.values())) == len(link), "a labelled image is claimed by two segmentation images"
    ctx.log(f"   linked {len(link)} segmentation images 1:1 to labelled images ({len(cands)} size candidates hashed)")

    seg_info: dict[str, dict] = {}     # labelled uuid -> geometry columns (+ links)
    n_clipped = 0
    for stem in sorted(seg_images):
        uuid = link[stem]
        info = img_info[uuid]
        assert (info["region"], info["category"], info["finding"]) == ("lower-gi-tract", "pathological-findings", "polyps"), uuid
        e = boxes_raw[stem]
        with Image.open(info["path"]) as im:
            W, H = im.size
        assert (W, H) == (e["width"], e["height"]), f"{stem}: JSON size != image size"
        with Image.open(seg_masks[stem]) as im:
            assert im.mode == "RGB", f"{stem}: mask mode {im.mode}"
            gray = np.asarray(im.convert("L"))
        assert gray.shape == (H, W), f"{stem}: mask size != image size"
        m, removed = c.clean_mask(gray > 127, drop_corner_pixel=True)       # white = polyp; drop the isolated JPEG pixel at (0,0)
        assert m.any(), f"empty mask {stem}"
        boxes = []
        for b in e["bbox"]:
            # JSON max edges can equal W / H (a box touching the border): clip to the inclusive pixel range [0, W-1] x [0, H-1]
            x0, y0, x1, y1 = c.clip_box(b["xmin"], b["ymin"], b["xmax"], b["ymax"], W, H)
            n_clipped += (x1, y1) != (b["xmax"], b["ymax"])
            boxes.append({"label": b["label"], "finding": info["finding_harmonized"], "xmin": x0, "ymin": y0, "xmax": x1, "ymax": y1})
        stats = c.mask_columns(m, [(b["xmin"], b["ymin"], b["xmax"], b["ymax"]) for b in boxes], noise_removed=removed)
        assert stats["mask_in_bbox_fraction"] >= 0.999, f"{stem}: mask foreground outside the boxes"
        seg_info[uuid] = {
            **c.box_columns(boxes, "annotator"), **stats,
            "class_counts_json": c.compact_json({info["finding_harmonized"]: len(boxes)}),
            "seg_stem": stem, "segmented_image_path": ctx.rel(seg_images[stem]), "mask_path": ctx.rel(seg_masks[stem]),
            "mask_format": "jpeg-rgb", "mask_encoding": "gray>127 white=polyp (isolated top-left JPEG noise pixel removed)",
            "annotation_source": seg_annotation_source, "_w": W, "_h": H,
        }
    if n_clipped:
        ctx.log(f"   {n_clipped} box edge(s) equal to the image width / height were clipped to the last pixel (inclusive convention)")

    # ---- image rows (sorted by file path like the old table)
    image_rows, mask_rows = [], []
    for uuid in sorted(img_info, key=lambda u: ctx.rel(img_info[u]["path"])):
        info = {k: v for k, v in img_info[uuid].items() if k != "path"}
        rel_path = ctx.rel(img_info[uuid]["path"])
        row = dict(info, item_id=uuid, source_subset="labeled-images", file_path=rel_path, image_path=rel_path,
                   label_source=image_label_source, label_level="image", annotation_types="class", annotation_format="csv",
                   group_id=None, group_kind="none", group_quality="none")
        desc = f"Endoscopic still image (labeled-images) — {info['organ_raw']} / {info['category']} / {info['finding']}"
        if uuid in seg_info:
            g = {k: v for k, v in seg_info[uuid].items() if not k.startswith("_")}
            mask_id = c.make_sample_id("segmentation_mask", ds, g["seg_stem"])
            row.update(g, has_mask=True, mask_sample_id=mask_id, annotation_types="class|bbox|mask", annotation_format="csv|json-bbox|mask-jpeg")
            desc += f"; has a polyp segmentation mask and {g['n_boxes']} bounding box(es)"
        row["row_description"] = desc
        image_rows.append(ctx.row("image", **row))

    # ---- mask rows (sorted by seg stem)
    for uuid, g_all in sorted(seg_info.items(), key=lambda kv: kv[1]["seg_stem"]):
        info = img_info[uuid]
        g = {k: v for k, v in g_all.items() if not k.startswith("_")}
        stem = g["seg_stem"]
        row = {k: info.get(k) for k in INHERIT}
        row.update(g, item_id=stem, source_subset="segmented-images", file_path=g["mask_path"], image_path=ctx.rel(info["path"]),
                   label_source=image_label_source + " (inherited from the MD5-linked labelled image)", label_level="mask",
                   parent_image_sample_id=c.make_sample_id("image", ds, uuid), has_mask=True,
                   annotation_types="class|bbox|mask", annotation_format="csv|json-bbox|mask-jpeg",
                   width=g_all["_w"], height=g_all["_h"], group_id=None, group_kind="none", group_quality="none")
        row["row_description"] = (f"Binary polyp segmentation mask (segmented-images) of {stem}, linked by MD5 to labelled image {uuid} "
                                  f"— {info['organ_raw']} / {info['category']} / {info['finding']}; {g['n_boxes']} bounding box(es), "
                                  f"{100 * g['mask_foreground_fraction']:.1f}% of the pixels are polyp")
        mask_rows.append(ctx.row("segmentation_mask", **row))

    # ================================================================= videos
    vl = c.read_csv_safe(vid_dir / "video-labels.csv")
    assert list(vl.columns) == VIDEO_COLUMNS, vl.columns.tolist()
    assert (vl["Video file"] != "").all() and vl["Video file"].is_unique
    for col in ["Organ", "Finding 1", "Classification 1"]:
        assert (vl[col] != "").all(), f"unexpected empty {col}"
    assert set(vl["Organ"]) <= set(REGION_BY_ORGAN)
    video_files = {}
    for p in sorted(vid_dir.rglob("*.avi")):
        assert p.stem not in video_files, f"duplicate video stem {p.stem}"
        video_files[p.stem] = p
    assert set(video_files) == set(vl["Video file"]), "video files on disk and rows in video-labels.csv differ"
    meta = pd.read_csv(VIDEO_META_CSV, dtype={"id": "string", "tract": "string", "category": "string", "folder": "string", "codec": "string"})
    meta["id"] = meta["id"].str.strip()
    assert meta["id"].is_unique and set(meta["id"]) == set(vl["Video file"]), "video metadata ids != video-labels.csv ids"
    meta = meta.set_index("id")

    clips = []
    for r in vl.to_dict("records"):
        vid = r["Video file"]
        parts = video_files[vid].relative_to(vid_dir).parts
        assert len(parts) == 4, f"expected <tract>/<category>/<finding>/<uuid>.avi: {parts}"
        region = REGION_BY_ORGAN[r["Organ"]]
        assert region == parts[0], "Organ disagrees with the tract folder"
        category, finding = c.slugify(r["Classification 1"]), c.slugify(r["Finding 1"])
        lab = ctx.label(f"{region}|{category}|{finding}")
        assert (lab["region"], lab["category"], lab["finding"]) == (region, category, finding), (vid, lab)
        fh = lab["finding_harmonized"]
        f2, c2 = c.slugify(r["Finding 2"]), c.slugify(r["Classification 2"])
        f2h = ctx.label(f"finding_2|{f2}")["finding_harmonized"] if f2 and f"finding_2|{f2}" in ctx.vocab.map else f2
        desc = _none(r["Detailed description of finding"])
        if desc is not None and not re.search(r"[A-Za-z0-9]", desc):
            desc = None                                         # the lone U+00A8 cell
        bbps_range = {"bbps-0-1": "0-1", "bbps-2-3": "2-3"}.get(fh)
        bbps_score = None
        if bbps_range and desc:
            mt = re.match(r"^BBPS\s*([0-3])$", desc, flags=re.IGNORECASE)
            if mt:
                bbps_score = int(mt.group(1))
                assert (bbps_range, bbps_score) in {("0-1", 0), ("0-1", 1), ("2-3", 2), ("2-3", 3)}, (vid, bbps_range, bbps_score)
        m = meta.loc[vid]
        assert (m["tract"], m["category"], m["folder"]) == parts[:3], f"{vid}: metadata folder columns disagree with the real location"
        n_frames, fps, dur = int(m["frames"]), float(m["fps"]), float(m["duration_s"])
        suspect = abs(n_frames - round(dur * fps)) > 2
        cat_mismatch = category != CATEGORY_DIR_ALIASES.get(parts[1], parts[1])
        find_mismatch = fh != parts[2].lower()
        qa = ([] if not suspect else ["frames-suspect"]) + (["label-folder-mismatch"] if (cat_mismatch or find_mismatch) else [])
        clips.append({
            **lab, "finding_harmonization": lab.get("finding_harmonization", "identity"),
            "video_id": vid, "organ_raw": r["Organ"], "category_raw": r["Classification 1"], "finding_raw": r["Finding 1"],
            "finding_2": f2, "finding_2_harmonized": f2h, "finding_2_raw": _none(r["Finding 2"]),
            "category_2": c2, "category_2_raw": _none(r["Classification 2"]),
            "n_labels": 1 + int(bool(f2 or c2)), "description": desc, "bbps_range": bbps_range, "bbps_score": bbps_score,
            "dir_region": parts[0], "dir_category": parts[1], "dir_finding": parts[2],
            "label_category_mismatch": cat_mismatch, "label_finding_mismatch": find_mismatch, "label_folder_mismatch": cat_mismatch or find_mismatch,
            "file_path": ctx.rel(video_files[vid]), "n_frames_total": n_frames, "fps": fps, "duration_s": dur,
            "width": int(m["width"]), "height": int(m["height"]), "codec": m["codec"], "frames_suspect": suspect,
            "fps_effective": FPS_OVERRIDE.get(vid, fps), "timestamp_note": TIMESTAMP_NOTES.get(vid), "qa_flags": c.pipe_join(qa),
        })
    assert {k["video_id"] for k in clips if k["frames_suspect"]} == set(TIMESTAMP_NOTES), \
        "the set of suspect videos changed - review FPS_OVERRIDE / TIMESTAMP_NOTES"

    per_video, stride = ctx.params["FRAMES_PER_VIDEO"], ctx.params.get("FRAME_STRIDE")
    selection = f"stride={stride}" if stride else f"even-segment-midpoints k={per_video}"
    frame_rows = []
    for k in sorted(clips, key=lambda k: k["file_path"]):
        idx = select_frame_indices(k["n_frames_total"], per_video, stride)
        for rank, fi in enumerate(idx):
            ts = float(np.round(np.float64(fi) / np.float64(k["fps_effective"]), 4))
            desc = (f"Video frame {fi} of {k['n_frames_total']} (t={ts:.2f} s) from labelled clip {k['video_id']} (labeled-videos) "
                    f"— {k['organ_raw']} / {k['category']} / {k['finding_raw']}")
            if k["finding_2"] or k["category_2"]:
                desc += f"; 2nd label: {k['finding_2_raw'] if k['finding_2_raw'] else '?'}"
            desc += "; label inherited from the clip"
            frame_rows.append(ctx.row(
                "video_frame", **k, item_id=k["video_id"], source_subset="labeled-videos", frame_index=fi, timestamp_s=ts,
                label_source=video_label_source, label_level="clip", annotation_types="clip-class", annotation_format="csv",
                frame_rank=rank, frames_sampled_in_video=len(idx), frame_selection=selection,
                group_id=f"{ds}:{k['video_id']}", group_kind="video", group_quality="exact", row_description=desc))

    ctx.log(f"   {len(image_rows):,} images ({len(seg_info)} with mask), {len(frame_rows):,} frames from {len(clips)} clips, {len(mask_rows)} masks")
    return image_rows + frame_rows + mask_rows
