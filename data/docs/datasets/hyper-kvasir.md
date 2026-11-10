# hyper-kvasir (dataset `hyper-kvasir`)

Adapter `unify/adapters/hyper_kvasir.py`, vocabulary `unify/vocab/hyper-kvasir.csv`, old-vs-new check `unify/tools/compare_hyper_kvasir_old_new.py`.
Analysis: `docs/reports/hyper-kvasir.md`; review of the schema: `docs/reviews/reader1-schema-review.md`.

## Source
Hyper-Kvasir (Borgli et al., Scientific Data 7, 283, 2020), white-light GI endoscopy from Baerum Hospital (Norway; literature, not stated in the folder), plus chromoscopy
(dyed classes). **Licence CC BY 4.0** (`out/license.txt` and the original `data/hk.zip`; the file is not inside `hyper-kvasir/`).
`data_to_merge/hyper-kvasir` is a byte-exact copy of the labelled part of `data/hk.zip` (path / size / CRC32 identical). The 99,417 `unlabeled-images` are **not**
part of this folder and not ingested. No device is named in the data (`device` empty).

## Layout used
| path | content | rows produced |
|---|---|--:|
| `labeled-images/image-labels.csv` + `<region>/<classification>/<finding>/<uuid>.jpg` | 10,662 stills, 23 classes | 10,662 `image` |
| `labeled-videos/video-labels.csv` + `<tract>/<category>/<finding>/<uuid>.avi` | 374 labelled clips (30 GB), clip-level labels | 374 x `FRAMES_PER_VIDEO` `video_frame` (default 20 -> **7,480**) |
| `segmented-images/{images,masks}/<cju...>.jpg` + `bounding-boxes.json` | 1,000 polyp images with box + mask (renamed byte-identical copies of labelled polyp images) | 1,000 `segmentation_mask` + mask / box columns on the 1,000 linked `image` rows |
| `unify/data/hyper-kvasir-video-metadata.csv` | ffprobe table (fps, frames, size, codec; snapshot of the project-root `video-metadata.csv`) | joined 1:1 to the clips |

`META["expected"] = {image: 10662, video_frame: 7480, segmentation_mask: 1000}` (total **19,142**; with `--param FRAMES_PER_VIDEO=10` the build gives 15,402 rows, = the
number in `merge/MERGE_PROCESS.md`, but validation then fails on the expected count by design). `FRAME_STRIDE=1` would give 875,940 frame rows.

## Label semantics
* **Still images**: one class per image (Organ, Classification, Finding). Graded classes: `ulcerative-colitis-grade-*` (`finding_subtype` = `grade-0-1` ... `grade-3`, `finding_parent` = `ulcerative-colitis`),
  `esophagitis-a` / `esophagitis-b-d` (`finding_subtype` `la-a` / `la-b-d`, parent `esophagitis`), `barretts-short-segment` (subtype `short-segment`, parent `barretts`).
* **Video frames** are *addressed*, not extracted: `file_path` is the `.avi`, `frame_index` the 0-based frame, `frame_selection` = `even-segment-midpoints k=20` (midpoints of k equal segments;
  never the first / last frame). Read them by sequential decoding (the VC-1/AVI files have very sparse key frames). Labels are clip-level and inherited by every frame; a clip has up to
  two label slots (`finding` / `finding_2`, free `description`); 63 clips have a second slot (`n_labels` = 2, 40 with both finding and category, 19 finding only, 4 category only).
* **Segmentation**: `segmentation_mask` rows (`label_level = mask`) are the mask files; the linked `image` row carries the same mask / box columns (`has_mask`, `mask_path`, `mask_sample_id`).
  Mask = JPEG RGB, binarised `gray > 127`, white = polyp; the isolated JPEG-noise pixel at (0,0) is removed (`mask_noise_pixels_removed` = 1; 143 masks). Boxes = `bounding-boxes.json`
  (`bbox_source = annotator`, `annotation_format = csv|json-bbox|mask-jpeg`), 1,071 boxes on 1,000 images (1 box: 945 images ... 10 boxes: 1), all of class `polyp` (`finding` `polyps`).
  The link image <-> segmentation is the **MD5 of the JPEG bytes** (names are unrelated): size pre-filter then md5 (cached), 1:1 for all 1,000.
* `bbps_range` for BBPS images / clips, `bbps_score` 0-3 parsed from descriptions that read exactly `BBPS n` (57 clips = 1,140 frame rows).

## Location (how it is known)
`region` comes from the CSV column `Organ` (Lower GI / Upper GI; equals the tract folder for all 11,036 labelled items) -> `location_source = label-column` where `site` is only `colon` / `unknown`,
`class-name` where the class implies a specific site (cecum, terminal-ileum, rectum, anorectum, pylorus, stomach, z-line, oesophagus, duodenum for ERCP). Upper-GI video classes whose site depends
on the free-text description (`cancer`, `polyps`, `ulcer`, `varices`, `optimal-view`, `reduced-view`) have `site = unknown` (for ~25 of the 60 upper clips the description names duodenum / stomach /
oesophagus - not parsed). `procedure` = colonoscopy (lower) / gastroscopy (upper). `imaging` = `chromoscopy` for `dyed-lifted-polyps` / `dyed-resection-margins`, `white-light` for everything else
(dataset-level assumption, not verified per image; NBI frames cannot be excluded).

