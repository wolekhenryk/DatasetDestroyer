# polypgen-ninja (`polypgen-ninja/`)

Adapter `unify/adapters/polypgen_ninja.py`, vocabulary `unify/vocab/polypgen-ninja.csv`. Analysis and evidence: `docs/reports/polypgen-ninja.md`. Overlay/independent check: `unify/tools/polyp_adapters_check.py`.

## Source
Dataset Ninja export (Supervisely JSON; labeller `inbox@datasetninja.com`) of **PolypGen** (Ali S. et al., *A multi-centre polyp detection and segmentation dataset for generalisability assessment*, Scientific Data 2023; EndoCV2021). 8,037 colonoscopy frames = 3,762 tagged positive + 4,275 negative, six centres. No README, no `meta.json`, no licence file -> `license = unknown` (check the PolypGen terms before redistribution).

## Layout used / ignored
```
polypgen-ninja/img/<name>.jpg        used   8,037 frames
polypgen-ninja/ann/<name>.jpg.json   used   8,037 annotation files, 1:1 with the images (0 orphans either way)
.DS_Store                             ignored
```
JSON keys: `description` (always empty), `tags[]`, `size`, `objects[]`. `tags`: `institute` (C1-C6), `sequence` (seq1-seq23), `positive` or `negative` (value null). `objects[]`: Supervisely `bitmap` objects, `classTitle = polyp`.
**Decoding a mask**: `bitmap.data` = base64(zlib(PNG)); the PNG (palette mode, values {0,1}; 1 = polyp) is the tight crop of one polyp instance, `bitmap.origin = [x, y]` = its top-left corner in the image. Verified on all 3,734 instances: crops are tight, instances never touch or overlap, each one is one connected component -> the box is the extent of the decoded foreground (inclusive pixels), the union of instances is the semantic mask. Image size in the JSON = real JPEG size for 8,037/8,037.

## Row units and counts (`META["expected"]`)
| source_type | rows |
|---|--:|
| image | **8,037** |
| segmentation_mask | **3,121** (one per image with >= 1 bitmap; 3,734 instances) |

Mask rows: `file_path = mask_path = annotation_path` = the annotation JSON (`file_ext json`), `mask_format = supervisely-bitmap-in-json`, `mask_encoding = bitmap PNG value==1, crop pasted at origin (x,y), OR over instances`; they carry the same labels, boxes and mask statistics as the image row and link both ways (`mask_sample_id` / `parent_image_sample_id`, `seg_stem` = item id). `dup_group_id` is never on mask rows. `item_id` = file name without `.jpg` (unique; one name contains a space).

## Label semantics and the choices made
| native | rows | category | finding / harmonized | `annotation_types` / geometry |
|---|--:|---|---|---|
| `polyp` bitmap(s) (positive) | 3,121 images | pathological-findings | `polyp` / `polyps`, confidence high | `class|mask`; `has_mask` True, `n_boxes` = instances (1: 2,671, 2: 361, 3: 57, 4: 18, 5: 6, 6: 3, 8: 2, 9: 1, 11: 1, 14: 1), per-instance boxes in `bboxes_json`, union box in `bbox_*`, `bbox_source = mask-derived`, `class_counts_json {"polyps": n}`, `mask_noise_pixels_removed = 0` (bitmaps are clean), mask QA columns `mask_in_bbox_fraction` / `mask_json_bbox_max_diff_px` empty (the boxes are derived from the same mask) |
| tag `positive` **without any object** | **641** | pathological-findings | `positive` / `polyps`, confidence **low** | `class` only; `has_mask` False, `n_boxes` empty (unknown), **`qa_flags = annotation-missing`**. Concentrated in whole sequences (seq1 36/36, seq7 48/48, seq11 92, C4 81, ...). Do not use as negatives or as mask-supervised positives. |
| tag `negative` | 4,275 | **background** | `no-polyp-annotated` (derived), confidence high | `class|mask`, `n_boxes = 0`, `has_mask` False, no mask row. **Choice:** the dataset explicitly ships these frames as polyp-free and the annotation JSON has an empty `objects` list, so the empty mask is treated as an ANNOTATED-EMPTY mask (analogous to an empty YOLO txt). NOT verified normal mucosa. |

