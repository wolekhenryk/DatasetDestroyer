# Report: `data_to_merge/polypgen-ninja/`

Reader 2 of 3. Scripts: scratchpad `.../scratchpad/polypgen-ninja/` (all run with `python -I`; nothing under `data_to_merge/` was modified).
Tags: **[measured]** computed from the files, **[inferred]** deduced from the data, **[literature]** background / web search, not verifiable on disk.

## 1. Identity

| item | value |
|---|---|
| name | **polypgen-ninja** = a **Dataset Ninja (datasetninja.com) export of PolypGen** in Supervisely JSON format **[measured + inferred]**. Evidence: every tag/object has `labelerLogin: inbox@datasetninja.com`; layout `ann/<img>.json` + `img/<img>`; Supervisely schema (`tags`, `objects`, `geometryType: bitmap`, `classId`, `classTitle`); six tags `institute=C1..C6`; **3,762 images tagged `positive` + 4,275 `negative` = 8,037**, which equals the published PolypGen figures (3,762 polyp frames, 6 centres) **[literature, web-search snippet; not verifiable here]**. |
| origin **[literature]** | PolypGen: Ali S. et al., *A multi-centre polyp detection and segmentation dataset for generalisability assessment*, Scientific Data 2023 (EndoCV2021 challenge data; centres in Egypt, France, Italy, Norway, UK). The C1..C6 -> hospital mapping is **not** in the files. |
| modality **[inferred]** | colonoscopy, predominantly white light; narrow-band frames may occur but there is no per-file modality field. |
| licence / readme | **No README, no `meta.json` (class list), no licence file** in the folder (a Dataset Ninja export normally has `meta.json`; here only `ann/` and `img/`). |
| size on disk | 1.6 GB (`img` 1.6 GB = 1,685 MB of JPEG, `ann` 39 MB) |
| files | `ann/`: 8,037 `.json`; `img/`: 8,037 `.jpg`; plus one `.DS_Store` at the top. Flat folders, no sub-directories. No other extension. |

```
polypgen-ninja/
  img/<name>.jpg          8,037 files  (name = "<prefix>_<original-name>", see 3/6)
  ann/<name>.jpg.json     8,037 files  (name = image file name + ".json")
```

## 2. Annotation source: `ann/*.json` (Supervisely image annotation)

Format: JSON, UTF-8, no BOM, LF, pretty-printed (4 spaces). One file per image; 8,037 files, all parse. Image <-> JSON are matched **1:1 by file name** (`img/X.jpg` <-> `ann/X.jpg.json`): **8,037 matched, 0 orphan JSON, 0 orphan image** [measured].

Top level keys (always these 4): `description` (always `""`), `tags` (list), `size` (`{height,width}`), `objects` (list).

| field | meaning | values [measured, all 8,037] |
|---|---|---|
| `size.width/height` | pixel size of the image | **equals the real JPEG size for 8,037/8,037**; 34 distinct sizes (see 7) |
| `tags[]` | image-level tags (`id, tagId, name, value, labelerLogin, createdAt, updatedAt`); tag names: `institute` (tagId 20947, value `C1`..`C6`), `positive` (20948, value null), `negative` (20949, value null), `sequence` (20946, value `seq1`..`seq23`) | combos: `negative+sequence` 3,544; `positive+sequence` 1,793; `institute+positive` 1,537; `institute+negative+sequence` 731; `institute+positive+sequence` 432. Exactly one of `positive`/`negative` per image. |
| `objects[]` | one entry per annotated polyp instance | 3,734 objects in 3,121 images; 4,916 images have `objects = []` |
| `objects[].classTitle / classId` | class | only `polyp` / 6461598 (3,734) |
| `objects[].geometryType` | geometry | only `bitmap` (3,734); **no polygons, no rectangles** |
| `objects[].bitmap.data` | base64 string of **zlib-compressed PNG** (the mask crop) | decodes for 3,734/3,734 |
| `objects[].bitmap.origin` | `[x, y]` = top-left pixel (column, row) of the crop in the full image | all inside the image |
| `objects[].id, labelerLogin, createdAt, updatedAt, description, tags` | Supervisely bookkeeping (`description` empty, `tags` always `[]`) | no information |

