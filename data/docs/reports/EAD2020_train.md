# Report: `data_to_merge/EAD2020_train/` (Endoscopy Artefact Detection challenge 2020)

Reader 3 of 3. Verified with scripts in the scratchpad (`.../scratchpad/EAD2020_train/`, `python -I`); md5 of all 5,606 jpg + 5,301 txt files, header/pixel reading of all 643 masks, overlay of boxes on images.

## 0. One-paragraph summary

EAD2020 contains **only 2,531 unique endoscopic images** (31,069 YOLO boxes of 8 *artefact* classes) and **643 multi-channel artefact masks** for a subset of those images; the 5,606 jpg files on disk are the same pictures copied into overlapping folders (3,075 are byte-identical duplicates). **There are no polyp / disease / pathology labels at all** - the classes are image-quality artefacts (specularity, saturation, artifact, blur, contrast, bubbles, instrument, blood). The organ is **not annotated**: the pictures are a mix of mostly upper-GI (oesophagus/stomach-like), colon, bladder (cystoscopy, "URO" overlays) and other views. **Useful as artefact / quality labels (and domain diversity), not for pathology training.** Licence CC BY-NC-SA 4.0 (non-commercial, share-alike).

## 1. Identity

| item | value |
|---|---|
| name | Endoscopy Artefact Detection and Segmentation Challenge 2020 (EAD2020, part of EndoCV2020), training data; organiser S. Ali et al. (Oxford) |
| papers (from `Readme.md`) | Ali et al., *An objective comparison of detection and segmentation algorithms for artefacts in clinical endoscopy*, Sci Rep 2020; Ali et al., *A deep learning framework for quality assessment and restoration in video endoscopy*, Med Image Anal 2021; EAD2019 dataset arXiv 1905.03209 |
| modality | white-light endoscopy mostly, some narrow-band / fluorescence (blue-light bladder frames); frames and short consecutive-frame sequences |
| licence | **CC BY-NC-SA 4.0** (stated in `Readme.md`; full text in `license.txt`) - non-commercial + share-alike obligation for derived tables |
| size | 2.8 GB (framesOnly 1.8 GB, 99Frames 568 MB, sequence 240 MB, allDetection_training 225 MB, sequence_onlyData_Detection 0.9 MB; 643 tif = 2.5 GB uncompressed multi-page) |

Files by extension: **5,606 `.jpg`**, **643 `.tif`**, **5,301 `.txt`** (5,294 YOLO label files + 6 `class_list*.txt` + `license.txt`), `Readme.md`, `Readme.pdf`, 10 `.DS_Store`.

### 1.1 Directory layout and what every sub-folder is

| folder | content | files | relation to the others (all verified by md5) |
|---|---|--:|---|
| `allDetection_training/bbox_images/` | **all detection data**: `.jpg` + `.txt` of the same stem | 2,531 jpg + 2,531 txt | = exact union of the three below; every file is **byte-identical** to its original (2,200 + 99 + 232) -> **canonical copy** |
| `EAD2020_dataType_framesOnly/frames/` + `gt_bbox/` | single frames `EAD2020_frameOnly_00001..02200.jpg` + YOLO boxes | 2,200 + 2,200 | subset of `allDetection_training` (identical) |
| `EAD2020_dataType_framesOnly/segmentation/images_ead2020/` + `masks_ead2020/` | `EAD2020_semantic_00000..00473.jpg` + `.tif` masks (5 channels) | 474 + 474 | **the 474 images are byte-identical copies of 474 images of `frames/`** (renamed; frames numbered 1307-2191, in scrambled order). They have **no txt of their own** - boxes live under the `frameOnly` name (mapping file: `.../scratchpad/EAD2020_train/seg_to_frame_map.csv`, 474 rows) |
| `EAD2020-Phase-II-Detection_Segmentation-99Frames/` | `originalImages/EAD2020_MP10000..10098.jpg`, `bbox/*.txt`, `semanticMasks/*_mask.tif` (6 channels) | 99 + 99 + 99 | subset of `allDetection_training` (identical); the only frames that have boxes **and** masks under one name |
| `EAD2020-Phase-II_dataType_sequence/Detection/<seq>` + `<seq>_bbox` | 5 consecutive-frame sequences: `1445-01` (50), `1445-02` (20), `1445-03` (74), `PYL-02` (60), `PYL-N-02` (28) | 232 jpg + 232 txt | subset of `allDetection_training` (identical) |
| `EAD2020-Phase-II_dataType_sequence/SemanticSegmentation_Sequence/<seq>` + `<seq>_masks` | masks for sequences `1445-01` (50) and `1445-02` (20) | 70 jpg + 70 tif | the 70 images are byte-identical to the same-named images in `Detection/1445-01`, `Detection/1445-02` (6-channel masks) |
| `sequence_onlyData_Detection/` | only the 232 sequence `.txt` boxes, flat | 232 txt | byte-identical to the `*_bbox` txt files |
| `class_list.txt` (+ copies) | bbox class names, one per line (see 3) | | the folder copies (`class_list_bbox.txt`, `framesOnly/class_list.txt`) are identical; `class_list_semantic.txt` (2 copies, identical) lists the mask channels |

