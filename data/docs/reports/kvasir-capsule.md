# kvasir-capsule (data_to_merge/kvasir-capsule) - reader report

Reader 1 of 3. All numbers come from scripts run in the scratchpad (`.../scratchpad/kvasir-capsule/`, python `-I`); the folder was only read.

## 0. Key findings in 10 lines

* Capsule endoscopy (whole GI tract: stomach -> small bowel -> colon), **47,238 JPEG frames, 14 classes, 336x336 px, class = folder name**. Nothing else ships: **no CSV/JSON/README, no bounding boxes, no official splits, no video list**.
* Frame filename = `<16-hex video id>_<frame number>.jpg` -> **43 source videos**, 1,098 frames/video on average. This is the grouping key for video-wise splits (frames are consecutive: 98.9 % of in-class neighbours differ by exactly 1 frame).
* **9 frames are labelled twice** (identical bytes in two class folders: 8x Erosion+Pylorus, 1x Ampulla of vater+Pylorus) -> 47,229 distinct images; `finding_2` slot needed.
* Anatomical landmark classes (Pylorus, Ileocecal valve, Ampulla of vater) are labels, **no per-frame location label exists** for the other 11 classes. I show that location can be *derived* per frame from the order of the Pylorus / Ileocecal-valve frames inside each video (sect. 4).
* Extremely imbalanced: Normal clean mucosa 72.7 %; Ampulla of vater 10, Blood-hematin 12, Polyp 55 frames, each from a single video.
* Images are plain endoscope frames with an **octagonal field of view (black corner cuts ~5 % of pixels + 1-px black frame)**; no text overlays.

## 1. Identity

* Name: **Kvasir-Capsule** (Smedsrud et al., Sci Data 2021; Olympus capsule endoscope, Baerum Hospital, Norway - this is literature knowledge, the folder contains no README). Modality: **video capsule endoscopy (VCE)**, white light, 336x336 px JPEG frames (the full public dataset has 117 videos and ~4.7 M frames; this folder is the *labelled-frames* part, 43 videos).
* Licence: no licence file in the folder. From memory the published dataset is CC BY 4.0 - **unverified, check before redistributing**.
* Size on disk 646 MB; 47,238 `.jpg` + 1 `.DS_Store`; no other file type.
* Layout (one level, class folders contain the frames directly):

| folder (= class) | files |
|---|--:|
| Normal clean mucosa | 34,338 |
| Ileocecal valve | 4,189 |
| Reduced mucosal view | 2,906 |
| Pylorus | 1,529 |
| Angiectasia | 866 |
| Ulcer | 854 |
| Foreign body | 776 |
| Lymphangiectasia | 592 |
| Erosion | 506 |
| Blood - fresh | 446 |
| Erythema | 159 |
| Polyp | 55 |
| Blood - hematin | 12 |
| Ampulla of vater | 10 |
| **total** | **47,238** |

(These 14 class counts are the published Kvasir-Capsule counts as far as I remember them; the total 47,238 matches the published number.)

## 2. Annotation sources

The **only annotation is the folder name** (class). There is no label CSV/JSON in the folder (searched: no `.csv/.json/.txt/.md/.xml` of any kind). Missing compared with the public release (from literature, not present here): `metadata.csv`, labelled-video list, COCO bounding boxes (a few thousand boxes), `official_splits`. Folder names contain spaces and one `-` with spaces (`Blood - fresh`).

* Encoding: n/a. Quirks: sentence-case names with spaces (slugify rule from the existing merge gives `ampulla-of-vater`, `blood-fresh`, `blood-hematin`, `foreign-body`, `ileocecal-valve`, `normal-clean-mucosa`, `reduced-mucosal-view`, ...).

## 3. What the annotation is

**Frame-level single-class label** (one class per file, taken from the parent folder). Exception: 9 frames exist in two class folders with identical bytes = multi-label frames (see sect. 8). No masks, no boxes, no polygons, no free text, no severity.

## 4. Location (anatomy)

* **Dataset level:** whole GI tract (swallowed capsule: oesophagus -> stomach -> small bowel -> colon). Not constant per file.
* **Per class (landmarks):** Pylorus = stomach/duodenum junction; Ampulla of Vater = duodenum (second part, papilla); Ileocecal valve = terminal ileum/caecum junction. These three classes *are* the location labels.
* **Per class (findings):** no site label in the dataset. Literature says most pathologies are small-bowel lesions, which is consistent with what I derived below.
* **Derived per-frame zone (my analysis, heuristic):** the frame number is the position inside the source video (time order). In the 43 videos, the Pylorus frames and the Ileocecal-valve frames identify the stomach -> small-bowel -> colon transitions: Pylorus is present in 32 videos, Ileocecal valve in 34, **both in 24 videos, and in all 24 the pylorus frames precede the ileocecal frames (24/24)**; 8 videos have only the pylorus, 10 only the ileocecal valve, 1 video neither. Zone rules: frame < first pylorus frame -> *stomach* (includes oesophagus); between last pylorus and first ileocecal frame -> *small-bowel*; after last ileocecal frame -> *colon*; if only one landmark exists the zone on the other side is *unknown*.

