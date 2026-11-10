# hyper-kvasir (data_to_merge/hyper-kvasir) - reader report

Reader 1 of 3. Everything below was verified by running scripts (scratchpad `.../scratchpad/hyper-kvasir/`, python `-I`). Nothing under `data_to_merge/`, `out/`, `data/`, `merge/` was modified.
Scope rule from the coordinator: do not repeat `merge/MERGE_PROCESS.md`; this report verifies it, adds what is new, and gives the adapter recipe and the label -> unified mapping.

## 0. Short answers to the questions asked

| question | answer (evidence in the sections below) |
|---|---|
| Is `data_to_merge/hyper-kvasir` a duplicate of `out/`? | **`out/` no longer contains the labelled data.** `out/` now holds only `license.txt` and `unlabeled-images/` (99,417 JPEG, 28 GB). `labeled-images/`, `labeled-videos/`, `segmented-images/` are gone from `out/` and exist only in `data_to_merge/hyper-kvasir/` (same disk volume, folder mtime 22 Oct; the folders look *moved*, not copied). So there is no second copy to diff; I verified the folder instead against the **original archive `data/hk.zip`** (CRC32) and against **`merge/merged-labels.csv`** (paths, sizes, md5) - it is the byte-exact Hyper-Kvasir labelled part (sect. 8). |
| Label files inside it? | **Yes, all three are inside**: `labeled-images/image-labels.csv`, `labeled-videos/video-labels.csv`, `segmented-images/bounding-boxes.json`. Only `video-metadata.csv` is outside (project root, unchanged, git-tracked). `license.txt` is not inside (only in `out/` and in the zip). |
| What differs vs the old `out/` layout? | Only the root: `out/<x>` became `data_to_merge/hyper-kvasir/<x>`. Relative layout, names, sizes, bytes identical. Unlabeled images were *not* brought over (not needed). |
| Can the existing merge be reused as adapter? | **Yes, with 2 functional line changes** (project-root detection marker, `OUT_DIR`) + cosmetic strings. I ran the notebook's code (copy in the scratchpad, output to the scratchpad): all 74 validation checks pass and the result equals `merge/merged-labels.csv` cell for cell once the path prefix is normalised (sect. 9d). |
| Exact row counts | image **10,662**, segmentation_mask **1,000**, video_frame **374 x min(k, n_frames)** = **3,740 (k=10)** / **7,480 (k=20, current notebook default)** / 875,940 (stride 1). Totals **15,402 / 19,142 / 887,602**. |

**Documentation drift found:** `MERGE_PROCESS.md` says 15,402 rows and 10 frames/video, but the notebook (saved 3 Nov 20:17, after the .md at 20:08) has `FRAMES_PER_VIDEO = 20` and the committed-to-disk `merge/merged-labels.csv` has **19,142 rows** (video_frame 7,480; `frame_selection = even-segment-midpoints k=20` on every frame row). Everything else in the .md matches.

## 1. Identity

* **Hyper-Kvasir** (Borgli et al., Sci Data 2020; origin Baerum Hospital, Norway - from the literature, not stated anywhere in the folder) - white-light GI endoscopy (colonoscopy + gastroscopy) incl. some chromoscopy (dyed classes, Lugol staining mentioned in a video description). Only the *labelled* part is in this folder. Licence: CC BY 4.0 (text in `out/license.txt`, identical copy inside `hk.zip`; not shipped in this folder - **copy the licence file or cite it**). No README shipped.
* Size 34 GB (32.54 GB videos, 3.99 GB JPEG, 1.07 MB labels).
* Files (13,039 + 5 `.DS_Store`): 12,662 `.jpg` (10,662 labelled + 1,000 segmented images + 1,000 masks), 374 `.avi`, 2 `.csv`, 1 `.json`.

