# Report: `data_to_merge/see-ai/` (SEE-AI small-bowel capsule endoscopy, YOLO boxes)

Reader 3 of 3. Everything below was verified by scripts (scratchpad `.../scratchpad/see-ai/`, `python -I`); statements that come only from memory or from the README are marked as such.

## 0. One-paragraph summary

18,481 JPEG stills (576x576) from **PillCam SB3 small-bowel capsule** exams, each with a YOLO-format `.txt` (normalised `class cx cy w h`), plus one CSV that holds per-image box *counts* per class and the **only** class-id -> name mapping (its first two header rows).
12 lesion classes, 23,033 boxes, 12,320 images with >=1 box and **6,161 images with an empty `.txt` (negatives / "no lesion annotated")**. Multi-label (up to 3 classes per image). No patient / case / video id, no official split, no README / licence in the folder.
The 5 mp4 files are **YOLO model predictions burned into video, not ground truth**. Biggest pitfalls: no grouping id (frames are strongly correlated, numbered in what looks like chronological order), 121 byte-identical image pairs that often carry *different* annotations, and two export batches (black level 16 vs 0) with very different negative rates.

## 1. Identity

| item | value |
|---|---|
| name | SEE-AI project dataset (folder `see-ai`); file names `SEE_AI_project_all_images`, `SEE_AI_project_all_txt`, `all_annotation.csv` |
| modality | capsule endoscopy, white light. The text `PillCam(R)SB3` is burned into the bottom-left of every sampled image (visually checked on ~30 images incl. both batches) -> Medtronic PillCam SB3 small-bowel capsule |
| origin / paper | Not stated anywhere in the folder. From memory (NOT verified from files): Yokote et al., *Small bowel capsule endoscopy examination and open access database with artificial intelligence: the SEE-artificial intelligence project*, DEN Open 2024. The counts (18,481 images / 12,320 annotated / 23,033 boxes) agree with that dataset |
| licence | **none in the folder** (no README / LICENSE) - unknown, must be checked at the original source before redistribution |
| size on disk | 1.3 GB (images 1.2 GB = 1,244,691,999 bytes; txt 48 MB incl. block slack; csv 604 KB; videos 15 MB) |

Files (excluding one `.DS_Store`):

| type | count |
|---|--:|
| `.jpg` | 18,481 |
| `.txt` | 18,481 |
| `.csv` | 1 |
| `.mp4` | 5 |

Layout (note the doubled folder names):

```
see-ai/
  all_annotation.csv                                   (18,484 lines)
  SEE_AI_project_all_images/SEE_AI_project_all_images/image00001.jpg ... image18481.jpg   (18,481)
  SEE_AI_project_all_txt/SEE_AI_project_all_txt/image00001.txt ... image18481.txt         (18,481)
  detected_samplevideo_short/detected_samplevideo_short/{VIdeoNo1,VideoNo2,...,VideoNo5}_detected_short.mp4  (5)
```

## 2. Annotation sources

### 2.1 `all_annotation.csv`
* UTF-8 **with BOM**, **CRLF** line endings (18,483 CRLFs; last line has no terminator), comma separated, 15 fields on every line.
* 18,484 lines = header + a second "class number" row + 18,481 data rows + a final `annotation_sum` row. Naive `pd.read_csv` will therefore treat row 2 and the last row as data.
* Columns (header row): `annotation_class_name`, `image_number`, `angiodysplasia`, `erosion`, `stenosis`, `lymphangiectasia`, `lymph follicle`, `SMT`, `polyp-like`, `bleeding`, `diverticulum`, `erythema`, `foreign body`, `vein`, `annotation_number`.
  * Row 2 (`annotation_class_number`, empty, `0,1,2,...,11`, empty) is the **class-id -> name mapping**.
  * `annotation_class_name` is empty in every data row (it only labels the header / sum rows). `image_number` 1..18481, unique and contiguous = the number in `imageNNNNN`.
  * The 12 class columns hold **the number of boxes of that class in that image** (integers, max per cell: 10, 8, 2, 3, 35, 3, 14, 3, 4, 5, 45, 20). `annotation_number` = total boxes in the image (== sum of the 12 cells for all 18,481 rows).
  * Final row `annotation_sum`: `931,5988,447,612,6792,547,3236,875,62,1028,1656,925`. **These sums are wrong by the class id** for 11 of 12 classes: real column sums (also = txt instance counts) are `931,5987,445,609,6788,542,3230,868,54,1019,1646,914` - i.e. the spreadsheet sum included the class-number row (differences are exactly 0,1,2,...,11). The final `annotation_number` sum cell is empty.