Object count per image (3,121 images with >= 1): 1: 2,671; 2: 361; 3: 57; 4: 18; 5: 6; 6: 3; 8: 2; 9: 1; 11: 1; 14: 1. **No image has `positive` and `negative`; no `negative` image has an object.**
Quirks: the file name `C4_31_endocv2021_positive_329 2.jpg` contains a **space**; file-name stems are inconsistent (see 6); `tag value` of `positive`/`negative` is `null` (JSON null, not a string).

## 3. What the annotation IS and how to decode it

* **Instance segmentation masks (binary), stored as tight bitmap crops** (Supervisely `bitmap`). One object = one polyp instance = one connected region.
* Verified **[measured]**: (i) every bitmap decodes to a PNG in palette mode `P` with values {0,1} (3,709 bitmaps) or only {1} (25 bitmaps that are completely filled rectangles); polarity: **1 = polyp, 0 = background**. (ii) Every bitmap is **tight**: its 1-pixels touch all four edges of the crop for 3,734/3,734 -> **bounding box = `origin` + PNG size**: `xmin=ox, ymin=oy, xmax=ox+w-1, ymax=oy+h-1` (inclusive pixel indices). (iii) crop + origin lies inside the image for 3,734/3,734; objects of one image **never overlap or touch** (checked by 1-px dilation on all 450 multi-object images) and each bitmap has **exactly one 8-connected component** (checked at 1/4 resolution for all 3,734) -> masks are **per-instance (connected components), not one semantic mask**; the union of instances of an image = the semantic mask. (iv) Overlays of 9 images (single, multi, 14-instance) were rendered and inspected: masks sit on the polyps (some multi-instance images have many small blobs; these are legitimate separate annotations, not noise).
* Mask statistics: area per instance min 51 px, median 54,407 px, max 1,523,608 px; 125 instances < 100 px, 208 < 500 px; as fraction of the image: min 0.003 %, median 4.4 %, max 81 %. Bitmap crop width/height: median 303 x 283 px, max 1716 x 1080.

**Decoding recipe** (stdlib + Pillow + numpy; tested on all 3,734 objects in 8 s):
```python
import json, base64, zlib, io, numpy as np
from PIL import Image
j = json.load(open("ann/NAME.jpg.json"))
H, W = j["size"]["height"], j["size"]["width"]
full = np.zeros((H, W), np.uint8)
inst_boxes = []
for o in j["objects"]:
    b = o["bitmap"]
    m = np.asarray(Image.open(io.BytesIO(zlib.decompress(base64.b64decode(b["data"])))))   # mode P, 0/1, shape (h, w)
    ox, oy = b["origin"]; h, w = m.shape
    full[oy:oy+h, ox:ox+w] |= m                       # semantic mask, 1 = polyp
    inst_boxes.append((ox, oy, ox+w-1, oy+h-1))       # tight inclusive box of this instance
```
* **No bounding boxes / polygons are shipped** in this export - boxes are derived (tight box of each bitmap; cheap, no pixel decoding of the full image; only the PNG header of the crop is needed). The original PolypGen release also has YOLO boxes; they are not here.
* No keypoints, no free text, no image-level class other than the tags.

## 4. LOCATION (anatomy)

Dataset-wide: **colon / lower GI** (colonoscopy polyp dataset; no per-file segment available, no README column) **[inferred + literature]**. Sub-site (cecum, sigmoid, rectum ...) unknown for every file.

## 5. FINDING

| native label | images | instances | category | note |
|---|--:|--:|---|---|
| `polyp` bitmap objects | 3,121 | 3,734 | pathological | polyps of any histology/size; no histology field |
| tag `positive` **without any object** | **641** | 0 | pathological (unlabelled) | positive frame but no mask in this export (see below) |
| tag `negative` | 4,275 | 0 | background / no polyp | all frames from sequences (`sequence` tag present) |
| **total** | **8,037** (3,762 positive + 4,275 negative) | 3,734 | | |

