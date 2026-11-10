# kvasir-capsule (dataset `kvasir-capsule`)

Adapter `unify/adapters/kvasir_capsule.py`, vocabulary `unify/vocab/kvasir-capsule.csv`. Analysis: `docs/reports/kvasir-capsule.md`; schema review: `docs/reviews/reader1-schema-review.md`.

## Source
Kvasir-Capsule (Smedsrud et al., Scientific Data 8, 142, 2021): video capsule endoscopy (VCE) frames, 336 x 336 JPEG, white light. The folder is the *labelled-frames* part (43 source videos);
the public release has 117 videos (literature). **Licence: no file shipped -> `license = unknown`** (my recollection is CC BY 4.0 - unverified). The folder names no device and no README, so
`device` is left empty (the Olympus capsule of the paper is not stated in the data).

## Layout used
`kvasir-capsule/<class folder>/<video id>_<frame>.jpg`, 14 class folders, 47,238 files; the **only annotation is the folder name**. No CSV / JSON / README / boxes / splits ship.
File name `<16 hex>_<n>.jpg`: video id and frame number of the (non-shipped) source video. Rows: **47,229 `image`** (one per distinct frame; no other row type, no video_frame rows -
the frames are real files). `META["expected"] = {image: 47229}`.

## Label semantics
Single-class frame label from the folder (14 classes; counts in `docs/reports/kvasir-capsule.md` section 1). **9 frames are stored byte-identical in two class folders** (8 x Erosion + Pylorus:
`eb0203196e284797_1125/1126/1130/1131/1135/1136/1137`, `fb86bc87d3874cd7_3660`; 1 x Ampulla of vater + Pylorus: `eb0203196e284797_1157`). They become ONE row each: `finding` = primary label
(order: pathological > quality > normal > landmark, then alphabetical folder), `finding_2` = the other, `n_labels = 2`, `findings_all = erosion|pylorus`, `qa_flags = multi-label-duplicate-file`,
`file_path` / `dir_finding` = the primary folder, the other copy in `extra_json`.
Mapping (see the vocabulary CSV for the notes): Pylorus -> `pylorus` (= Hyper-Kvasir), Normal clean mucosa -> category `normal` / `normal-mucosa` (the class also means "clean view"),
Reduced mucosal view -> `quality-of-mucosal-views` / `reduced-view` (= Hyper-Kvasir upper-GI class), Polyp -> `polyps` (parent `polyps`; **55 frames from ONE video, small-bowel polyp seen by a capsule -
equal slug does not mean equal appearance, always combine with `procedure`**), Foreign body -> `pathological-findings` / `foreign-body` (**low confidence**: a lumen object, not a pathology),
Blood - fresh / hematin -> `blood-fresh` / `blood-hematin` (parent `bleeding`), Angiectasia / Erosion / Erythema / Lymphangiectasia / Ulcer -> same-named slugs.

## Location
* `procedure = capsule-whole-gi` (oesophagus -> stomach -> small bowel -> colon). **`region` is authoritative only for the 3 landmark classes**: Pylorus `upper-gi-tract` / `pylorus`;
  Ampulla of vater `upper-gi-tract` / `duodenum` (table convention: duodenum is upper GI; label confidence medium); Ileocecal valve `lower-gi-tract` / `ileocecal-valve` (terminal ileum / cecum
  border; medium). `location_source = class-name` for them.
* The other 11 classes: `region = unknown`, `site = unknown`, `location_source = unknown` - the source has no per-frame location (41,502 of 47,229 rows, 88 %). For a double-labelled
  frame region / site come from the landmark label (Erosion + Pylorus -> upper-gi-tract / pylorus; Ampulla + Pylorus -> primary label's site `duodenum`, the other in `extra_json.alt_site`).
* **`region_derived`** (heuristic, never used for `region`): from the order of frame numbers inside one video - the first / last Pylorus frame and Ileocecal-valve frame of the video mark the stomach /
  small-bowel / colon transitions (in all 24 videos that have both landmarks, pylorus precedes ileocecal). Null for the 5,727 landmark and double-labelled rows. Values over the 47,229 rows:
  `small-bowel` 23,327; `small-bowel-or-colon` 9,117 (only Pylorus exists in the video, frame after it); `stomach-or-small-bowel` 7,545 (only Ileocecal exists, frame before it); `stomach` 1,342
  (before the first Pylorus frame; includes oesophagus); `unknown` 127 (video without landmark); `colon` 44; null 5,727. Colon frames are practically absent in this dataset; assumes a single forward
  pass (capsule retrograde movement possible).

## Grouping and splits
`group_id = kvasir-capsule:<video_id>`, `video` / `exact` (all frames of one source video). Patient identity across the 43 videos is not shipped. Consecutive frames are near-duplicates
(98.9 % of in-class neighbours differ by one frame): **split by `group_id`, never by row**; class availability by video: Ampulla of vater 1, Blood - hematin 1, Polyp 1, Blood - fresh 2,
Erythema 3, Lymphangiectasia 3, Ulcer 3, Foreign body 4, Angiectasia 6, Reduced mucosal view 7, Erosion 9, Pylorus 32, Ileocecal valve 34, Normal clean mucosa 37 - rare classes can never be in train
and test at the same time under a video split. No official splits shipped (`split_official` empty).

## Technical facts
336 x 336 RGB baseline JPEG for all 47,238 files (6.8-31 KB), plain frames without text overlay, **octagonal field of view**: the four corners are black (5 % of the pixels are black in
>= 95 % of frames, corner legs ~54 px) plus a 1-pixel black frame. `frame_index` = frame number in the source video (not 0-based, 27 ... 89,099), `timestamp_s` is empty (fps unknown).

## Duplicates and overlap
md5 over all files: 47,229 distinct; the only repeats are the 9 double-labelled frames (collapsed into single rows). No other dataset in `data_to_merge/` contains a 336 x 336 image, so no byte-identical
overlap is possible; resized copies (e.g. in DataCrohnIPI 320 x 320 or see-ai 576 x 576) were not tested.

## extra_json keys
Only on the 9 double-labelled rows: `alt_paths` (list: the other folder copies of the frame), `alt_dir_finding` (list: their folder names), `alt_site` (only Ampulla + Pylorus: the site of the second landmark).

## Pitfalls
1. A folder-based loader double-counts the 9 frames and can put the same bytes into train and test.
2. 88 % of the rows have `region = unknown`: select capsule data with `procedure`, not with `region`; use `region_derived` knowingly (heuristic).
3. Extreme imbalance (Normal clean mucosa 72.7 %; Ampulla 10, Blood - hematin 12, Polyp 55 frames) and effective sample size far below 47 k (near-duplicate frames).
4. Large domain gap to colonoscopy / gastroscopy sets (colour, field of view, small-bowel anatomy); same slugs (`polyps`, `ulcer`, `pylorus`, `reduced-view`) are not visually equal across datasets.
5. `is_negative` is True only for `normal-mucosa`; null for landmarks and `reduced-view`, False for the pathology classes.

## Verification (done)
`python -m unify --only kvasir-capsule ...`: 47,229 rows; validation 113/113 PASS (also 114/114 together with etis-laribpolypdb); byte-identical across two runs; ~11 s with md5 (3.6 s adapter). Spot checks: 8 random rows against the raw files (size, md5, header size, id parsing); `region_derived`
recomputed for all 41,502 non-landmark rows by an independent script (0 mismatches); the 9 doubles listed above.