* **The CSV contains no box coordinates and no file names.** It is only per-image class counts. Verified: for all 18,481 images x 12 classes the counts equal the counts derived from the `.txt` files (0 mismatches).

### 2.2 YOLO `.txt` files (the real annotation)
* ASCII, **no trailing newline**, LF line separators, no CR, one box per line, exactly 5 whitespace-separated fields: `class_id cx cy w h` with `class_id` an integer 0..11 and the four floats with 6 decimals, **normalised to image width/height (576)**, centre + size (YOLO). Verified by drawing the boxes on images (see below) and by ranges: `cx` 0.055-0.933, `cy` 0.062-0.936, `w` 0-0.989, `h` 0-0.967; 0 out-of-range boxes (box edges all within [0,1]), 0 duplicate lines, 0 malformed lines.
* One zero-area box: `image07741.txt` line `3 0.114906 0.877222 0.000000 0.000000` (class 3 lymphangiectasia).
* **6,161 `.txt` files are 0 bytes** (empty) = images without any annotated lesion; 12,320 files have >= 1 line.
* Boxes per image: 0 -> 6,161; 1 -> 8,237; 2 -> 2,181; 3 -> 747; 4 -> 354; 5 -> 225; ...; max 45 (long tail, e.g. many lymph follicles / foreign body).
* Distinct classes per image: 0 -> 6,161; 1 -> 10,920; 2 -> 1,356; 3 -> 44 (so **multi-label**; the Hyper-Kvasir style single `finding` + `finding_2` cannot hold the 44 three-class images).
* Link: `imageNNNNN.jpg` <-> `imageNNNNN.txt` <-> csv `image_number = NNNNN`. 18,481 matched in all three directions, 0 images without txt, 0 txt without image, 0 csv rows without file.

### 2.3 `detected_samplevideo_short/*.mp4` - model output, not ground truth
* 5 H.264 files, **576x576, 25 fps**: VIdeoNo1 (typo in name) 355 frames / 14.2 s; VideoNo2 1,005 / 40.2 s; VideoNo3 535 / 21.4 s; VideoNo4 1,505 / 60.2 s; VideoNo5 1,505 / 60.2 s (total 4,905 frames, 15 MB).
* A decoded frame shows a PillCam SB3 frame with an **orange YOLO prediction box and a label with confidence** drawn on it (e.g. `erosion 0.5`). These are detector outputs ("detected"), there are no label files for them -> **do not use as labels**. Whether their frames overlap the 18,481 stills is unknown (not tested; the overlays prevent an exact hash test).

## 3. What each annotation IS

| annotation | kind |
|---|---|
| `.txt` | **object-detection bounding boxes** (YOLO normalised cx,cy,w,h), multi-class, multi-instance; image-level labels can be derived (set of classes present) |
| `.txt` empty | image-level negative: "none of the 12 lesion classes annotated" (not verified "normal": e.g. image00001 is a hair/fibre-like non-diagnostic scene and is a negative) |
| csv | per-image box counts per class (redundant with txt) |
| mp4 | model predictions (not annotation) |

No masks, polygons or keypoints.

## 4. Location (anatomy)

* **Dataset-wide constant: small bowel** (capsule endoscopy with PillCam SB3, images show villous mucosa, jejunal/ileal folds; confirmed visually). The exact segment (duodenum / jejunum / ileum / terminal ileum) is **not recorded** per image or per class -> `unknown segment`. (A few early frames, e.g. image00001, may belong to the oesophagus/stomach/mouth part of a capsule transit; not annotated.)
* region value for the unified table: `small-bowel` (new value, the existing merge only has `lower-gi-tract` / `upper-gi-tract`).

## 5. Findings - class table (verified by txt)