* Single-frame data (tag `institute` but no `sequence`): **1,537 images, all positive**: C1 256, C2 301, C3 457, C4 227, C5 208, C6 88; of them 1,411 have >= 1 bitmap (C1 251, C2 269, C3 456, C4 146, C5 206, C6 83) = 1,640 instances; 126 have none.
* Sequence data (tag `sequence` = `seq1`..`seq23`): **6,500 images** = 2,225 positive (1,710 with bitmap = 2,094 instances; 515 without) + 4,275 negative (3,544 without institute tag, 731 `institute=C5`; the 432 C6 positives are `seq16..seq23`).
* **641 positive-tagged images have no object** (7.97 % of the dataset; 17.0 % of positives): C4 81, C2 32, and whole sequences (`seq1` 36/36, `seq7` 48/48, `seq11` 92 of 228, `seq5` 51 of 250, `seq13` 51 of 250, `seq14` 49 of 249, `seq6` 29, `seq8` 19, `seq10` 18, `seq9` 9, `seq2` 3, `seq4` 2, `seq16..23` 108 of 432 (C6), single-frame C1 5, C3 1, C5 2, C6 5). The concentration in whole sequences suggests that masks were never drawn / were dropped by the export, not random omission; whether the original PolypGen has masks for them cannot be checked here. Visual check of 6 such images: no obvious polyp visible in some. **Do not use them as negatives or as mask-supervised positives.**
* The name stem may contradict the tag: 3 images `C4_35_endocv2021_negative_*` are tagged **positive** (2 have a mask); 40 images `seq3_..._neg_2_endocv2021_positive_*` are tagged **negative**. The **tag is authoritative** (the name is the original folder naming).
* No instrument / artefact / quality / normal-mucosa class. Negatives = polyp-free frames of the sequences; they can contain folds, stool, blur, bubbles, overlay text etc.

Sequence table [measured] (`pos` = positive-tagged, `mask` = positive with >= 1 bitmap; sizes = distinct image sizes in the sequence):

| seq | images | pos | pos with mask | neg | seq | images | pos | pos with mask | neg |
|---|--:|--:|--:|--:|---|--:|--:|--:|--:|
| seq1 | 351 | 36 | 0 | 315 | seq13 | 530 | 250 | 199 | 280 |
| seq2 | 365 | 63 | 60 | 302 | seq14 | 550 | 249 | 200 | 301 |
| seq3 | 55 | 15 | 15 | 40 | seq15 | 394 | 116 | 116 | 278 |
| seq4 | 120 | 48 | 46 | 72 | seq16 | 181 | 40 | 33 | 141 |
| seq5 | 311 | 250 | 199 | 61 | seq17 | 193 | 63 | 44 | 130 |
| seq6 | 181 | 91 | 62 | 90 | seq18 | 184 | 63 | 56 | 121 |
| seq7 | 255 | 48 | 0 | 207 | seq19 | 266 | 56 | 55 | 210 |
| seq8 | 384 | 73 | 54 | 311 | seq20 | 243 | 52 | 31 | 191 |
| seq9 | 150 | 51 | 42 | 99 | seq21 | 207 | 56 | 25 | 151 |
| seq10 | 317 | 25 | 7 | 292 | seq22 | 128 | 46 | 44 | 82 |
| seq11 | 418 | 228 | 136 | 190 | seq23 | 206 | 56 | 36 | 150 |
| seq12 | 511 | 250 | 250 | 261 | | | | | |

## 6. Linking keys, grouping ids, splits

* **Image <-> label**: file name (`X.jpg` <-> `X.jpg.json`), 8,037/8,037 matched.
* **No official train/val/test split** and no split tag in this export.
* **Grouping ids available** (the file name is `<prefix>_<original name>`; `prefix` is either the centre `C1..C6` (single frames) or the `sequence` tag value `seqN`; the tag `sequence` is identical to the file-name prefix for 6,500/6,500 sequence frames):