Frames per derived zone (all 43 videos; "unknown" = landmark of the other side missing in that video):

| class | stomach | small-bowel | colon | at-landmark / unknown |
|---|--:|--:|--:|--:|
| Normal clean mucosa | 816 | 19,765 | 0 | 6,281 before-ileocecal (stomach or SB) + 7,476 after-pylorus (SB or colon) |
| Reduced mucosal view | 0 | 1,188 | 0 | 1,264 before-ileocecal + 454 after-pylorus |
| Angiectasia | 108 | 663 | 0 | 95 after-pylorus |
| Foreign body | 301 | 475 | 0 | 0 |
| Erosion | 83 | 285 | 44 | 86 after-pylorus + 8 at pylorus |
| Ulcer | 0 | 145 | 0 | 582 after-pylorus + 127 video without landmarks |
| Lymphangiectasia | 0 | 592 | 0 | 0 |
| Erythema | 0 | 159 | 0 | 0 |
| Polyp | 0 | 55 | 0 | 0 |
| Blood - fresh | 22 | 0 | 0 | 424 after-pylorus |
| Blood - hematin | 12 | 0 | 0 | 0 |
| Ampulla of vater | 0 | 0 | 0 | 9 after-pylorus + 1 at pylorus (duodenum by definition) |
| Pylorus / Ileocecal valve | landmark classes (1,529 / 4,189) | | | |

Take-aways: (a) **colon frames are practically absent** (only 44 Erosion frames come out as colon); (b) the Kvasir-Capsule "Polyp" class is 55 small-bowel frames from one video - not comparable with colonoscopy polyps; (c) `stomach` here includes the oesophagus; (d) the rule assumes a single forward pass (capsule retrograde movement is possible), so keep it as an optional *derived* column with its source flagged, not as ground truth.

## 5. Findings

| class | frames | videos | kind | note |
|---|--:|--:|---|---|
| Normal clean mucosa | 34,338 | 37 | normal | the only "negative"-like class; clean view |
| Reduced mucosal view | 2,906 | 7 | quality | bubbles/debris/turbid fluid obscure the mucosa |
| Pylorus | 1,529 | 32 | landmark | |
| Ileocecal valve | 4,189 | 34 | landmark | |
| Ampulla of vater | 10 | 1 | landmark | |
| Angiectasia | 866 | 6 | pathology | vascular lesion |
| Ulcer | 854 | 3 | pathology | |
| Erosion | 506 | 9 | pathology | |
| Lymphangiectasia | 592 | 3 | pathology | |
| Erythema | 159 | 3 | pathology | |
| Polyp | 55 | 1 | pathology | |
| Blood - fresh | 446 | 2 | pathology (bleeding) | |
| Blood - hematin | 12 | 1 | pathology (old blood) | |
| Foreign body | 776 | 4 | content / artefact-like | ingested/retained material |

Negatives: there is no explicit "no finding" class; `Normal clean mucosa` plays that role. Frames that are neither normal nor a listed finding are simply not part of this (labelled-only) set.

## 6. Linking keys, grouping, splits

* Key = file stem = `<video_id>_<frame>`; unique except for the 9 double-labelled frames (same stem in two class folders). All 47,238 filenames match `^[0-9a-f]{16}_\d+$` (0 unparsed); video id length 16 for all.
* **43 distinct video ids, frame numbers 27-89,099.** Frames/video min 74, median 1,002, max 2,394; the 5 biggest videos hold 22.9 % of all frames.
* Frames of one (video, class) are mostly **consecutive**: 143 (video, class) groups; of all within-group neighbours 46,588 differ by 1 frame (98.9 %), the rest by 2-13+. -> massive near-duplicates; **split by video id, never by frame**.
* Class availability by number of videos (limits video-wise splitting): Ampulla 1, Polyp 1, Blood-hematin 1, Blood-fresh 2, Erythema 3, Lymphangiectasia 3, Ulcer 3, Foreign body 4, Angiectasia 6, Reduced mucosal view 7, Erosion 9; Pylorus 32, Ileocecal 34, Normal 37. With grouped k-fold some classes can never appear in train and test at once.
* Official train/val/test splits: **not shipped**.

## 7. Technical facts