Class id -> name from csv row 1/2. Mapping confirmed visually by drawing boxes on ~12 random single-class images (e.g. class 7 `bleeding` boxes sit on red blood patches, class 10 `foreign body` boxes enclose an orange foreign object, class 2 `stenosis` boxes are large and enclose a narrowed lumen) and by the 1:1 equality of per-image counts with the CSV columns.

| id | name | boxes | images with it | median box w x h (norm.) | nature |
|--:|---|--:|--:|---|---|
| 0 | angiodysplasia | 931 | 825 | 0.17 x 0.16 | pathological (vascular lesion) |
| 1 | erosion | 5,987 | 4,390 | 0.30 x 0.28 | pathological |
| 2 | stenosis | 445 | 442 | 0.75 x 0.74 | pathological |
| 3 | lymphangiectasia | 609 | 572 | 0.21 x 0.21 | pathological |
| 4 | lymph follicle | 6,788 | 1,788 | 0.11 x 0.10 | benign / normal-variant (lymphoid hyperplasia); debatable |
| 5 | SMT (submucosal tumour) | 542 | 528 | 0.50 x 0.48 | pathological |
| 6 | polyp-like | 3,230 | 2,157 | 0.30 x 0.30 | pathological (protruding lesion) |
| 7 | bleeding | 868 | 801 | 0.61 x 0.60 | pathological |
| 8 | diverticulum | 54 | 40 | 0.36 x 0.37 | pathological / anatomical variant |
| 9 | erythema | 1,019 | 915 | 0.61 x 0.59 | pathological (mild) |
| 10 | foreign body | 1,646 | 583 | 0.14 x 0.13 | foreign body (pill, debris) |
| 11 | vein | 914 | 723 | 0.33 x 0.32 | vascular structure (visible vein; normal anatomy / angiectasia mimic) |
| - | (no box, empty txt) | - | 6,161 | - | negative |
| | **total** | **23,033** | 12,320 positive | | |

Single-class images (10,920): erosion 3,550; polyp-like 1,931; lymph follicle 1,594; angiodysplasia 707; bleeding 624; erythema 525; lymphangiectasia 514; vein 481; stenosis 349; foreign body 323; SMT 292; diverticulum 30. Most frequent pairs: erosion+erythema 222, erosion+foreign body 171, SMT+vein 139, erosion+bleeding 116, erosion+stenosis 78, polyp-like+erythema 61.

Negatives are present: 6,161 images (33.3 %), identifiable only by an **empty `.txt` file** (or all-zero csv row).

## 6. Linking keys, grouping ids, splits

* Key: file stem `imageNNNNN` (NNNNN = csv `image_number`). Proven 18,481/18,481 in all directions.
* **No patient / case / video id anywhere** (names are plain sequential numbers; JPEG headers carry only a `Lavc58.134.100` encoder comment, no EXIF; csv has none).
* **No official train/val/test split** shipped.
* Frames are obviously taken from continuous videos: adjacent numbers share the same class set in 75.2 % of pairs (random pairs: 17.3 %); among adjacent positive pairs 78 % have an identical class set (random: 14 %); positives come in runs (2,095 positive/negative runs; e.g. images 18-27 all `polyp-like`, images 28 and 30-36 `erosion`). The numbering therefore looks chronological per examination, but exam boundaries are **not** identifiable (a thumbnail difference threshold gave 1,346 candidate "jumps" - too noisy). 24x24 thumbnail cosine > 0.995 occurs for 327 images (near duplicates, partly adjacent, 145 not within 50 indices).
* Recommendation: split by **contiguous blocks of image numbers** (blocks of several hundred) as a proxy group id, and keep the 121 duplicate pairs (section 8) in the same fold. A random per-image split will leak.

## 7. Technical facts