```
hyper-kvasir/
  labeled-images/            image-labels.csv (10,662 rows)
     lower-gi-tract/  <classification>/<finding>/<uuid>.jpg      7,210 jpg
     upper-gi-tract/  <classification>/<finding>/<uuid>.jpg      3,452 jpg
  labeled-videos/            video-labels.csv (374 rows)
     lower-gi-tract/  <category>/<finding>/<uuid>.avi            314 avi
     upper-gi-tract/  <category>/<finding>/<uuid>.avi             60 avi
  segmented-images/          bounding-boxes.json (1,000 entries)
     images/<cju...>.jpg  1,000      masks/<cju...>.jpg  1,000
```
Relative layout 1:1 identical to what `MERGE_PROCESS.md` describes for `out/`.

## 2. Annotation sources (re-verified)

| file | format | rows | notes |
|---|---|--:|---|
| `labeled-images/image-labels.csv` | comma, UTF-8, **no BOM, CRLF, no trailing newline**; 888,054 bytes | 10,662 | cols `Video file` (=image UUID, misnomer), `Organ` (Lower GI 7,210 / Upper GI 3,452), `Finding`, `Classification`. No empties; labels already slugs. md5 identical to `data/hyper-kvasir/image-labels.csv`. |
| `labeled-videos/video-labels.csv` | same dialect; 37,107 bytes | 374 | cols `Video file`, `Organ` (Lower 314 / Upper 60), `Finding 1`, `Classification 1`, `Detailed description of finding`, `Finding 2`, `Classification 2`. Quirks as in MERGE_PROCESS 3.1 (trailing blanks, case variants, typos, commas inside values). |
| `segmented-images/bounding-boxes.json` | JSON object keyed by `cju...` stem: `{height,width,bbox:[{label,xmin,ymin,xmax,ymax}]}` | 1,000 entries / 1,071 boxes (only label `polyp`) | integer pixels, top-left origin, corner format, max coordinates behave as **inclusive** (MERGE_PROCESS 5.6). |
| `video-metadata.csv` (project root, outside the folder) | `id,tract,category,folder,duration_s,size_mb,fps,frames,width,height,codec` | 374 | still 1:1 with the videos on disk; `size_mb` equals the real file size for 374/374; ffprobe on 6 clips (4 random + the truncated `478400dc` + mpeg1 `05a868ca`) agrees with the file (header `nb_frames` is wrong exactly for the known suspects). |

## 3. What each annotation is

* **image-level class label**: one (Organ, Classification, Finding) per labelled JPEG; 23 classes. Graded classes: `ulcerative-colitis-grade-*` (Mayo-like 0-1 ... 3), `esophagitis-a`, `esophagitis-b-d`.
* **video clip-level label**: up to two label pairs per clip, free-text description; no frame/time-interval labels.
* **segmentation**: binary semantic mask (JPEG, RGB with equal channels, not strictly 0/255, **white = polyp**, foreground fraction re-measured: min 0.47 %, median 11.4 %, max 81.2 %; threshold `> 127`) + bounding boxes (corner xyxy, inclusive max) for 1,000 polyp images; 1,071 boxes; classes: only `polyp`; masks are semantic (several boxes can share one mask).

## 4. Location (anatomy)

Per class, from the `Organ` column (Lower GI / Upper GI) and the class name; the folder name `lower-gi-tract` / `upper-gi-tract` repeats it. There is **no finer per-file site** column; the site in the mapping table (9b) is inferred from the class name (and, for videos, the free-text description, e.g. `duodenum`, `stomach`, `esophagus`).

## 5. Findings (counts)

See the mapping table 9b (images / masks / clips / frame rows per class). Normal-only images do not exist as a class (the only "normal" notion is the video `Finding 2` text `normal mucosa`, 16 clips); there are **no negative images in the sense of "no finding"** - every image carries a class. Instrument/artefact classes: none (quality classes `bbps-*`, `impacted-stool`, `reduced-view` are mucosal-view quality, `clip-placement`, `snare-resection`, `ercp` etc. are therapeutic).

## 6. Linking keys, grouping, splits