Arithmetic proof: 2,531 = 2,200 + 99 + 232 (stem sets disjoint); jpg on disk 5,606 = 2,531 (all) + 2,200 + 99 + 232 + 474 + 70. **Unique images = 2,531**; the others are duplicates. Within each folder there are no duplicate md5s.
Masks: 643 = 474 + 99 + 70, all for images that are in the 2,531 (so unique masked images = 643: 474 in the `frames` set + 99 + 70 of the sequences).

README claims versus reality: README.md says 2,299 single frames (2,200 + 99 OK) + **233** sequence frames (found **232**), detection 31,069 annotations (**exact: 31,069**), segmentation **642** frames / ~3,500 annotations (found **643**); `Readme.pdf` is an older text: **573** frames (= 474 + 99) / 3,248 annotations. Data and `Readme.md` agree on the total number of boxes.

## 2. Annotation sources

### 2.1 YOLO boxes (`*.txt`)
* ASCII, one box per line, **5 fields `class_id cx cy w h`**, class id integer 0-7, coordinates **normalised (0-1), centre + size** (YOLO). Verified by overlaying on images (boxes enclose specular highlights, instruments, bubbles). 31,069 boxes, 0 malformed lines. 133 files (all `EAD2020_frameOnly_*`) use CRLF; all end with a newline.
* Quirks: 13 boxes protrude outside the image by 0.001-0.019 (normalised); 3 zero-area boxes; 8 files contain an exact duplicate line.
* **No image has an empty txt**: every one of the 2,531 images carries >= 1 box, i.e. there are **no negative / artefact-free images** (a quality-free frame is simply absent from the dataset).
* Mapping name -> id: `class_list.txt` line order: 0 specularity, 1 saturation, 2 artifact, 3 blur, 4 contrast, 5 bubbles, 6 instrument, 7 blood (identical in every copy; the README mentions `class_list_bbox.txt`).

### 2.2 Masks (`*.tif`) - multi-page TIFF, one page per class
* Each `.tif` is a **multi-page (multi-frame) 8-bit grayscale TIFF**; PIL (`Image.open(...).n_frames`, `ImageSequence`) reads it. One page = one binary mask of one class; width/height equal the paired image for all 643.
* Page order is given by `class_list_semantic.txt` (`Instrument`, `Specularity`, `Artefact`, `Bubbles`, `Saturation`, `blood`; note trailing space and blank lines in the file). I confirmed the order independently by measuring how much of each page's foreground falls inside boxes of each class: page 0 -> class 6 instrument (>= 0.94), page 1 -> class 0 specularity, page 2 -> class 2 artifact, page 3 -> class 5 bubbles, page 4 -> class 1 saturation, page 5 -> class 7 blood (1.0 in 99Frames).

| mask set | masks | pages | value encoding |
|---|--:|--:|---|
| `framesOnly/segmentation` | 474 | **5** (no blood) | **messy**: of 2,370 pages: 866 all-zero, 526 "sentinel" pages (0 everywhere except the **last pixel row = 255**), 454 clean binary foreground, 524 foreground pages with some intermediate grey values (0.0-1.6 % of pixels not in {0,255}, resampling artefacts) **and** a last row of 255. Use `page > 127` and ignore (zero) the last row |
| `99Frames` | 99 | **6** | clean 0/255, empty pages all 0 |
| sequence `1445-01` | 50 | 6 | clean 0/255 (pages blood / blur etc. empty; only instrument, specularity, artefact present) |
| sequence `1445-02` | 20 | 6 | clean 0/255 |