## Findings (rows by category; counts per class are in the vocabulary notes and `docs/reports/hyper-kvasir.md` 9b)
| category | image | video_frame | segmentation_mask |
|---|--:|--:|--:|
| anatomical-landmarks | 4,104 | 280 | - |
| pathological-findings | 2,642 | 2,920 | 1,000 |
| quality-of-mucosal-views | 1,925 | 1,360 | - |
| therapeutic-interventions | 1,991 | 2,920 | - |

Video slugs rewritten to the dataset's own folder / image names (vocabulary column `finding_harmonized`, `finding_harmonization = mapped`): `barretts-oesophagus` -> `barretts`, `gave` ->
`gastric-antral-vascular-ectasia`, `cancer-colorectal` -> `colorectal-cancer`, `cavity-of-anastomotic-leak` -> `anastomotic-leakage`, `self-expanding-stent` -> `self-expanding-stents`;
second labels: `dyed-resction-margin` / `dyed-resection-margin` -> `dyed-resection-margins` (vocabulary rows `finding_2|<slug>`). Deliberately **not** mapped: `esophagitis`, `colitis`
(`finding_parent` stays `colitis`: one clip is pseudomembranous colitis), `polyps` in the upper GI, `anastomosis`.
`finding_in_image_vocab` (video rows only): 265 clips / 11 findings have a still-image class with the same (region, category, finding_harmonized), 109 clips / 19 findings do not.
No negatives / normal class (the only "normal" is the free second video label `normal mucosa`); every still carries a class.

## Grouping and splits
* `video_frame`: `group_id = hyper-kvasir:<video_id>`, `video` / `exact` - split by it (frames of a clip are near-duplicates).
* **Stills and mask rows: no group id exists** (UUIDs are random; images come from consecutive frames of the same examinations) -> `group_kind = none`, `group_quality = none`; a random split of the
  stills leaks near-duplicates. Possible stills <-> clips overlap of the same patient is undetectable. No official splits shipped (`split_official` empty).
* `qa_flags`: `frames-suspect` (9 clips = 180 frame rows), `label-folder-mismatch` (12 clips = 240 frame rows; CSV label and folder disagree: 7 `anastomosis` rows labelled Pathological sitting
  in `therapeutic-interventions/anastomosis`, 4 therapeutic rows in `pathological-findings/polyps`, 1 `clip placement` in `dyed-resection-margins`); both views are kept (`category` vs `dir_category`).

## Technical facts
* Stills: RGB baseline JPEG, 751 distinct sizes (332-1920 x 352-1079). Videos: vc1 (369), rawvideo (3), mpeg1video (2); 875,940 frames; 720x576 / 1280x1024 / 1920x1072 / 768x576 / 576x576.
* 9 `frames_suspect` clips: the AVI header values are wrong (`timestamp_note` explains each), the frame count is exact; the two `mpeg1video` clips declare 50 fps but are 25 fps (`fps_effective` = 25);
  two `rawvideo` clips have a variable frame rate (timestamps approximate); `478400dc-...` is truncated to 336 frames.
* **Boxes clipped:** the JSON max edges equal the image width / height for 40 / 88 boxes (a box touching the border). The table uses the inclusive convention, so these edges are clipped to `W-1` / `H-1`
  (116 edges on 113 images; `bbox_xmax` differs from the old table on 76 rows, `bbox_ymax` on 174 rows, nothing else). The mask is binarised after JPEG decoding; `mask_json_bbox_max_diff_px` compares the
  tight mask box with the clipped annotator box (JSON boxes are looser than the mask by 1-2 px, by > 10 px for 19 masks).
* Overlays in the stills (not flagged per row, only visible in a sample): burnt-in text (ID / name / date lines, bitrate), a green ScopeGuide box or a black rectangle bottom-left, black corner cuts.
  Consider cropping / masking them (shortcut risk).

## Duplicates
No byte-identical stills inside the labelled set, none between labelled and unlabeled images (size + CRC32 from the zip). The 1,000 `segmentation_mask` rows duplicate the pictures of 1,000 `image` rows
(not new images; `source_type` filter!). Not tested against other datasets of `data_to_merge/` except ETIS (24x24 thumbnail correlation, nothing >= 0.95).

## extra_json
Not used (null on all rows).

## Pitfalls
1. Count images with `source_type == image` only; mask rows duplicate 1,000 pictures.
2. The old table's `finding_in_image_vocab` was True on all image / mask rows; the unified column exists on `video_frame` rows only.
3. `image_md5` is now filled for every image row (+ mask rows = md5 of the parent image).
4. `bbox_xmax` / `bbox_ymax` of border-touching boxes are 1 px smaller than in the old table (inclusive convention).
5. Frame rows are addresses into the `.avi`, not files; do not time-seek.
6. `site` is class-level only; do not read `unknown` as "not GI".

## Verification (done)
`python -m unify --only hyper-kvasir` -> 19,142 rows, 112/113 validation checks pass with the stock validator - the only failure is `no NA-like strings in text columns`, which flags the legal value `none` of `group_kind` / `group_quality` on the 11,662 rows without group (HK stills + masks); with `none` removed from the validator's NA-like list (local wrapper) 113/113 pass -,
output byte-identical across two runs, 3 s. `unify.tools.compare_hyper_kvasir_old_new`: row sets equal (19,142 = 19,142), 75 column mappings identical (incl. mechanical / redefined ones),
2 differ as documented (`bbox_xmax`, `bbox_ymax`), 0 unexpected. Spot checks: 6 images, 6 video frames (ffprobe codec / size), 6 masks (md5 of the segmented copy, mask statistics, noise pixel) against the raw files;
overlay of 6 images with box + mask outline viewed.