`finding` is the slug of the native text (`polyp` = classTitle; `positive` / `negative` = the image tag), `finding_raw` the same text. The tag, not the file name, is authoritative (3 `C4_..._negative_*` files are tagged positive, 40 `seq3_..._neg_2_..._positive_*` are tagged negative).

## Location / imaging
Dataset-constant colon / lower-gi-tract, no segment per file (`location_source = dataset-constant`). `procedure = colonoscopy`, `imaging = unknown` (white light and NBI are not distinguished in the files).

## Centres, groups and splits
* `centre` = `institute` tag, only present on 2,700 of 8,037 rows (1,537 single frames, the C5 negatives of seq11-13, the C6 positives of seq16-23); empty for the other 5,337 sequence frames. C1..C6 -> hospital is not in the files. Counts: C1 256, C2 301, C3 457, C4 227, C5 939, C6 520.
* `source_subset`: `single-frame` (1,537) / `sequence` (6,500).
* `group_id` (all rows have one):
  * sequence frames: `polypgen-ninja:<seqN>` (23 groups), `group_kind = sequence`, `exact` - each `seqN` contains one positive sub-sequence and its negative frames; `video_id = seqN`. `frame_index` stays empty: positive and negative frames of a sequence use independent numberings.
  * single frames of C1 (`C1_<NNN>OLCV1_...`, 158 values) and C4 (`C4_<k>_endocv2021_...`, 31 values): `polypgen-ninja:C1-case-<NNN>` / `C4-case-<k>`, `group_kind = case`, **`group_quality = proxy`** (the meaning of NNN / k is inferred, not documented; k has constant image size). 480 rows, 189 groups.
  * all other single frames (C2, C3, C5, C6 and 3 unnumbered C1 files): `polypgen-ninja:centre-<Cx>`, `group_kind = centre`, `group_quality = coarse` (1,057 rows, 5 groups): safe but not splittable below centre level.
* No official split (`split_official` empty). For leave-one-centre-out use `centre` (partial) or the `centre-*` groups.
* Known leak (not flaggable per row): two C2 single frames are near-duplicates (resized) of `seq12`/`seq15` frames, i.e. single frames and sequences of the same centre can share videos.

## Duplicates and conflicts
4 identical-byte pairs (8 rows), all inside one centre: C2 `..001028`/`..001031`, `..001029`/`..001030`; C5 `..50000140`/`..141` (4 vs 1 instance), `..50000284`/`..285`. All 8 rows carry `dup_group_id` and `dup-box-conflict` (same classes, different boxes: IoU between 0.02 and 0.98, median 0.97).

## `extra_json` keys
`orig_name` (file name without the `seqN_`/`Cx_` prefix), `name_prefix` (`seqN` or centre), `sub_sequence` (sequence frames; e.g. `seq14_neg`), `case_number` (C1 NNN / C4 k), `instance_areas_px` (per-instance foreground areas, positives with masks), `negative_basis` (`image tag negative`, negatives only).

## Pitfalls
* 17 % of positives (641) have no mask in this export - treat separately (`annotation-missing`).
* Masks are per-instance tight crops inside JSON, not images; use the recipe above (the adapter did the decoding once for the statistics).
* 34 image sizes (280x240 to 1892x1064), wide black borders, and burnt-in text / patient-info panels (partly blanked) in several centres; crop/resize policy needed (dataset-wide, not flagged per row).
* File names are inconsistent (6+ patterns, a space in one name); use tags.
* `group_quality` below `exact` for all single frames: a fully leakage-safe split exists only at sequence level (23 groups) and, coarsely, centre level.