* All 47,238 files: JPEG baseline, 3 components (RGB), **336 x 336** (single size, header read of every file, 4.2 s), no progressive, no EXIF, 0 unreadable. File size 6.8-31 KB (median ~12 KB per class).
* Plain frames, no text overlays, no burnt-in annotations (montage of 1 random frame per class + mean image of 1,500 frames inspected). **Octagonal field of view**: the four image corners are black (mean over 1,500 random frames: 20x20 corner windows 100 % dark; 5,675 of 112,896 pixels (5.0 %) are dark in >= 95 % of frames, corner-cut legs ~54 px) plus a 1-pixel black frame at all four edges. Mask or crop if the model must not see this; it is identical for every class (no shortcut), but it differs from the round/rectangular fields of the colonoscopy datasets.
* Colours: yellowish-brown small-bowel look; classes differ in hue a lot (bile, bubbles) - domain shift versus colonoscopy white-light datasets is large.

## 8. Duplicates and overlap

* **Inside:** md5 over all 47,238 files: 47,229 distinct; the 9 repeats are exactly the double-labelled frames: Erosion/Pylorus (8) and Ampulla of vater/Pylorus (1): `eb0203196e284797_1125, _1126, _1130, _1131, _1135, _1136, _1137, _1157` (the last is the Ampulla one) and `fb86bc87d3874cd7_3660`. No duplicates inside any single class. These are multi-label frames, not copy errors.
* **Across `data_to_merge/`:** no other dataset contains a single 336x336 image (header scan of 136,904 images in all 9 folders; the 612 `CVC-ClinicDB/TIF/Original` files could not be read by Pillow, their PNG twins are 384x288) -> **zero byte-identical overlap possible**. Other capsule datasets in the repo have other resolutions: DataCrohnIPI 320x320, see-ai 576x576. Re-encoded / resized copies (e.g. of Kvasir-Capsule inside DataCrohnIPI) were **not** tested.
* No overlap with `out/` (derived from Hyper-Kvasir; colonoscopy/gastroscopy only).

## 9. Proposed mapping to the unified table

### 9a. Row unit

* `source_type = image` (one JPEG = one row); frames are real files, so **not** `video_frame` (which in the existing merge means "addressed frame inside an .avi"). Columns `video_id` and `frame_index` are *also* filled for these image rows (grouping key, provenance).
* Recommended rows: **47,229** (one per distinct image; the 9 double-labelled frames carry `finding` + `finding_2`, `n_labels = 2`). Alternative: 47,238 (one row per file; then the 9 pairs share a `sample_id` stem and must be grouped together in splits).
* `sample_id` proposal: `image:kc:<vid>_<frame>` (the filename stem is unique across the 43 videos).

### 9b. Native class -> unified label

Existing vocabulary (`finding_harmonized`) is reused where the meaning is the same; new slugs otherwise. `region` uses the brief's values; for the 11 non-landmark classes I give `unknown` as dataset-level value plus the derived majority zone from section 4 (to be stored in a separate derived column).

| native class | n | region | site (anatomical) | category | finding slug | existing-slug match | confidence |
|---|--:|---|---|---|---|---|---|
| Pylorus | 1,529 | upper-gi-tract | pylorus (stomach-duodenum junction) | anatomical-landmarks | `pylorus` | = HK `pylorus` (upper, anatomical) | high |
| Ileocecal valve | 4,189 | lower-gi-tract (ileum/cecum junction; alt. small-bowel) | ileocecal valve | anatomical-landmarks | `ileocecal-valve` (new) | related to HK `cecum`, `ileum` (not equal) | medium (region) / high (class) |
| Ampulla of vater | 10 | small-bowel (duodenum; HK convention would say upper-gi-tract) | duodenum (papilla of Vater) | anatomical-landmarks | `ampulla-of-vater` (new) | related to HK video `ercp` ("papilla vateri") but not the same | high (class) / medium (region naming) |
| Normal clean mucosa | 34,338 | unknown (derived: 96 % of the located frames are small-bowel) | - | **normal** (new category) | `normal-mucosa` (new) | HK has none as class (only video `Finding 2` text `normal mucosa`) | high |
| Reduced mucosal view | 2,906 | unknown (derived mostly small-bowel) | - | quality-of-mucosal-views | `reduced-view` | = HK upper-GI video class `reduced-view` (same meaning; HK clips are gastroscopy) | medium-high |
| Angiectasia | 866 | unknown (derived: SB 663, stomach 108) | - | pathological-findings | `angiectasia` (new) | related to HK `gastric-antral-vascular-ectasia` (GAVE) - different disease, keep separate | high |
| Ulcer | 854 | unknown (derived: SB 145; most frames unlocated) | - | pathological-findings | `ulcer` | = HK upper-GI video class `ulcer` | high (class) |
| Erosion | 506 | unknown (SB 285, stomach 83, colon 44) | - | pathological-findings | `erosion` (new) | none | high |
| Lymphangiectasia | 592 | unknown (derived: SB 592) | small bowel | pathological-findings | `lymphangiectasia` (new) | none | high |
| Erythema | 159 | unknown (derived: SB 159) | small bowel | pathological-findings | `erythema` (new) | none | high |
| Polyp | 55 | unknown (derived: SB 55) | small bowel | pathological-findings | `polyps` (**keep `region`/`modality` in the key!**) | = HK `polyps` by name; clinically a small-bowel polyp seen by a capsule | medium (name equal, domain very different) |
| Blood - fresh | 446 | unknown (stomach 22, rest unlocated) | - | pathological-findings | `blood-fresh` (new) | none (HK: none) | high |
| Blood - hematin | 12 | unknown (derived: stomach 12) | stomach (derived) | pathological-findings | `blood-hematin` (new) | none | high |
| Foreign body | 776 | unknown (stomach 301, SB 475) | - | pathological-findings (alt. new category `artefact`/`foreign-object`) | `foreign-body` (new) | none | medium (category) |