Polarity: foreground (the artefact) = 255 (white) = "1". Semantic (per-class) masks, not per-instance. Foreground fractions (mean per page): instrument 0.016-0.066, specularity 0.0004-0.013, artifact 0.012-0.193, bubbles ~0.003-0.016, saturation 0.019-0.033, blood 0.010-0.037 (varies by set). Masks exist **only** for 5 (6) of the 8 box classes: `blur` and `contrast` have boxes only.
Masks and boxes are not interchangeable: e.g. for framesOnly masks, 91 of 303 specularity-box images have an empty specularity page, 136 of 331 artifact-box images an empty artifact page.

## 3. What each annotation IS

* **Bounding boxes**: YOLO normalised, 8 artefact classes (frame-level quality annotation).
* **Semantic masks**: per-class binary masks of artefact regions (5-6 classes), multi-page TIFF.
* **No image-level class, no organ, no pathology, no patient label.**

## 4. Location (anatomy)

* **Not annotated; not given by file name, class list or README** (the README does not name organs). The mix is clearly heterogeneous. Visual inspection (contact sheets of 18 sequence + 12 size-group + 32 random 512x512 frames):
  * `512x512` (1,555 images = 61 % of all, octagon-shaped field with black corners, tiny white square bottom right): predominantly upper-GI white-light frames (oesophagus / gastro-oesophageal junction / stomach-like lumen, some blood, some over-saturated red frames) - appears to be a single scope/centre domain.
  * Other sizes (1349x1079, 768x576, 1081x808, 1920x1080 ...): colon-like (red mucosa with many specular dots), bladder (cystoscopy with overlay text `URO` / `HAL URO`, blue-light fluorescence), plus at least one laparoscope-like frame and screens with patient-data text. Details: ~81 distinct image sizes in total.
  * Sequences: `1445-01/-02/-03` red tubular lumen with an instrument in view (upper-GI-like); `PYL-02` / `PYL-N-02` (file stems `Pylseg2` / `Pylseg4`): textured mucosa with a large number of specular reflections and bubbles, one in dark green-grey NBI-like tone (a stomach/pylorus-like view is my guess - **unknown**).
* Per-image organ could only be obtained by manual / heuristic tagging; I would use `region = unknown` and flag that non-GI (bladder) frames exist. I did not attempt to count bladder frames.

## 5. Findings / content

There is **no pathology class**. All classes are artefact or view-quality classes (blood = bleeding / blood obscuring the view; instrument = tool in view):

| id | class | boxes | images with it | in masks? (page) | category |
|--:|---|--:|--:|---|---|
| 0 | specularity | 11,859 | 1,140 | yes (1) | artefact |
| 1 | saturation | 1,423 | 1,127 | yes (4) | artefact |
| 2 | artifact (other: motion, stains, text, colour shift...) | 8,694 | 1,991 | yes (2) | artefact |
| 3 | blur | 749 | 625 | no | artefact |
| 4 | contrast (low contrast / dark) | 1,866 | 1,648 | no | artefact |
| 5 | bubbles | 5,345 | 689 | yes (3) | artefact |
| 6 | instrument | 605 | 417 | yes (0) | instrument |
| 7 | blood | 528 | 225 | yes (5, only in 99Frames + sequences) | artefact (blood obscuring view; clinically bleeding) |
| | **total** | **31,069** | 2,531 images | | |

By subset (images / boxes): framesOnly 2,200 / 25,249; 99Frames 99 / 1,787; seq 1445-01 50 / 524; seq 1445-02 20 / 176; seq 1445-03 74 / 643; seq PYL-02 60 / 1,864; seq PYL-N-02 28 / 826. Mean boxes per image 12.3 (max 156). Image sizes: framesOnly 60 distinct sizes, 99Frames 26, each sequence one size (800x700 for the 1445 sequences, 675x540 for PYL).
Negatives: none. **Pathology: none** (visible lesions, tumours, bleeding appear in the pictures but are not labelled as such).

## 6. Linking keys, grouping ids, splits