| group | how to get it | groups | caveat |
|---|---|--:|---|
| sequence frames | tag `sequence` (`seq1`..`seq23`); each tag contains one positive sub-sequence **and its negative frames** (inner name e.g. `seq16_neg`, `seq1_C6`, `0_endocv2021_positive`) | 23 | **the right grouping key** for sequence frames |
| centre | tag `institute` (`C1`..`C6`) exists only on the 1,537 single frames, the 731 C5 negatives (seq11-13) and the 432 C6 positives (seq16-23). For the other 5,337 sequence frames the centre is **not recorded** (can only be guessed from image size). | 6 (partial) | for a leave-one-centre-out split 5,337 frames stay unassigned |
| single-frame case | C1: `C1_<NNN>OLCV1_100[HS]<k>` -> NNN = case-like id (158 distinct, 1-18 frames each, 3 frames without NNN); C4: `C4_<k>_endocv2021_positive_<n>` -> k = case-like id (31 groups, constant image size within k); **C2, C3, C5, C6: only a running frame number, no case id** (C2 numbers 1000-1431, sizes interleave pseudo-randomly) | partial | for C2/C3/C5/C6 use "centre" as the group |

* Frames come from videos: sequence frames are consecutive/near-consecutive video frames (many near-identical); single frames are individual frames, possibly several per polyp. Split by group, never by frame.
* Image sizes also identify the source (e.g. seq1-3 and seq8-10 are entirely 1350x1080; seq16-23 positives are 680x695-910x710, their negatives 1245x1050/1015x1065) - useful as a weak centre proxy only.

## 7. Technical facts

* All 8,037 images: JPEG, RGB; headers read for all and decoded (thumbnail pass) without error. 34 distinct sizes: 1350x1080 (2,611), 1245x1050 (1,394), 1245x1080 (913), 1350x1064 (865), 630x550 (658), 1015x1065 (361), 900x1010 (280), 1440x1064 (162), 910x710 (148), 680x695 (119), 830x700 (109), 1232x1048 (94), 1420x1070 (67), 830x720 (56), 280x240 (26), 645x540 (23), plus 18 sizes with < 20 images (572x498, 628x513, 1760x1070, 1892x1064, ...). Widths 280-1892, heights 240-1080. **Sizes differ per centre/sequence -> resize before batching.**
* Frames are the usual endoscope view with **black borders / pillar-boxing** (very wide for 1350x1080 frames) and often **burnt-in text** (patient-info panel "ID / Name / Sex / Age / D.O.B.", time stamps, "Near Focus" tags; seen in C3 and seq11 frames; the fields appear blank/redacted in the samples inspected). Not removed.
* Decoding all 3,734 bitmaps + union masks took 8 s; connected-component check at 1/4 res 62 s.

## 8. Duplicates and overlap

Tested [measured]:
1. **md5 of all 8,037 images: 8,033 distinct; 4 duplicate pairs** (nearby frame numbers inside one centre): `C2_..001028` = `..001031`, `C2_..001029` = `..001030`, `C5_..50000284` = `..285`, `C5_..50000140` = `..141`. For the last pair the **annotations disagree** (4 instances vs 1) although the pixels are identical.
2. **Near-duplicates between groups** (32x32 gray thumbnail NN, images of other groups): RMSE < 4 only between **C2 single frames and frames of `seq12` / `seq15`** (2 C2 images, matched to 38 sequence frames; at different image sizes in half the cases = same video rescaled); no such case for C1, C3, C4, C5, C6. So C2 single frames are (partly) frames of the same videos as seq12/seq15 -> a mild leakage if single frames and sequences are split independently.
3. **Against PolypsSet** (37,899 images): no image size in common, md5 intersection 0, thumbnail NN min RMSE 17.2, **0 pairs < 8** => no overlap.
4. **Against CVC-ClinicDB** (612 frames 384x288): size not present in PolypGen, md5 intersection 0, thumbnail NN min RMSE 19.9, **0 pairs < 8** => no overlap.
5. Not tested: against `out/` (Hyper-Kvasir), ETIS-Larib, EAD2020_train (PolypGen/EndoCV2021 and EAD2020 are both EndoCV-challenge data; worth a thumbnail test by whoever reads EAD2020).

## 9. PROPOSED MAPPING to the unified table