* image <-> label: file stem = `Video file` (10,662/10,662 matched, path = labels verbatim; 0 orphans either way - re-confirmed by the adapter run).
* video <-> label <-> metadata: UUID stem.
* segmentation <-> labelled image: **MD5 of the JPEG bytes** (names unrelated). Re-checked: all 1,000 `segmented-images/images` have exactly one labelled twin, md5 values equal the `image_md5` column of `merge/merged-labels.csv` for 2,000/2,000 files (1,000 seg + 1,000 labelled twins); 1,000 distinct mask md5.
* Grouping ids for leakage-safe splits: **video_id** for clips (and frames). **For still images there is no patient / procedure / sequence id** (UUIDs are random) - Hyper-Kvasir images come from many consecutive frames of the same examinations, so near-duplicates across a random split are likely and cannot be prevented from the metadata. Official train/val/test splits: **none shipped** in this folder.

## 7. Technical facts (re-verified)

* Labelled images: all RGB baseline JPEG, **751 distinct sizes**, width 332-1920, height 352-1079 (most common 633x532 n=1,311, 633x531 n=1,272, 1349x1071 n=838, 1221x1012 n=788). Segmentation images/masks 332-1920 x 352-1072; mask size == image size == JSON size.
* Videos: 374 `.avi`, codec vc1 (369) / rawvideo (3) / mpeg1video (2); 875,940 frames; fps 25/30/20/50 (metadata fps wrong for the 2 mpeg1 clips); 720x576, 1280x1024, 1920x1072, 768x576, 576x576; 9 clips with suspect header values (MERGE_PROCESS 5.5). No decoding errors found in the clips I probed.
* Visual overlays/borders (looked at 8 random stills + 1 mask pair): black octagonal corner masks; many lower-GI images carry a **burnt-in text block** (patient ID / name / sex / date-of-birth lines, time stamps, bitrate text) and a **green ScopeGuide position box (bottom-left)** or a plain black rectangle in the same place (in the 8-image sample 5/8 had text, 4/8 had the box: 3 green, 1 black). These are dataset artefacts a model can learn to shortcut on (the box position correlates with colonoscopy and sometimes with class); consider cropping or masking. Not quantified over all 10,662 images (would need pixel decoding).
* No corrupt or unreadable file found (CRC32 of all 12,665 non-video files equals the zip's; header read of all 12,662 JPEG succeeded).

## 8. Duplicates and overlap (what was actually tested)

* **vs original archive `data/hk.zip`** (59 GB, 112,535 entries, central directory read; CRC32 compared): paths 13,039 = 13,039 both directions (0 only-local, 0 only-zip); **size equal for 13,039/13,039**; **CRC32 equal for 12,665/12,665** non-video files and for 8 videos (5 smallest + 3 random); the other 366 videos are verified by size only (as instructed - no hashing of 30 GB). Conclusion: byte-exact copy of the zip's labelled part.
* **vs `merge/merged-labels.csv`** (built from `out/`): all 12,036 unique `file_path` values exist after replacing `out/` -> `data_to_merge/hyper-kvasir/`, `file_size_bytes` equal for 12,036/12,036, `image_path`/`segmented_image_path`/`mask_path` all exist, md5 of 1,000 segmented images + 1,000 labelled twins == stored `image_md5`; md5 of a random 500 labelled JPEGs: 500 distinct.
* **inside the labelled set:** by (size, CRC32) from the zip index: 0 duplicate groups in `labeled-images`; segmented images = a subset of labelled images (1,000/1,000 match, 0 match any unlabeled image).
* **labelled vs unlabeled** (never tested before; `MERGE_PROCESS.md` lists it as untested): by (size, CRC32) from the zip index there is **no content overlap** between the 11,662 distinct labelled+segmented JPEGs and the 99,417 unlabeled JPEGs, and no duplicates inside the unlabeled set. (Byte-identical test only; re-encoded copies not tested.)
* **vs other datasets in `data_to_merge/`:** ETIS-LaribPolypDB (196 images) vs the 7,210 labelled lower-GI HK images by 24x24 grey correlation: max 0.936, nothing above 0.95 (true near-duplicates reach >= 0.98) -> no overlap found. HK vs CVC-ClinicDB / PolypGen / PolypsSet was **not** tested by me (other readers). Kvasir-SEG is not in `data_to_merge/`, so HK-segmented vs Kvasir-SEG could not be tested; the HK segmentation set *is* the same 1,000 images Kvasir-SEG is known to be built from (literature, unverified here) - keep one copy if Kvasir-SEG is ever added.

## 9. Proposed mapping to the unified table

### 9a. Row units

Unchanged: `image` 10,662, `segmentation_mask` 1,000, `video_frame` 374 x k. Keep the 1,000 mask rows as explicit duplicates of 1,000 image rows (as now). Counts: see section 0.

### 9b. Native class -> unified label

`region` / `category` / `finding_harmonized` exactly as in the existing merge (these are what the notebook already produces; verified by the adapter run). Counts: I = labelled images, M = mask rows, C = clips, F = frame rows at k=20. "site" is **new** information (not in the 76 columns), inferred from class name/description.

| native (Organ / Classification / Finding) | I | M | C | F (k=20) | region | site | category | finding slug (`finding_harmonized`) | confidence |
|---|--:|--:|--:|--:|---|---|---|---|---|
| Lower / anatomical / cecum | 1,009 | - | 4 | 80 | lower-gi-tract | cecum | anatomical-landmarks | cecum | high |
| Lower / anatomical / ileum | 9 | - | - | - | lower-gi-tract | terminal ileum | anatomical-landmarks | ileum | high |
| Lower / anatomical / retroflex-rectum | 391 | - | - | - | lower-gi-tract | rectum (retroflexed) | anatomical-landmarks | retroflex-rectum | high |
| Lower / pathological / polyps | 1,028 | 1,000 | 69 | 1,380 | lower-gi-tract | colon | pathological-findings | polyps | high |
| Lower / pathological / hemorrhoids | 6 | - | 1 | 20 | lower-gi-tract | anorectum | pathological-findings | hemorrhoids | high |
| Lower / pathological / ulcerative-colitis-grade-0-1, -1, -1-2, -2, -2-3, -3 | 35, 201, 11, 443, 28, 133 (851) | - | - | - | lower-gi-tract | colon | pathological-findings | ulcerative-colitis-grade-* (keep 6 strings; **add severity column**: 0-1 / 1 / 1-2 / 2 / 2-3 / 3) | high |
| Lower / pathological / colitis (video only) | - | - | 15 | 300 | lower-gi-tract | colon | pathological-findings | colitis (grade unknown; do not merge with the graded image classes) | medium |
| Lower / pathological / anastomosis (video; CSV says Pathological, folder says therapeutic) | - | - | 7 | 140 | lower-gi-tract | colon (surgical anastomosis) | pathological-findings (as per CSV) | anastomosis | medium |
| Lower / pathological / anastomotic-leakage, colorectal-cancer, parasites, stenosis (video only) | - | - | 3, 3, 4, 1 | 60, 60, 80, 20 | lower-gi-tract | colon | pathological-findings | anastomotic-leakage, colorectal-cancer, parasites, stenosis | high / high / high / medium |
| Lower / quality / bbps-0-1 | 646 | - | 34 | 680 | lower-gi-tract | colon | quality-of-mucosal-views | bbps-0-1 (+`bbps_score` 0-3 where known) | high |
| Lower / quality / bbps-2-3 | 1,148 | - | 31 | 620 | lower-gi-tract | colon | quality-of-mucosal-views | bbps-2-3 | high |
| Lower / quality / impacted-stool | 131 | - | - | - | lower-gi-tract | colon | quality-of-mucosal-views | impacted-stool | high |
| Lower / therapeutic / dyed-lifted-polyps | 1,002 | - | 94 | 1,880 | lower-gi-tract | colon | therapeutic-interventions | dyed-lifted-polyps | high |
| Lower / therapeutic / dyed-resection-margins | 989 | - | 19 | 380 | lower-gi-tract | colon | therapeutic-interventions | dyed-resection-margins | high |
| Lower / therapeutic / clip-placement, snare-resection, self-expanding-stent(s) (video only) | - | - | 6, 13, 10 | 120, 260, 200 | lower-gi-tract | colon | therapeutic-interventions | clip-placement, snare-resection, self-expanding-stents | high |
| Upper / anatomical / pylorus | 999 | - | 5 | 100 | upper-gi-tract | stomach (pylorus) | anatomical-landmarks | pylorus | high |
| Upper / anatomical / retroflex-stomach | 764 | - | 2 | 40 | upper-gi-tract | stomach (fundus/cardia) | anatomical-landmarks | retroflex-stomach | high |
| Upper / anatomical / z-line | 932 | - | 3 | 60 | upper-gi-tract | oesophagogastric junction | anatomical-landmarks | z-line | high |
| Upper / pathological / barretts (+ video "barrett's oesophagus") | 41 | - | 3 | 60 | upper-gi-tract | distal oesophagus | pathological-findings | barretts | high |
| Upper / pathological / barretts-short-segment | 53 | - | - | - | upper-gi-tract | distal oesophagus | pathological-findings | barretts-short-segment | high |
| Upper / pathological / esophagitis-a, esophagitis-b-d | 403, 260 | - | - | - | upper-gi-tract | oesophagus | pathological-findings | esophagitis-a, esophagitis-b-d (add severity: LA A / LA B-D) | high |
| Upper / pathological / esophagitis (video) | - | - | 3 | 60 | upper-gi-tract | oesophagus | pathological-findings | esophagitis (ungraded) | medium |
| Upper / pathological / cancer, GAVE, gastric banding perforated, polyps, ulcer, varices (video only) | - | - | 4, 4, 2, 8, 17, 2 | 80, 80, 40, 160, 340, 40 | upper-gi-tract | varies: free-text says oesophagus / stomach / duodenum (see description) | pathological-findings | cancer, gastric-antral-vascular-ectasia, gastric-banding-perforated, polyps, ulcer, varices | high (class) / low (site) |
| Upper / quality / optimal-view, reduced-view (video only) | - | - | 1, 2 | 20, 40 | upper-gi-tract | stomach/duodenum | quality-of-mucosal-views | optimal-view, reduced-view | high |
| Upper / therapeutic / ercp (video only) | - | - | 4 | 80 | upper-gi-tract | duodenum (papilla) | therapeutic-interventions | ercp | high |
| **total** | **10,662** | **1,000** | **374** | **7,480** | | | | | |

Cross-dataset reminders for the coordinator: the existing slugs `polyps`, `pylorus`, `ulcer`, `reduced-view`, `cecum`, `ileum` collide in meaning with other datasets (e.g. Kvasir-Capsule `Polyp`, `Pylorus`, `Ulcer`, `Reduced mucosal view`) - so `finding_harmonized` alone is not enough to tell the colonoscopy `polyps` from a capsule small-bowel polyp; keep `region` / `site` / `modality` in the key (see kvasir-capsule report).

### 9c. Columns

* All 76 existing columns apply unchanged for this dataset (the adapter produces exactly them).
* Suggested additions (needed anyway for the multi-dataset table): `dataset` (= `hyper-kvasir`; today `source_dataset` holds the sub-folder `labeled-images` etc., so a second column is needed), `modality` (white-light; chromoscopy for `dyed-*`), `site` (anatomical site, section 9b), `severity` (ulcerative-colitis grade 0-3 incl. half steps, esophagitis A / B-D, BBPS score), `patient_id` / `split_group` (null for images, `video_id` for clips), `split` (null - none shipped), `annotation_format` (`class` / `mask+bbox` / `clip-class`).
* Paths: store relative to the **`data_to_merge/` root** (e.g. `hyper-kvasir/labeled-images/...`) instead of the project root, so one `DATA_ROOT` serves all datasets. The current column `file_path` would otherwise start with `data_to_merge/hyper-kvasir/` (what the adapter run produced).

### 9d. Adapter recipe (verified)

Changes to `merge/merge_labels.ipynb`:

1. **Functional** - first code cell, `detect_project_root`: it looks for `out/labeled-images/image-labels.csv` and `out/labeled-videos/video-labels.csv`; **these no longer exist** (the notebook as saved would raise `FileNotFoundError` today). Change the marker to `data_to_merge/hyper-kvasir/labeled-images/image-labels.csv` (+ video file), or set `PROJECT_ROOT_OVERRIDE`.
2. **Functional** - `OUT_DIR = PROJECT_ROOT / "out"` -> `PROJECT_ROOT / "data_to_merge" / "hyper-kvasir"` (all of `IMG_DIR`, `VID_DIR`, `SEG_DIR`, the CSV and JSON paths derive from it). `VID_META_CSV` stays `PROJECT_ROOT / "video-metadata.csv"` (file is outside the dataset folder; keep it, `video_meta.py` regenerates it).
3. Cosmetic: the hard-coded `SEG_ANNOTATION_SOURCE = "out/segmented-images/..."` string and the `out/` mentions in `SCHEMA_SPEC` descriptions (the CSV column `annotation_source` would still say `out/...`; `file_path`, `image_path`, `segmented_image_path`, `mask_path`, `label_source` follow the new root automatically via `rel()`).
4. If the original `merged-labels.csv` must not be overwritten, change `OUTPUT_CSV` (and drop `OUTPUT_CSV.relative_to(PROJECT_ROOT)` prints if the output goes outside the project).

Evidence: the notebook code with exactly changes 1-2 (+ output redirected to the scratchpad) ran to completion, `ALL 74 CHECKS PASSED`, output 19,142 x 76; compared with the existing `merge/merged-labels.csv` (all cells as strings): same columns/order, same per-type counts (10,662 / 7,480 / 1,000) and **0 differing columns** after replacing the prefix `data_to_merge/hyper-kvasir/` by `out/` in `file_path`, `image_path`, `segmented_image_path`, `mask_path`, `label_source` (`annotation_source` is the unchanged hard-coded string). Also run with `FRAMES_PER_VIDEO = 10`: 74/74 checks pass, **15,402 rows** (= the number in `MERGE_PROCESS.md`). Runtime 3.2 s (warm cache).

### 9e. What must be read / computed

Nothing new beyond the existing notebook: JPEG headers of 12,662 files (seconds), `stat` of 12,036 files, md5 of 2,000 files (seconds), mask decoding of 1,000 masks (a few seconds). The ffprobe work (frames/fps) is already in `video-metadata.csv` (do not hash the 30 GB of videos).

## 10. Pitfalls and open questions

1. **`out/` is empty of labelled data now** - the old notebook cannot be re-run unchanged; do not assume `out/labeled-*` exists (`.gitignore` ignores `out/`, so git cannot restore it). Two parallel copies of the labelled data are *not* present - only `data_to_merge/hyper-kvasir` and the original `data/hk.zip` (59 GB, still there; safe backup).
2. `MERGE_PROCESS.md` (15,402 rows, k=10) vs real `merged-labels.csv` (19,142 rows, k=20): update the document or re-run with the desired `FRAMES_PER_VIDEO`; the coordinator must decide k (3,740 vs 7,480 frame rows, or stride) - frames of one clip are near-duplicates, always split by `video_id`.
3. No patient/procedure id for stills -> random splits leak; no official split shipped. Offer: split by class-stratified groups that approximate sessions? Not possible from metadata - flag as known limitation.
4. 1,000 `segmentation_mask` rows duplicate 1,000 `image` rows; every counting query must filter on `source_type`.
5. Burnt-in overlays (text, green ScopeGuide box, black rectangle) are shortcuts; decide whether to crop/mask before training.
6. Class vocabularies overlap in name but not always in meaning across datasets (see 9b note); `ulcerative-colitis-grade-*` and `esophagitis-*` are graded in images but not in videos.
7. Licence file not inside the folder (CC BY 4.0 from `out/license.txt`).
8. FYI for the CVC-ClinicDB reader: while scanning headers with Pillow 13, all 612 `CVC-ClinicDB/TIF/Original/*.tif` failed to open (header read), the PNG copies and the TIF ground-truth files read fine.