* Image <-> boxes: same stem, `.jpg` + `.txt` (proved 2,531/2,531; 0 orphans in `allDetection_training`). Image <-> mask: same stem (`*_mask.tif` suffix in 99Frames and sequence; no suffix in framesOnly/segmentation); proved 474/474, 99/99, 50/50, 20/20 incl. equal pixel size.
* **Masks of `EAD2020_semantic_*` have no box file under that name** - link through byte identity to `EAD2020_frameOnly_*` (map file in scratchpad).
* Name conventions / grouping ids:
  * `EAD2020_frameOnly_NNNNN` (2,200) - single frames, **no patient / video id**; numbering is partly source-ordered (adjacent frames similar, median thumbnail difference 30 vs 52 for random pairs; long runs of 512x512 frames: 1-224, 226-768, 784-1306, 1320-1388; 768x576 runs at 1955-2131). 1,030 of 2,200 frames have a near-duplicate neighbour (24x24 grey cosine > 0.98): **heavy near-duplication, no way to group exactly**.
  * `EAD2020_MPNNNNN` (99) - independent frames (adjacent difference ~ random).
  * Sequences (consecutive video frames, very similar; adjacent thumbnail diff 3-7 vs random 21-37): `EDD2020_SA1445100NN` = sequence `1445-01` (frames 0-49); `EDD2020_M1445200NN` = `1445-02` (0-19); `1445-03_clipSB_avi_N` = `1445-03` (0-73); `Pylseg2_NNNNNN` = `PYL-02` (1-60); `Pylseg4_NNNNNN` = `PYL-N-02` (168-195). **Group id = sequence name** (5 groups).
* No official train/val/test split inside this folder (it is the *train* release; the challenge test sets are not included).

## 7. Technical facts

* All 2,531 images: RGB JPEG, readable, 81 distinct sizes (top: 512x512 1,555; 1349x1079 176; 768x576 165; 800x700 145 [sequences]; 675x540 93; 1081x808 55; 472x499 26; 1079x879 26; 1167x1024 23; 1920x1080 22 ...). Many have black corners / octagonal masks, burned-in text (patient data panels, `URO`, `HAL URO`), and some are almost featureless saturated-red frames.
* Masks: see 2.2; 8-bit gray, LZW-free uncompressed TIFF (2.5 GB for 643 files); reading all 643 with PIL took ~10 s including boxes.
* No videos.

## 8. Duplicates and overlap

* Inside the dataset: see 1.1 - only 2,531 unique images (md5); 3,075 extra copies spread over the folders (2,531 + 2,200 + 99 + 232 + 474 + 70 files for 2,531 pictures).
* Across datasets: size + MD5 test of all jpg/png/tif files of the 3 datasets of this report vs CVC-ClinicDB, ETIS-Larib, hyper-kvasir, kvasir-capsule, polypgen-ninja, PolypsSet and `out/` (208,093 image files) -> **0 identical files** (re-encoded/resized copies not tested). EAD2019 (an earlier challenge) is a different, earlier dataset; EAD2020 may include EAD2019 frames, which are not part of this folder.

## 9. Proposed mapping to a unified table

**Recommendation: ingest only as artefact / quality annotations; exclude from pathology-classification training (or include as unlabeled-pathology background with a `has_pathology_label = False` flag).** No frame is "negative" for artefacts, no frame is pathology-labelled.

### (a) Row unit
* `image`: **2,531** rows from the canonical folder `allDetection_training/bbox_images/` only (ignore the duplicate copies listed in 1.1). `label_level = image/box`.
* `segmentation_mask`: **643** rows (one per `.tif`), `parent_image_sample_id` -> the image row (for `EAD2020_semantic_*` through the md5 map). Mask file has 5 or 6 class pages -> new columns for the page -> class mapping; alternatively expand to one row per (image, class page that is non-empty) = ~1,950 rows (not recommended).
* optional `bbox_annotation` rows (31,069).
* No `video_frame`; the 5 sequences are folders of extracted frames (use `video_id`/`sequence_id` column for grouping).

### (b) Native class -> unified label
region = `unknown` (mixed: upper-GI-like, colon-like, bladder); anatomical site unknown.