**(a) Row units**
* `image`: **8,037 rows** (every frame, positives and negatives), with the annotation attached: `has_mask`, `has_bbox`, `n_boxes` (= instances), `bboxes_json` (per-instance tight boxes, same JSON shape as the Hyper-Kvasir boxes, but inclusive-corner from the bitmaps), union box `bbox_*`, `mask_foreground_pixels/fraction`, `mask_tight_*` (= union box).
* Optionally `segmentation_mask` rows to mimic the Hyper-Kvasir convention: **3,121 rows** (one per image with >= 1 bitmap; `parent_image_sample_id` -> the image row). There is no mask *file* (masks live inside the JSON), so `file_path` would be the JSON and the row would carry only the derived statistics. My recommendation: **do not duplicate rows**; keep the 8,037 image rows and mark masks via `has_mask`/`mask_format` (decide with the coordinator). No `video_frame` rows (frames are already extracted images). No per-instance row type is needed (boxes go into `bboxes_json`).

**(b) Native class -> unified label**

| native | count | region | site | category | finding slug | confidence |
|---|--:|---|---|---|---|---|
| `polyp` bitmap (positive with mask) | 3,121 img / 3,734 inst | lower-gi-tract | colon | pathological-findings | `polyps` | high |
| positive tag, no mask | 641 img | lower-gi-tract | colon | pathological-findings | `polyps` with `has_mask=False`, new flag `annotation_missing=True` | low (label exists, geometry missing; suggest excluding from segmentation/detection training, optional classification use) |
| negative tag | 4,275 img | lower-gi-tract | colon | new category `normal`/`background` | `no-polyp` (new; same as the PolypsSet negative slug) | high for "no polyp", none for "normal mucosa" |

**(c) Columns**: apply: identity (`sample_id` e.g. `image:polypgen:<name>`), `source_type`, `source_dataset`, `label_source` (`ann/<name>.json`), `label_level=image`, paths, `region`, `organ_raw`, `category*`, `finding*`, `width`, `height`, `has_mask`, `has_bbox`, `n_boxes`, `bboxes_json`, `bbox_label=polyp`, `bbox_xmin..ymax`, `mask_foreground_*`, `mask_tight_*`, `annotation_source`, `image_md5` (cheap: 2.3 s). Not applicable: video columns, `seg_stem`, `mask_path`(none), `bbps_*`, `finding_2*`, `mask_corner_pixel_removed`, `mask_json_bbox_max_diff_px`. **NEW columns**: `dataset_name`, `centre` (`C1..C6` or null), `sequence_id` (`seq1..seq23` or null), `group_id` (sequence tag; else `centre|case` if parsable else centre), `is_sequence_frame`, `is_negative` (tag), `n_instances`, `annotation_missing`, `mask_format` (`supervisely-bitmap`), `annotation_json_path`, `bbox_format`, `modality` (`unknown`/`WLI`), `size_json_w/h` (optional), `dup_group_id`, `has_overlay_text`, `split_official` (null here).

**(d) To compute**: decode all bitmaps (8 s) for area/box/union stats; image md5 (2.3 s); everything else is in the JSON. Cheap overall (< 2 minutes).

## 10. Pitfalls and open questions

1. **641 positive images without any mask** (17 % of positives; whole sequences seq1 and seq7 have none). Decide: exclude, flag, or treat as weak positives.
2. Masks are **per-instance connected components in tight crops**, not full-size images; naive "mask = file" pipelines will not work - use the recipe.
3. Centre (`institute`) is missing for 5,337 sequence frames; single frames of C2/C3/C5/C6 have no case id. A fully leakage-safe split is only possible at sequence level (23 groups) and for C1/C4 cases; C2 single frames partly share videos with seq12/seq15.
4. File names are inconsistent (6+ stem patterns, one with a space, 3 + 40 names contradicting their tag); use tags, not names, for the label.
5. Image sizes vary widely (34 sizes, up to 1892x1064) plus wide black borders and burnt-in text overlays (patient-info panels); crop/resize policy needed.
6. No README / `meta.json` / licence; PolypGen licence terms (research use, citation of Ali et al. 2023) must be checked by the user.
7. Open: C1..C6 -> hospital mapping; whether the raw PolypGen download (with masks for the 641 images and YOLO boxes) is available; whether the unified table should keep PolypGen negatives under a general `no-polyp` class.