* All 18,481 JPEGs: 576x576, RGB, baseline, no unreadable header (header-read of all). File size 24.7 KB - 167 KB (median 66 KB).
* Circular field of view inside a black square: black corners, **burned-in text `PillCam(R)SB3` bottom-left**, a small white dot near the top-right in some frames, and a dark top-left patch (in a sample of every 37th image, i.e. 500 images, numbers 1-17,085 have a constant grey level 16 in the top-left patch and numbers 17,086-18,481 level 0). Consider masking the bottom ~40 rows / top-left patch if the overlay should not be learned (not checked whether any box overlaps the text).
* Two export batches are distinguishable: images 1-17,085 carry the JPEG comment `Lavc58.134.100` and black level 16 (limited-range video frames); images 17,086-18,481 (1,395 files; image18424 is an exception with the comment) have no comment and black level 0. **Class balance differs**: batch 2 has only 119 negatives of 1,396 (8.5 %) versus 6,042 of 17,085 (35 %) in batch 1 -> a model can learn the batch as a shortcut for "has lesion". Check sampling of negatives.
* Videos: see 2.3.

## 8. Duplicates and overlap

* Inside the dataset: MD5 of all 18,481 images -> 18,360 distinct; **121 groups of exactly 2 byte-identical images (242 images)**. 111 pairs are both positive, 9 both negative, 1 mixed (one empty, one with boxes). Index gaps: median 48, max 15,683 (pairs such as 121 <-> 15804, 225 <-> 13494 are far apart; images 1-2,000: 53 duplicates, 10,001-12,000: 126). **Their labels often differ**: identical label text in only 9 pairs; same class multiset in 93 of 121; different class multiset in 28 (18 with different class *sets*); e.g. image00225 `bleeding` large box vs image13494 `erosion` small box for the same picture, 130 <-> 15806 `lymph follicle` x3 vs x6 with different box positions. Looks like the same frame annotated twice in two sessions (conflicting / re-annotated). -> Keep one copy (or both in one fold) and flag.
* Across datasets (`data_to_merge/*` and `out/`, 208,093 image files): size-collision + MD5 test of all see-ai, EAD2020 and CrohnIPI images against CVC-ClinicDB, ETIS-Larib, hyper-kvasir, kvasir-capsule, polypgen-ninja, PolypsSet and `out/` -> **0 byte-identical files**. Not tested: re-encoded / resized copies. A crude coarse-thumbnail comparison of see-ai vs DataCrohnIPI found no real matches (6 best candidates inspected: different scenes). Kvasir-Capsule is another capsule dataset (Olympus capsule, from memory) with overlapping class names (angiectasia, erosion, erythema, foreign body, lymphangiectasia, blood ...), but a different device / source; no overlap expected.

## 9. Proposed mapping to the unified table

### (a) Row unit
* **`image`** - one row per JPEG: **18,481 rows** (12,320 positive + 6,161 negative). Boxes kept as JSON on the row, like the existing `bboxes_json`.
* Optional **`bbox_annotation`** rows (one per box, **23,033** rows) linked with `parent_image_sample_id`, only if the training pipeline wants object-level rows (the existing merge duplicated images for masks in the same way). Not required.
* No `video_frame` rows (the mp4 are predictions; if ever used, as `video_frame`-like rows flagged `label_source = model prediction`, not recommended).

### (b) Native class -> unified label

region = `small-bowel` for all; anatomical site = `small-bowel (segment unknown)`.

| native id / name | count (boxes / images) | category | finding slug (`finding_harmonized`) | confidence |
|---|---|---|---|---|
| 0 angiodysplasia | 931 / 825 | pathological-findings | `angiectasia` (= Kvasir-Capsule "Angiectasia"; keep native `angiodysplasia` in `finding_raw`) | high |
| 1 erosion | 5,987 / 4,390 | pathological-findings | `erosion` | high |
| 2 stenosis | 445 / 442 | pathological-findings | `stenosis` (video vocabulary has lower-GI `stenosis`; region differs) | high |
| 3 lymphangiectasia | 609 / 572 | pathological-findings | `lymphangiectasia` | high |
| 4 lymph follicle | 6,788 / 1,788 | pathological-findings (or new `normal-variant`) | `lymphoid-follicle` | medium (benign variant) |
| 5 SMT | 542 / 528 | pathological-findings | `submucosal-tumor` | high |
| 6 polyp-like | 3,230 / 2,157 | pathological-findings | `polyp-like-lesion`; may be pooled with `polyps` only after deciding that small-bowel protrusions equal colonic polyps (I would keep separate, `region` distinguishes) | medium |
| 7 bleeding | 868 / 801 | pathological-findings | `bleeding` (Kvasir-Capsule: `blood-fresh` / `blood-hematin`) | high |
| 8 diverticulum | 54 / 40 | pathological-findings | `diverticulum` | medium |
| 9 erythema | 1,019 / 915 | pathological-findings | `erythema` | high |
| 10 foreign body | 1,646 / 583 | pathological-findings (or new `content`) | `foreign-body` | medium |
| 11 vein | 914 / 723 | pathological-findings or anatomical-landmarks | `vein` (visible venous pattern; normal anatomy mimic) | low - coordinator decision |
| empty txt | 6,161 images | new category `normal` (or `no-finding`) | `no-annotated-finding` (do **not** call it "normal mucosa": not verified) | medium |