| native | count (boxes / images) | proposed category | finding slug | confidence |
|---|---|---|---|---|
| specularity | 11,859 / 1,140 | **`artefact`** (new; or `quality-of-mucosal-views` if the coordinator prefers four-category compatibility) | `specular-reflection` | high |
| saturation | 1,423 / 1,127 | artefact | `saturation` | high |
| artifact | 8,694 / 1,991 | artefact | `other-artefact` | high |
| blur | 749 / 625 | artefact | `blur` | high |
| contrast | 1,866 / 1,648 | artefact | `low-contrast` | medium (label means "low contrast / underexposure") |
| bubbles | 5,345 / 689 | artefact | `bubbles` (Hyper-Kvasir has no equivalent) | high |
| instrument | 605 / 417 | `instrument` (new) or artefact | `instrument` | medium |
| blood | 528 / 225 | artefact (quality) - **not** pathology `bleeding` | `blood-in-view` | medium (clinically bleeding, here a view-quality class) |

Do **not** map any of these to the existing pathology vocabulary (`polyps`, ...). `finding_in_image_vocab` = False for all.

### (c) Columns
* Apply: `sample_id` (`image:ead2020:<stem>`, `mask:ead2020:<stem>`), `source_type`, `source_dataset`, `label_source`, `label_level`, `row_description`, `item_id`, `file_path`, `file_ext`, `file_exists`, `file_size_bytes`, `image_path`, `mask_path`, `image_md5`, `region`, `category`, `finding*`, `width`, `height`, `has_mask`, `has_bbox`, `n_boxes`, `bboxes_json` (use one class per box; the existing schema has a single `bbox_label`, needs `bbox_labels_json` or per-box class inside `bboxes_json`), `bbox_*` union (meaningless for 8 classes with many boxes - prefer `bboxes_json`), `mask_foreground_*` per class (new), `annotation_source`.
* Many boxes per image (mean 12) and **up to 8 classes per image** -> `finding`/`finding_2` cannot store the labels; need `classes_present` (list) and `class_counts_json`.
* New columns: `modality`, `annotation_format` (`yolo-txt`, `multipage-tif-per-class`), `bboxes_norm_json`, `mask_channel_names`, `mask_pages`, `mask_has_sentinel_row`, `sequence_id` (`1445-01` ... or null), `frame_index_in_sequence`, `duplicate_of` (md5 group; canonical = `allDetection_training`), `organ_inferred` (null / manual), `has_pathology_label` (False), `license` (`CC BY-NC-SA 4.0`), `is_non_gi` flag.

### (d) To read / compute
* Image size: header read of 2,531 JPEG (seconds); md5 of 2,531 images (~2-3 s, whole folder tree ~3 s); read 643 TIFF pages (~10 s) for per-class foreground fraction and tight boxes; parse 2,531 txt (<1 s). Optional organ tagging (manual or a quick classifier / size-based heuristic) would be the only expensive step.

## 10. Pitfalls and open questions

1. **No pathology**; do not mix the classes into a polyp / disease column. It does supply artefact labels (useful for a quality / robustness head or for filtering).
2. **Folder overlap**: ingest each image once (canonical `allDetection_training/bbox_images`); otherwise 2.2x duplicates appear (and leak across splits).
3. **Name changes**: `EAD2020_semantic_*` = renamed copies of `EAD2020_frameOnly_*`; boxes are only available under the frameOnly name.
4. **Mask encodings differ** (5 vs 6 pages; messy framesOnly masks with sentinel last rows and non-binary values; page order differs from the bbox class order).
5. Organ missing; non-GI (bladder) and non-endoscopic-looking frames are included (decide to keep, flag or drop). Every frame is heavily artefact-laden by design.
6. Splits: no patient id; near-duplicate frames; sequences must go to one fold each; framesOnly cannot be grouped exactly (cluster by perceptual hash if leakage matters).
7. Licence CC BY-NC-SA 4.0 - non-commercial, share-alike; the merged table inherits SA/NC for these rows.
8. `Readme.md` / `Readme.pdf` counts disagree with each other and with the data (642/573 vs 643 masks; 233 vs 232 sequence frames) - the data is authoritative.
9. `blood` and `instrument` ambiguity: artefact (quality) vs finding (bleeding) vs therapeutic - coordinator decision.