Region/site for findings is **not in the source**; recommend columns `region` = `unknown`, `region_derived` (`stomach`/`small-bowel`/`colon`/`unknown`) and `region_derived_source = landmark-order` so downstream users can ignore it. Optional shortcut if a single value is required: `region = small-bowel` for the 11 non-landmark classes (supported by 94 % of the 24,713 frames that could be located: 23,327 SB, 1,342 stomach, 44 colon), flagged low confidence.

### 9c. Columns

Existing columns that apply: `sample_id`, `source_type`, `source_dataset` (`kvasir-capsule`), `label_source` (`class = parent folder`), `label_level` (`image`), `row_description`, `item_id`, **`video_id`** and **`frame_index`** (now also on image rows; semantics: video hash id / original frame number), `image_md5` (cheap; useful for dedupe), `file_path`, `file_ext`, `file_exists`, `file_size_bytes`, `image_path`, `region`, `category`, `category_raw` (= null; there is none), `finding`, `finding_raw` (folder name), `finding_harmonized`, `finding_harmonization`, `finding_in_image_vocab`, `finding_2*` + `n_labels` (the 9 double-labelled frames), `dir_finding` (folder), `width`, `height`.
Do not apply: `timestamp_s` (fps unknown, so no seconds; keep `frame_index`), `seg_stem`, `parent_image_sample_id`, `mask_*`, `bbox_*`, `bboxes_json`, `has_mask`/`has_bbox` (False), `n_frames_total`, `fps`, `fps_effective`, `duration_s`, `codec`, `frames_*`, `description`, `bbps_*`, `organ_raw` (no Organ column; could be set to `capsule (whole GI)` or null), `dir_region`, `dir_category`, `label_*_mismatch`.
**New columns this dataset needs:** `dataset`, `modality` (`capsule-endoscopy`), `device`/`image_geometry` (octagonal FOV, 336x336), `site` / `region_derived` / `region_derived_source`, `split_group` (= video_id), `multi_label_group` (or just `finding_2`), `class_count_videos` (optional QA).

### 9d. What must be read / computed

* Directory listing + JPEG header (width/height) + size: 4.2 s for 47k files (done in scratch, no decoding).
* md5 for all frames: ~10 s (646 MB). Parse `<vid>_<frame>` with the regex above (instant).
* Derived zone: group by `video_id`, take min/max frame of Pylorus and Ileocecal valve - pandas, < 1 s.
* No pixel decoding needed for the table.

## 10. Pitfalls and open questions

1. **No split, no metadata**: video-wise split is the only leakage-safe option and several classes live in 1-3 videos; decide how to treat them (e.g. force them into train, or evaluate only classes with >= 4-5 videos).
2. **Domain gap** (capsule vs colonoscopy/gastroscopy): same slug (`polyps`, `ulcer`, `pylorus`, `reduced-view`) may mean different appearance; recommend a `modality` column and not pooling capsule classes blindly into colonoscopy classes. Kvasir-Capsule contains almost no colon.
3. 9 frames are in two folders (Erosion/Pylorus, Ampulla/Pylorus): a naive folder-based loader double-counts them and can leak the same bytes into train and test; also suggests the Pylorus label co-occurs with other findings.
4. Extreme class imbalance (72.7 % Normal; 3 classes < 60 frames) and near-duplicate consecutive frames (98.9 % are adjacent) - effective sample size is much smaller than 47k.
5. `region` of pathologies is unknown at source; the derived zone relies on landmark frames existing in the same video (24/43 videos have both).
6. Licence not in the folder (unverified: CC BY 4.0).
7. Should `Normal clean mucosa` become a new `normal` category (my proposal) or be mapped into `quality-of-mucosal-views` (clean view)? Needs a decision because HK has no normal class.
8. Region value for duodenum/small bowel: the brief lists `small-bowel` as a region; the existing merge calls everything above the ileocecal valve `upper-gi-tract`/`lower-gi-tract` only. Confirm convention (affects Ampulla of vater and all small-bowel derived zones).