Multi-label rows: store all classes (e.g. `findings_all` = pipe-separated, `class_counts_json`); `finding` = most frequent / first class, `finding_2` = second. 44 images have 3 classes.

### (c) Existing 76 columns
* Apply as-is: `sample_id` (use `image:see-ai:image00018` - bare `imageNNNNN` collides in meaning with other datasets), `source_type`, `source_dataset` (`see-ai`), `label_source`, `label_level` (`image`; boxes = `box`), `row_description`, `item_id`, `file_path`, `file_ext`, `file_exists`, `file_size_bytes`, `image_path`, `region`, `organ_raw` (n/a -> `small bowel`), `category(_raw)`, `finding(_raw|_harmonized|_harmonization)`, `finding_in_image_vocab`, `finding_2*`, `n_labels`, `width`, `height` (=576 for all), `n_boxes`, `bboxes_json`, `bbox_label`, `bbox_xmin..ymax` (union of boxes; convert normalised -> pixel inclusive corners), `has_bbox`, `annotation_source`, `image_md5` (compute for all: 1.2 GB, ~20 s).
* Not applicable: video columns, mask columns, `dir_*` (no folders per class), `label_*_mismatch`, `bbps_*`, `description`.
* **New columns needed**: `modality` (`capsule-white-light`), `device` (`PillCam SB3`), `annotation_format` (`yolo-txt`), `bboxes_norm_json` (original normalised boxes with class ids), `class_counts_json` / `findings_all` / `n_classes_in_image`, `is_negative` (empty txt), `duplicate_group_id` (MD5 group) + `duplicate_label_conflict`, `export_batch` (1: <=17,085, 2: >=17,086), `split_group` (block id proxy), `native_class_id`, `label_certainty`.

### (d) To compute / read
* Nothing mandatory beyond parsing 18,481 small txt files (seconds). Image size already known (576x576). MD5 of all images ~20 s; thumbnails / perceptual hashes for near-duplicate grouping ~25 s. No video decoding needed.

## 10. Pitfalls and open questions

1. **CSV is not tidy**: BOM, CRLF, an extra class-number row (row 2) and a final sum row that is wrong by the class id; it contains counts, not boxes. Use the `.txt` files as the source of truth and the CSV only for id -> name.
2. Class names have spaces / mixed case (`lymph follicle`, `foreign body`, `SMT`, `polyp-like`); slugify (`lymph-follicle`, `foreign-body`, `smt`).
3. **No patient/exam ids**, so leakage-safe splits are impossible exactly; contiguous-block splits are a heuristic. Ask the user whether a coarser guarantee (e.g. keep number ranges together) is acceptable.
4. 121 exact duplicate pairs with conflicting annotations (28 with different class multisets) - decide which annotation wins or drop both.
5. "No lesion annotated" negatives may still contain non-diagnostic frames (hair-like/food, bubbles, turbid fluid) and unlabelled benign structures; class imbalance by export batch (see 7).
6. `lymph follicle` and `vein` are arguably benign / normal structures; decide whether they count as `pathological-findings`.
7. Licence unknown (no file). Videos are predictions only.
8. Class vocabulary overlap with Kvasir-Capsule (a second small-bowel capsule set in `data_to_merge/`) suggests harmonising slugs across both (angiectasia / erosion / erythema / foreign-body / lymphangiectasia / bleeding).
