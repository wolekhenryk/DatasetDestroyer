# Report: `data_to_merge/DataCrohnIPI/` (CrohnIPI - small-bowel capsule images of Crohn's disease)

Reader 3 of 3. Verified with scripts in the scratchpad (`.../scratchpad/DataCrohnIPI/`, `python -I`): CSV parsing, file matching, md5 of all images, header/pixel reading of all images, thumbnails, visual check of 24 images.

## 0. One-paragraph summary

3,484 labelled 320x320 JPEG frames from **small-bowel capsule endoscopy** (README: "endoscopic video capsules"; paper title: Crohn's disease images of the small bowel). **One image-level label per image from 7 classes** (N normal 2,124; lesions E erythema, O oedema, AU aphthoid ulceration, U3-10 ulcer 3-10 mm, U>10 ulcer > 10 mm, S stenosis), a predefined **5-fold assignment** (random per frame, *not* patient-grouped), no boxes / masks / patient ids. Frames come from continuous video segments, so neighbouring files are near-duplicates that sit in different folds (leakage). 14 extra images on disk have no CSV row. Licence **CC BY-NC-ND** (no derivatives!).

## 1. Identity

| item | value |
|---|---|
| name | CROHN-IPI dataset (`https://crohnipi.ls2n.fr/`); Univ. of Nantes, CHU de Nantes, LS2N, IMAD |
| modality | capsule endoscopy, white light. Appearance (circular field of view, villous mucosa, colour) is that of a PillCam-type capsule; the exact device is **not stated** in the README (the burned-in `PillCam SB3` text of see-ai is absent here) |
| papers (README) | A. de Maissin et al., *Added value of a multi-expert annotation of Crohn's disease images of the small bowel...*, Endoscopy Int. Open (accepted); R. Vallee et al., *CrohnIPI: An endoscopic image database...*, Proc. SPIE 11317 (2020), doi 10.1117/12.2543584 |
| licence / caveat | README: "research use only", **CC BY-NC-ND** (link to by-nc-nd/2.0). *NoDerivatives* matters if images are cropped / resized / redistributed in a merged corpus -> check |
| size on disk | 79 MB (75,567,970 bytes of images; per image 14.4-45.2 KB, median 21.1 KB) |

Files: `imgs/` **3,498 `.jpg`** (`00001.jpg` ... `03498.jpg`, contiguous, 5-digit numbers), `CrohnIPI_description.csv`, `Readme.md`. No other files, no sub-folders.

## 2. Annotation sources

`CrohnIPI_description.csv`: UTF-8 without BOM, **CRLF**, ends with a newline, comma separated, **3,485 lines = header + 3,484 data rows**, 3 fields on every line.

| column | meaning | dtype | values |
|---|---|---|---|
| `Frame name` | image file name incl. `.jpg` | string | `00001.jpg` ... ; 3,484 unique, no whitespace |
| `Label` | one of 7 classes (README legend) | string | `N` 2,124; `U3-10` 408; `U>10` 297; `AU` 251; `O` 149; `S` 130; `E` 125 |
| `Fold` | cross-validation test-set number | int 1-5 | 1: 697, 2: 697, 3: 697, 4: 697, 5: 696 |

Quirks: no NA-like values, no case/whitespace variants. Label strings contain `>` and `-` (`U>10`, `U3-10`) - slugify. The README mentions "3 columns ... frame name, label, test set number" - header names are `Frame name,Label,Fold`.

**Orphans (images without CSV row): 14** - `00042, 00093, 00190, 00191, 00192, 00201, 00222, 00313, 00620, 00707, 00708, 00709, 00710, 01022` (all `.jpg`). CSV rows without file: 0. The README says 3,484 images (= CSV), so these 14 are extra, unlabeled files; the neighbouring CSV rows have mixed labels (e.g. 42 lies between AU and U3-10, 93 between N and N). They show ordinary-looking mucosa (00222 shows white oval objects), reason for exclusion unknown (possibly images without expert consensus - **speculation**). Do not treat them as `N`.

## 3. What the annotation IS

**Image-level single-label class** (7 mutually exclusive classes: normal + 6 lesion types/severities). No bounding boxes, masks, polygons, no per-lesion localisation, no free text.
Label legend (README, French abbreviations): E = Erytheme (erythema), O = (O)edema, AU = Aphthoid ulceration, U3-10 = ulceration between 3 and 10 mm, U>10 = ulceration over 10 mm, S = Stenosis, N = Normal.

## 4. Location (anatomy)

* **Small bowel** (capsule endoscopy for Crohn's disease; paper title says small bowel). Dataset-wide constant, known from the README/paper title, **not** stored per file; the segment (jejunum / ileum / terminal ileum) is **not recorded**. Visually consistent: villous small-bowel mucosa, bubbles, bile-stained fluid.
* Unified region: `small-bowel`.

## 5. Findings

| label | meaning | images | nature | per fold (1..5) |
|---|---|--:|---|---|
| N | normal | 2,124 | normal (but frames come from Crohn's-disease capsule exams; README does not say whether healthy controls are included -> "normal mucosa of Crohn patients" is the safe reading) | 435, 414, 423, 433, 419 |
| E | erythema | 125 | pathological (mild) | 21, 26, 35, 22, 21 |
| O | oedema | 149 | pathological | 32, 30, 33, 18, 36 |
| AU | aphthoid ulceration | 251 | pathological | 41, 57, 51, 51, 51 |
| U3-10 | ulcer 3-10 mm | 408 | pathological | 85, 86, 74, 84, 79 |
| U>10 | ulcer > 10 mm | 297 | pathological | 53, 62, 53, 62, 67 |
| S | stenosis | 130 | pathological | 30, 22, 28, 27, 23 |
| total | | 3,484 | 1,360 lesion (39 %), 2,124 normal (61 %) | |

Negatives (normal) exist and are an explicit class `N`. The 3,498 - 3,484 = 14 orphans are unlabeled. Folds are roughly stratified by label.

## 6. Linking keys, grouping ids, splits

* Key: `Frame name` == file name in `imgs/`. 3,484 matched, 0 CSV rows without file, 14 files without row.
* **No patient / video / case id.** The file numbering follows the capsule video order: in file order the label forms 532 runs (mean run length 6.6, max 331) and neighbouring frames have the same label in 84.8 % of pairs (random order: 39.6 %); median 24x24-thumbnail difference of neighbours 16.7 vs 24.4 for random pairs. 129 images have a near-duplicate (cosine > 0.98 of 24x24 grey thumbs); of the 127 such pairs where both are labelled, **99 lie in different folds**, so the shipped folds **leak** near-identical frames between train and test.
* Official split: the **`Fold` column** (5-fold CV, 80/20 each) - frame-wise random, not video-/patient-grouped. For a leakage-safe protocol group by contiguous runs of file numbers (proxy for the capsule video segment) instead of using `Fold` blindly.

## 7. Technical facts

* All 3,498 files: **320x320**, RGB JPEG, no unreadable file. Circular field of view (black corners), no visible text overlay in the 24 images inspected (7 classes x 2 + 10 orphans), colour/brightness vary with transit (green bile, yellow debris, red mucosa). Looks like a crop of the capsule image (the FOV fills the 320x320 square) - sharper/zoomed compared with see-ai's 576x576 frames.
* No EXIF/orientation issues observed (not exhaustively checked for tags).

## 8. Duplicates and overlap

* Inside: MD5 of all 3,498 images -> **0 duplicates** (3,498 distinct). Near-duplicates as in section 6.
* Across datasets in `data_to_merge/` and `out/` (208,093 image files): file size + MD5 -> **0 byte-identical files**. A coarse thumbnail comparison with see-ai (also small-bowel capsule) found no real match (6 best candidates visually checked: different scenes); resized copies cannot be excluded by this test. Kvasir-Capsule (another small-bowel capsule set) was only covered by the exact-bytes test; its frames have a different pixel size, so only resized copies could overlap and a perceptual-hash comparison (not done) would be needed to exclude that.

## 9. Proposed mapping to a unified table

### (a) Row unit
**`image`**, one row per labelled image: **3,484** rows (CSV). Add the 14 orphans only as `unlabeled` rows if wanted (label null, `label_source = none`); recommended: skip. No video, no masks, no boxes.

### (b) Native label -> unified label

region = `small-bowel`; anatomical site = `small-bowel (segment unknown)`.

| native | count | category | finding slug (`finding_harmonized`) | extra columns | confidence |
|---|--:|---|---|---|---|
| N | 2,124 | new `normal` (or `no-finding`) | `normal-mucosa` (the existing vocabulary already has `normal-mucosa` as a video second label) | - | high |
| E | 125 | pathological-findings | `erythema` (same as see-ai class 9) | severity unspecified | high |
| O | 149 | pathological-findings | `edema` (UK: oedema) | - | high |
| AU | 251 | pathological-findings | `aphthoid-ulceration` (parent `ulcer`; clinically close to see-ai/Kvasir-Capsule `erosion`, keep separate) | lesion size < 3 mm implied | high (native), medium (pooling with `erosion`) |
| U3-10 | 408 | pathological-findings | `ulcer` | `lesion_size_class = 3-10mm` | high |
| U>10 | 297 | pathological-findings | `ulcer` | `lesion_size_class = >10mm` | high |
| S | 130 | pathological-findings | `stenosis` | - | high |

Suggested: keep a native-faithful finer slug (`ulcer-3-10mm`, `ulcer-over-10mm`) **and** the parent `ulcer` (e.g. `finding_parent`) so that pooling with other datasets is possible.

### (c) Columns
* Apply: `sample_id` (`image:crohnipi:00001`), `source_type = image`, `source_dataset`, `label_source`, `label_level = image`, `row_description`, `item_id`, `file_path`, `file_ext`, `file_exists`, `file_size_bytes`, `image_path`, `image_md5`, `region`, `organ_raw` (n/a), `category`, `category_raw`, `finding`, `finding_raw` (`U>10` etc.), `finding_harmonized`, `finding_harmonization`, `finding_in_image_vocab`, `n_labels` (=1), `width`, `height` (320), `has_mask`/`has_bbox` = False.
* Not applicable: video columns, mask/bbox columns, `dir_*`, `label_*_mismatch`, `bbps_*`, `finding_2*`, `description`.
* **New columns**: `modality` (`capsule-white-light`), `device` (unknown), `disease_context` (`crohns-disease`), `severity_or_size` (`3-10mm`, `>10mm`, `<3mm-aphthoid`), `finding_parent`, `fold_official` (1-5), `split_group` (proxy: contiguous run id of the file numbering), `orphan_unlabeled` (for the 14), `license` (`CC BY-NC-ND`).

### (d) To read / compute
* Nothing heavy: sizes known (320x320 uniform), md5 of all (75 MB, <1 s), CSV parse (ms). Run-based group ids from file order (ms).

## 10. Pitfalls and open questions

1. **Leakage**: `Fold` is random per frame; adjacent video frames in different folds. Use run-based groups or accept optimistic CV results; no patient id exists.
2. 14 images on disk without a label (not in README's 3,484) - exclude; do not assume normal.
3. Licence **CC BY-NC-ND**: derivatives (resizing, cropping, mixing into new datasets) may be restricted - check before publishing a merged dataset.
4. Device / capsule model and anatomical segment unknown; `N` frames may come from diseased patients (domain: Crohn's patients only) - possible bias for a model trained to separate "normal" in general (other datasets contribute different normals).
5. Class granularity: ulcer size classes and `AU` vs `erosion` need an explicit harmonisation decision with see-ai / Kvasir-Capsule.
6. Class imbalance 61 % normal; lesion classes 125-408 images each (small).
7. Image-level labels only; a lesion may occupy a small part of the 320x320 frame (no localisation).
