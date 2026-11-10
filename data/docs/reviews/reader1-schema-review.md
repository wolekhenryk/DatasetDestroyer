# Reader 1 - review of `SCHEMA_DRAFT.md` (hyper-kvasir, kvasir-capsule, ETIS-LaribPolypDB)

Column numbers `#n` refer to the numbering in `SCHEMA_DRAFT.md` (#1-#68; the pixel/video and boxes/masks blocks are un-numbered there, I name them). Real values below come from the files / `merge/merged-labels.csv`; the few claims I re-checked with scripts are marked (verified).
Dataset folder names are used in paths exactly as on disk (`ETIS-LaribPolypDB/...`); `dataset` is the registry name (`etis-laribpolypdb`) - see 5.3.

## 0. Requested changes, ranked

| # | change | why |
|--:|---|---|
| 1 | **`#27 finding_in_image_vocab`**: do not redefine table-wide with key (region, category, finding_harmonized). Define it only for `video_frame` rows (null for image / mask rows) or keep "occurs among `image` rows of the same dataset", and add `procedure` to the key. | By construction it is True for every `image` and `segmentation_mask` row of every dataset (their own triple is an image-row triple), so for KC and ETIS it carries no information; it only has meaning for HK video rows. With `region = unknown` (11 KC classes) a table-wide key would also match across unrelated datasets. |
| 2 | **`#35 n_labels`**: say explicitly "number of filled label slots (old definition: 1, or 2 if `finding_2` and/or `category_2` is filled)" and "never the number of boxes/instances". | The old HK value is 2 for 63 clips (1,260 frame rows at k=20), 4 of them (80 frame rows) have only `Classification 2` and no `Finding 2`; `len(findings_all)` would give 1 for those 80 rows. ETIS image with 3 polyps must stay `n_labels = 1`. |
| 3 | **`#40 is_negative`**: make it tri-state (True normal/background, False pathological-findings, **null** for landmark / quality / therapeutic / artefact) or rename `is_explicit_normal`. | KC `Pylorus`, `Ileocecal valve`, HK `cecum`, `bbps-*` frames are polyp-free in practice but would be `is_negative=False` ("positive") under the draft rule; `Reduced mucosal view` may hide lesions. A consumer using `NOT is_negative` as "has lesion" gets it wrong. |
| 4 | **`#16 region_derived`**: allow 6 values, not 3: `stomach`, `small-bowel`, `colon`, `stomach-or-small-bowel`, `small-bowel-or-colon`, `unknown`; null on landmark rows. | With only 3 values 16,662 of 47,229 KC rows (35 %) cannot be placed (one landmark missing in their video). Counts in 1.2. |
| 5 | **Multi-label rows need a location rule** (KC double-labelled frames): region/site = taken from the first label that has an authoritative one (the landmark label); primary label = pathological > quality > landmark, then alphabetical. | Otherwise `region` of an Erosion+Pylorus frame is ambiguous (Erosion has none, Pylorus says upper). |
| 6 | **`label_source` / `file_path` root**: `video-metadata.csv` is outside `data_to_merge/` (project root). Decide where it lives (copy to `data_to_merge/_derived/` or write `../video-metadata.csv`). Add allowed value `dataset-constant` to `label_source` (ETIS has no label file). | adapter would otherwise emit a path that does not resolve for HK video rows. |
| 7 | **`has_bbox` / `annotation_types` / `bbox_source=mask-derived`**: define `annotation_types` = what the dataset *ships*; `has_bbox` = bbox columns are populated (any source). ETIS: `annotation_types=mask`, `has_bbox=True`, `bbox_source=mask-derived`; `mask_in_bbox_fraction`, `mask_json_bbox_max_diff_px` null unless `bbox_source=annotator`. | Without that, ETIS gets `has_bbox=True` but "no bbox annotation", and two QA columns that are trivially 1.0 / 0 look like validation. |
| 8 | **`#62-64` group columns**: add `group_kind = dataset` and `group_quality = coarse` (whole dataset is one unit, safe but not splittable) for ETIS; state what consumers must do with null `group_id` (HK stills). | see 2.5. |
| 9 | Provide **one ordered column list with exact count**; the draft's counts do not add up (see 5.1) and the "superset of the 76 columns, all kept" claim holds for content but not by name: of the 76 old columns 61 are identical, 1 is renamed (`source_dataset`), 10 change value mechanically (ids / paths / text) and 4 are redefined (`image_md5`, `finding_in_image_vocab`, `n_labels`, `bboxes_json`) - table 1.1.2. | adapters must emit an exact header. |
| 10 | Separator `\|` is used both inside `group_id` (`<dataset>\|<group>`) and as the multi-value separator (`findings_all`, `annotation_types`, `qa_flags`, `bbox_label`). Use `:` in `group_id`. | parsing ambiguity. |

## 1. Example rows

### 1.1 hyper-kvasir

#### 1.1.1 Rows (real data; "= image" means the same value as in the image column)

Image row `image:hyper-kvasir:0004a718-546c-41c2-9c69-c4685093a039` (one of the 1,000 with mask), video frame `frame:hyper-kvasir:11305ea5-389a-46c8-95f3-94a1af84247d:000181` (clip with second label), mask row `mask:hyper-kvasir:cju8c5223s8j80850b4kealt4` (the mask of that image).

| column (#) | image row | video_frame row | mask row |
|---|---|---|---|
| `sample_id` (#1) | `image:hyper-kvasir:0004a718-546c-41c2-9c69-c4685093a039` | `frame:hyper-kvasir:11305ea5-389a-46c8-95f3-94a1af84247d:000181` | `mask:hyper-kvasir:cju8c5223s8j80850b4kealt4` |
| `source_type` (#2) | image | video_frame | segmentation_mask |
| `dataset` (#3) | hyper-kvasir | hyper-kvasir | hyper-kvasir |
| `source_subset` (#4) | labeled-images | labeled-videos | segmented-images |
| `item_id` (#5) | 0004a718-546c-41c2-9c69-c4685093a039 | 11305ea5-389a-46c8-95f3-94a1af84247d | cju8c5223s8j80850b4kealt4 |
| `label_source` (#6) | `hyper-kvasir/labeled-images/image-labels.csv` | `hyper-kvasir/labeled-videos/video-labels.csv + ../video-metadata.csv` (see change 6) | `hyper-kvasir/labeled-images/image-labels.csv (inherited from the MD5-linked labelled image)` |
| `label_level` (#7) | image | clip | mask |
| `row_description` (#8) | same template as old, e.g. "Endoscopic still image (labeled-images) - Lower GI / pathological-findings / polyps; has a polyp segmentation mask and 1 bounding box(es)" | old template | old template |
| `license` (#9) | CC BY 4.0 | CC BY 4.0 | CC BY 4.0 |
| `annotation_types` (#10) | `class\|bbox\|mask` | `clip-class` | `class\|bbox\|mask` |
| `annotation_format` (#11) | `class=csv\|bbox=json-bbox\|mask=mask-jpeg` (proposal, see 5.2) | `csv` | same as image |
| `region` (#12) | lower-gi-tract | lower-gi-tract | lower-gi-tract |
| `organ_raw` (#13) | Lower GI | Lower GI | Lower GI |
| `site` (#14) | colon | colon | colon |
| `location_source` (#15) | label-column (region from `Organ`; site is class-implied - one column cannot say both, see 2.2) | label-column | label-column |
| `region_derived` (#16) | (null) | (null) | (null) |
| `procedure` (#17) | colonoscopy (from Organ = Lower GI) | colonoscopy | colonoscopy |
| `imaging` (#18) | white-light (dataset-level assumption, not verified per image; `dyed-*` classes -> chromoscopy) | chromoscopy (this clip's `description` = "chromoscopy") | white-light |
| `category` / `category_raw` (#19/#20) | pathological-findings / pathological-findings | pathological-findings / Pathological findings | pathological-findings / pathological-findings |
| `finding` / `finding_raw` (#21/#22) | polyps / polyps | polyps / polyps | polyps / polyps |
| `finding_harmonized` (#23) | polyps | polyps | polyps |
| `finding_parent` (#24) | polyps | polyps | polyps |
| `finding_subtype` (#25) | (null) | (null) | (null) |
| `finding_harmonization` (#26) | native | identity | native |
| `finding_in_image_vocab` (#27) | True | True | True |
| `findings_all` (#28) | polyps | `polyps\|retroflex-rectum` | polyps |
| `class_counts_json` (#29) | `{"polyps": 1}` | (null) | `{"polyps": 1}` |
| `finding_2`, `_harmonized`, `_raw` (#30-32) | - | retroflex-rectum / retroflex-rectum / retroflex rectum | - |
| `category_2`, `_raw` (#33-34) | - | anatomical-landmarks / Anatomical landmarks | - |
| `n_labels` (#35) | 1 | 2 | 1 |
| `description` (#36) | - | chromoscopy | - |
| `label_confidence` (#39) | high | high | high |
| `is_negative` (#40) | False | False | False |
| `dir_region/category/finding` (#41-43) | lower-gi-tract / pathological-findings / polyps | same | same |
| `label_*_mismatch` (#44-46) | False / False / False | False / False / False | False / False / False |
| `file_path` (#47) | `hyper-kvasir/labeled-images/lower-gi-tract/pathological-findings/polyps/0004a718-546c-41c2-9c69-c4685093a039.jpg` | `hyper-kvasir/labeled-videos/lower-gi-tract/pathological-findings/polyps/11305ea5-389a-46c8-95f3-94a1af84247d.avi` | `hyper-kvasir/segmented-images/masks/cju8c5223s8j80850b4kealt4.jpg` |
| `file_ext`, `file_exists`, `file_size_bytes` (#48-50) | jpg, True, 38790 | avi, True, 30918144 | jpg, True, 12497 |
| `image_path` (#51) | = file_path | (null) | the labelled image path |
| `segmented_image_path` (#52) | `hyper-kvasir/segmented-images/images/cju8c5223s8j80850b4kealt4.jpg` | (null) | same |
| `mask_path` (#53) | `hyper-kvasir/segmented-images/masks/cju8c5223s8j80850b4kealt4.jpg` | (null) | = file_path |
| `annotation_path` (#54) | (null) (boxes are in one shared JSON, not per item) | (null) | (null) |
| `image_md5` (#55) | 026c950a26ee2d224e472b41f91e006d (now for all 10,662 image rows) | (null) (a frame, not an image file) | 026c950a26ee2d224e472b41f91e006d (md5 of the *image*, as in the old table) |
| `video_id` / `frame_index` / `timestamp_s` (#56-58) | - | 11305ea5-... / 181 / 7.24 | - |
| `seg_stem` / `parent_image_sample_id` / `mask_sample_id` (#59-61) | cju8c5223s8j80850b4kealt4 / - / `mask:hyper-kvasir:cju8c5223s8j80850b4kealt4` | - | cju8c... / `image:hyper-kvasir:0004a718-...` / - |
| `group_id` / `group_kind` / `group_quality` (#62-64) | (null) / none / none | `hyper-kvasir:11305ea5-...` / video / exact | (null) / none / none |
| `split_official` (#65) | (null) | (null) | (null) |
| `dup_group_id` (#66) | (null) | (null) | (null) |
| `qa_flags`, `extra_json` (#67-68) | (null) | (null) | (null) |
| `width`, `height` (#69-70) | 619, 529 | 720, 576 | 619, 529 |
| video block | - | `n_frames_total` 661, `fps` 25.0, `fps_effective` 25.0, `duration_s` 26.44, `codec` vc1, `frames_suspect` False, `frame_rank` 5, `frames_sampled_in_video` 20, `frame_selection` `even-segment-midpoints k=20` | - |
| `has_mask` / `has_bbox` | True / True | False / False | True / True |
| `n_boxes`, `bbox_label` | 1, polyp | - | 1, polyp |
| `bboxes_json` | `[{"label":"polyp","finding":"polyps","xmin":262,"ymin":0,"xmax":454,"ymax":326}]` (new `finding` key) | - | same |
| `bbox_xmin/ymin/xmax/ymax` | 262 / 0 / 454 / 326 | - | same |
| `bbox_source`, `mask_format`, `mask_encoding` | annotator, jpeg, `gray>127 white=polyp` | - | same |
| `mask_foreground_pixels` / `_fraction` | 23336 / 0.071266 | - | same |
| `mask_tight_xmin/ymin/xmax/ymax` | 263 / 0 / 453 / 325 | - | same |
| `mask_in_bbox_fraction`, `mask_json_bbox_max_diff_px`, `mask_corner_pixel_removed` | 1.0, 1, False | - | same |
| `annotation_source` | `hyper-kvasir/segmented-images/bounding-boxes.json + hyper-kvasir/segmented-images/masks (linked to the labelled image by MD5)` | - | same |

#### 1.1.2 Old 76 columns -> new columns (fate of every old column)

* **Identical definition and values** (61 of 76): `source_type`, `label_level`, `item_id`, `video_id`, `frame_index`, `timestamp_s`, `seg_stem`, `file_ext`, `file_exists`, `file_size_bytes`, `region`, `organ_raw`, `category`, `category_raw`, `finding`, `finding_raw`, `finding_harmonized`, `finding_harmonization`, `finding_2`, `finding_2_harmonized`, `finding_2_raw`, `category_2`, `category_2_raw`, `description`, `bbps_score`, `bbps_range`, `dir_region`, `dir_category`, `dir_finding`, `label_category_mismatch`, `label_finding_mismatch`, `label_folder_mismatch`, `width`, `height`, the 10 video columns (`n_frames_total` ... `frame_selection`), `has_mask`, `has_bbox`, `n_boxes`, `bbox_label`, `bbox_xmin/ymin/xmax/ymax`, all `mask_*` columns (`mask_foreground_*`, `mask_tight_*`, `mask_in_bbox_fraction`, `mask_json_bbox_max_diff_px`, `mask_corner_pixel_removed`).
* **Renamed:** `source_dataset` -> `source_subset` (same strings: `labeled-images`, `labeled-videos`, `segmented-images`); new `dataset` = `hyper-kvasir`. The draft therefore is a superset only in content, not by column name.
* **Values change mechanically** (path root / id prefix): `sample_id`, `parent_image_sample_id`, `mask_sample_id` (insert `hyper-kvasir:`), `file_path`, `image_path`, `segmented_image_path`, `mask_path` (`out/` -> `hyper-kvasir/`), `label_source` (+ path root, + the video-metadata issue), `annotation_source` (text), `row_description` (only if the template quotes paths; it quotes `source_dataset`, which is unchanged).
* **Redefined, values can change:** `image_md5` (#55: now all 10,662 image rows instead of 2,000 rows), `finding_in_image_vocab` (#27: no HK value changes expected from my datasets - KC and ETIS add no triple that matches a currently-False HK triple - but the column becomes trivial elsewhere), `n_labels` (#35: 80 frame rows differ if `len(findings_all)` is used, see change 2), `bboxes_json` (new `finding` key inside each item -> text differs on 2,000 rows).
* **Mechanical reproducibility of ids (verified):** all 19,142 old `sample_id`s match `^(image|mask):[^:]+$` or `^frame:[^:]+:\d{6}$`; inserting `hyper-kvasir:` after the first colon gives 19,142 unique ids; the 1,000 `parent_image_sample_id` and 1,000 `mask_sample_id` values also match `^(image|mask):[^:]+$` and all resolve to an existing `sample_id` (so they get the same transformation). `image:<uuid>` -> `image:hyper-kvasir:<uuid>`, `mask:<cju>` -> `mask:hyper-kvasir:<cju>`, `frame:<vid>:<idx>` -> `frame:hyper-kvasir:<vid>:<idx>`: a pure string operation, so the old and new HK rows can be joined 1:1 and compared cell by cell, **excluding** the redefined columns above (`image_md5`, `bboxes_json`, `row_description` if the template changes, and `finding_in_image_vocab` / `n_labels` depending on the final definitions). I already ran the old notebook code against `data_to_merge/hyper-kvasir` (previous report): the only differences to the old CSV were the path prefix.

### 1.2 kvasir-capsule (47,229 `image` rows, no other row type)

Rows: a Pylorus frame (`131368cc17e44240_1141`, first Pylorus frame of that video; the video also has Ileocecal frames 30438-31698) and a double-labelled frame (`eb0203196e284797_1125`, same bytes in `Erosion/` and `Pylorus/`).

| column (#) | Pylorus frame | double-labelled frame (Erosion + Pylorus) |
|---|---|---|
| `sample_id` (#1) | `image:kvasir-capsule:131368cc17e44240_1141` | `image:kvasir-capsule:eb0203196e284797_1125` |
| `source_type`, `dataset`, `source_subset` | image, kvasir-capsule, (null) | same |
| `item_id` (#5) | 131368cc17e44240_1141 | eb0203196e284797_1125 |
| `label_source`, `label_level` | `folder-name`, image | same |
| `license` (#9) | unknown (published as CC BY 4.0 from my memory - unverified, no licence file in the folder) | same |
| `annotation_types`, `annotation_format` | class, folder-name | same |
| `region` (#12) | upper-gi-tract | upper-gi-tract (taken from the Pylorus label, change 5) |
| `organ_raw` (#13) | (null) | (null) |
| `site` (#14) | pylorus | pylorus |
| `location_source` (#15) | class-name | class-name |
| `region_derived` (#16) | (null) (landmark row) | (null) |
| `procedure`, `imaging` (#17-18) | capsule-whole-gi, white-light | same |
| `category` (#19) | anatomical-landmarks | pathological-findings |
| `category_raw` (#20) | (null) (no category text in the source) | (null) |
| `finding` / `finding_raw` (#21/22) | pylorus / `Pylorus` | erosion / `Erosion` |
| `finding_harmonized` (#23) | pylorus | erosion |
| `finding_parent` (#24) | pylorus | erosion |
| `finding_harmonization` (#26) | identity | identity |
| `finding_in_image_vocab` (#27) | True (trivial) | True (trivial) |
| `findings_all` (#28) | pylorus | `erosion\|pylorus` |
| `finding_2` / `_harmonized` / `_raw` (#30-32) | - | pylorus / pylorus / `Pylorus` |
| `category_2` (#33) | - | anatomical-landmarks (`category_2_raw` (null)) |
| `n_labels` (#35) | 1 | 2 |
| `label_confidence` (#39) | high | high |
| `is_negative` (#40) | (null) per change 3 (draft: False) | False |
| `dir_region`, `dir_category` (#41-42) | (null), (null) | (null), (null) |
| `dir_finding` (#43) | `Pylorus` | `Erosion` (folder of `file_path`) |
| `label_category_mismatch` / `label_finding_mismatch` / `label_folder_mismatch` (#44-46) | (null) / False / False | (null) / False / False |
| `file_path` (#47) | `kvasir-capsule/Pylorus/131368cc17e44240_1141.jpg` | `kvasir-capsule/Erosion/eb0203196e284797_1125.jpg` |
| `file_ext`, `file_exists`, `file_size_bytes` | jpg, True, 9685 | jpg, True, 11962 |
| `image_path` (#51) | = file_path | = file_path |
| `image_md5` (#55) | 44f88f2d6d4279368afb069215041d08 | 4a0ffd05e1a9656235494bc0ac083d71 |
| `video_id` / `frame_index` / `timestamp_s` | 131368cc17e44240 / 1141 / (null) (fps unknown) | eb0203196e284797 / 1125 / (null) |
| `group_id` / `group_kind` / `group_quality` | `kvasir-capsule:131368cc17e44240` / video / exact (video level; patient level unknown) | `kvasir-capsule:eb0203196e284797` / video / exact |
| `split_official`, `dup_group_id` | (null), (null) | (null), (null) (the 2 folder copies are collapsed into one row) |
| `qa_flags` (#67) | (null) | `multi-folder-label` (new flag) |
| `extra_json` (#68) | (null) | `{"alt_paths":["kvasir-capsule/Pylorus/eb0203196e284797_1125.jpg"],"alt_dir_finding":"Pylorus"}` |
| `width`, `height` | 336, 336 | 336, 336 |
| `has_mask`, `has_bbox` | False, False | False, False |

Other 8 doubles: 7 more Erosion+Pylorus (`eb0203196e284797_1126/1130/1131/1135/1136/1137`, `fb86bc87d3874cd7_3660`) and 1 Ampulla+Pylorus (`eb0203196e284797_1157`, size 10827, md5 2634a3d09ce35a93407f69546bf62a7d: `finding=ampulla-of-vater`, `finding_2=pylorus`, both landmark -> alphabetical primary, region upper-gi-tract, site `duodenum` from the primary label, alt site in `extra_json`).
A non-landmark single-label row would differ like this: e.g. an `Angiectasia` frame: `region=unknown`, `site=unknown`, `location_source=unknown`, `region_derived` = one of the 6 values, `category=pathological-findings`.

`region_derived` distribution over the 47,229 rows (rule: first / last Pylorus and Ileocecal frame of the same `video_id`; null for the 5,727 landmark and double-labelled rows):

| value | rows |
|---|--:|
| small-bowel | 23,327 |
| small-bowel-or-colon (only the Pylorus landmark exists in that video, frame after it) | 9,117 |
| stomach-or-small-bowel (only the Ileocecal landmark exists, frame before it) | 7,545 |
| stomach (before the first Pylorus frame; includes oesophagus) | 1,342 |
| unknown (video has neither landmark) | 127 |
| colon | 44 |
| (null) | 5,727 |

### 1.3 ETIS-LaribPolypDB (196 `image` + 196 `segmentation_mask` rows, or 196 image rows only - decision 7)

Real rows: image 43 (the scene with 3 polyps) and its mask row; image 20 added to show the duplicate flag.

| column (#) | image row `43` | mask row `43` |
|---|---|---|
| `sample_id` (#1) | `image:etis-laribpolypdb:43` | `mask:etis-laribpolypdb:43` |
| `source_type`, `dataset`, `source_subset` | image, etis-laribpolypdb, (null) | segmentation_mask, etis-laribpolypdb, (null) |
| `item_id` | 43 | 43 |
| `label_source` (#6) | `dataset-constant` (every image is polyp-positive; geometry from `ETIS-LaribPolypDB/masks/43.png`) | same |
| `label_level` | image | mask |
| `license` | unknown | unknown |
| `annotation_types` / `annotation_format` | mask / mask-png | mask / mask-png |
| `region` / `organ_raw` / `site` | lower-gi-tract / (null) / colon | same |
| `location_source` | dataset-constant | dataset-constant |
| `region_derived` | (null) | (null) |
| `procedure`, `imaging` | colonoscopy, white-light | same |
| `category`, `category_raw` | pathological-findings, (null) | same |
| `finding`, `finding_raw`, `finding_harmonized`, `finding_parent` | polyps, (null), polyps, polyps | same |
| `finding_harmonization` | identity | identity |
| `finding_in_image_vocab` | True (trivial) | True |
| `findings_all`, `class_counts_json` | polyps, `{"polyps": 3}` | same |
| `n_labels` | 1 | 1 |
| `label_confidence`, `is_negative` | high, False | high, False |
| `dir_*`, `label_*_mismatch`, `description`, `bbps_*`, `finding_2*` | (not applicable) | (not applicable) |
| `file_path` | `ETIS-LaribPolypDB/images/43.png` | `ETIS-LaribPolypDB/masks/43.png` |
| `file_ext`, `file_exists`, `file_size_bytes` | png, True, 1051311 | png, True, 3369 |
| `image_path` / `mask_path` | `ETIS-LaribPolypDB/images/43.png` / `ETIS-LaribPolypDB/masks/43.png` | same |
| `image_md5` | bcef0f59af599b4d0269dad3bb306b53 | same (md5 of the image, HK convention) |
| `mask_sample_id` / `parent_image_sample_id` | `mask:etis-laribpolypdb:43` / - | - / `image:etis-laribpolypdb:43` |
| `seg_stem` | (null) | (null) |
| `group_id` / `group_kind` / `group_quality` | `etis-laribpolypdb:all` / dataset / coarse (change 8) | same |
| `dup_group_id`, `qa_flags` | (null), (null) | same |
| `width`, `height` | 1225, 966 | 1225, 966 |
| `has_mask` / `has_bbox` | True / True | True / True |
| `n_boxes` | 3 (8-connected components) | 3 |
| `bboxes_json` | `[{"label":"polyp","finding":"polyps","xmin":102,"ymin":374,"xmax":271,"ymax":603},{"label":"polyp","finding":"polyps","xmin":302,"ymin":234,"xmax":481,"ymax":549},{"label":"polyp","finding":"polyps","xmin":1050,"ymin":464,"xmax":1091,"ymax":513}]` | same |
| `bbox_label` | polyp | polyp |
| `bbox_xmin/ymin/xmax/ymax` (union) | 102 / 234 / 1091 / 603 | same |
| `bbox_source`, `mask_format`, `mask_encoding` | mask-derived, png, `png-L value==255 white=polyp (values exactly {0,255})` | same |
| `mask_foreground_pixels` / `_fraction` | 75578 / 0.063868 | same |
| `mask_tight_xmin/ymin/xmax/ymax` | 102 / 234 / 1091 / 603 (== union box by construction) | same |
| `mask_in_bbox_fraction`, `mask_json_bbox_max_diff_px`, `mask_corner_pixel_removed` | (null), (null), (null) (no annotator box, lossless mask, nothing removed; checked: 0 of 196 masks have a foreground pixel at (0,0)) | same |
| `annotation_source` | `ETIS-LaribPolypDB/masks (8-connected components of the 0/255 PNG mask; boxes are derived, not shipped)` | same |
| `extra_json` | `{"component_pixels":[43695,30140,1743],"connectivity":8}` (optional) | same |

Image `20` (identical bytes to image `22`, md5 726d76dfc7198b89c74919b334a16e81; masks differ, IoU 0.796): same pattern with `dup_group_id=dup:726d76dfc719` (12 hex), `qa_flags=dup-label-conflict`, `extra_json={"dup_partner_ids":["22"],"mask_iou_with_partner":0.796}`, `n_boxes=1`, box 867/705/996/899, `mask_foreground_pixels` 18171. Same for (127,131) and (172,175): 6 image rows + 6 mask rows carry the flag.

## 2. Columns that cannot be filled correctly / would mislead / definition wrong for these datasets

### 2.1 Table-wide definitions
* **#27 `finding_in_image_vocab`** - see change 1. True for every image/mask row by construction; informative only for HK video rows. Keep the HK values unchanged by computing it with the same key on the same subset, or add `procedure` to the key.
* **#35 `n_labels`** - change 2.
* **#40 `is_negative`** - change 3. Also note R3: for datasets with only normal/pathology classes it is fine, but KC / HK have landmark and quality classes.
* **#55 `image_md5`**: text says "MD5 of the JPEG bytes" -> "of the image file bytes" (ETIS is PNG). On mask rows it must stay the md5 of the *parent image* (that is how the HK link works); state it. Cost: roughly 10-20 s over all HK + KC + ETIS images (HK 4 GB ~7 s, KC 0.65 GB, ETIS 0.2 GB).
* **#66 `dup_group_id`**: say it is computed over `image` rows only; `segmentation_mask` rows copy their parent's value. Otherwise HK's 1,000 image/mask pairs (same bytes) become 1,000 "duplicate groups". For KC the 9 doubles are collapsed into one row, so no `dup_group_id` there.
* **#26 `finding_harmonization`**: `native | identity | mapped` are not defined in the draft. Proposal: `identity` if `finding == finding_harmonized`, `mapped` otherwise; `native` only for HK image/mask rows (compat). KC examples: `mapped` for Polyp (`polyp` -> `polyps`), Normal clean mucosa (`normal-clean-mucosa` -> `normal-mucosa`), Reduced mucosal view (`reduced-mucosal-view` -> `reduced-view`); `identity` for Pylorus, Ulcer, Erosion, ...
* **#44-46 `label_*_mismatch`** (KC): the HK rule "`finding_harmonized` differs from the lower-cased folder" would give True for every KC class whose slug differs from the folder (`Blood - fresh`, `Polyp`, `Normal clean mucosa`, ...). For KC compare the *native* `finding` slug with `slugify(dir_finding)` -> always False (labels are the folders); `label_category_mismatch` = null (no category folder). The draft text (#41-46) only says "filled for KC `dir_finding`"; please specify.
* **#67 `qa_flags` `burned-in-text`**: cannot be set per row for HK (some images have text, a green ScopeGuide box or a black box; I only saw it in a sample), KC and ETIS have none. Do not emit it for HK; put the dataset-level remark in the registry / `extra_json` of the dataset description rather than on 10,662 rows.

### 2.2 Location columns (#12-18)
* **KC `region`**: authoritative for 3 landmark classes only (my decision 1 answer in section 4); 11 classes `unknown`. `#14 site` the same (`unknown` for them, never the derived value). `#15 location_source` for them = `unknown`; for landmarks `class-name`. `#16 region_derived`: see change 4 and the counts in 1.2. `#16` must not be filled for rows that have an authoritative region (landmarks / doubles).
* **KC region in a double-labelled row**: change 5.
* **`#15 location_source` is single-valued**, but for HK it is two different sources: region from the `Organ` column (`label-column`), site from the class name (`class-name`), and for ~25 of the 60 upper-GI clips the site could be read from the free-text description (`duodenum`, `stomach`, `esophagus`: e.g. ulcer / "Forrest IIa, duodenum", polyp / "polyp, stomach"). Proposal: `location_source` describes the *site* (finest value); `region` is always implied by region-level evidence; add the value `description` to the allowed list. Default for HK: fill `site` from the class table in my HK report (section 9b), `unknown` for upper-GI video classes without a keyword in `description`.
* **`#17 procedure` for KC** `capsule-whole-gi` is right (videos span stomach -> small bowel -> colon); do not use `capsule-small-bowel` there. ETIS `colonoscopy`. HK: `colonoscopy` for Organ = Lower GI, `gastroscopy` for Upper GI (the Upper GI clips include duodenum / ERCP, still gastroscopy-type).
* **`#18 imaging` for HK**: `white-light` is a dataset-level assumption (not verified per image; NBI frames cannot be excluded); `chromoscopy` for `dyed-*` classes and for clips whose `description` says chromoscopy / lugol. I would write the assumption into the registry, not claim it per row as verified.

### 2.3 Finding columns
* **`#20 category_raw`, `#22 finding_raw` (ETIS)**: no source text -> null (not "polyp"). `#21 finding` = `polyps` constant, `finding_harmonization = identity`.
* **`#24 finding_parent` for HK**: do **not** map the ungraded video class `colitis` to `ulcerative-colitis` (one clip's description is "pseudomembrane", i.e. not UC); keep parent = `colitis`. `ulcerative-colitis-grade-*` -> `ulcerative-colitis`, `esophagitis-a`/`esophagitis-b-d` and video `esophagitis` -> `esophagitis`, `barretts-short-segment` and `barretts` -> `barretts`.
* **`#25 finding_subtype` for HK**: UC grade `0-1 | 1 | 1-2 | 2 | 2-3 | 3` (grade slug stays in `finding_harmonized` too), esophagitis `la-a | la-b-d`. KC / ETIS: none.
* **`#29 class_counts_json`** also applies to HK mask images and ETIS (`{"polyps": n_boxes}`); the draft says "detection datasets".
* **`#28 findings_all` vs `#35 n_labels`** can legitimately differ (HK: 4 clips with `Classification 2` only).

### 2.4 Files / ids
* **#47 `file_path` case**: must be the real folder name (`ETIS-LaribPolypDB/...`, `EAD2020_train/...`) while `dataset` is the lower-case registry name. On macOS both resolve, on Linux not; see 5.3.
* **#6 / #54** `annotation_path` stays null for HK / KC / ETIS (boxes in one shared JSON or masks in a separate image row).
* **#58 `timestamp_s` (KC)**: (null) - fps unknown; `frame_index` is the frame number inside the original (non-shipped) video, not 0-based (min 27, max 89,099). Say so in #57.
* **#59 `seg_stem` (ETIS)**: null; the link is `mask_sample_id` / `parent_image_sample_id`.

### 2.5 Group columns (#62-64)
* **HK stills (10,662 `image` + 1,000 `segmentation_mask` rows):** no id exists (UUIDs random). `group_id=(null)`, `group_kind=none`, `group_quality=none`. **R6 must say what a consumer does with null**: each null row is *its own* group -> leaks (near-duplicate frames from the same examination); recommended wording: "rows with `group_quality=none` cannot be split leakage-safely; use `dup_group_id` only for byte-identical copies". HK clips: `group_id=hyper-kvasir:<video_id>`, kind `video`, quality `exact`. Possible cross-type leakage (a still and a clip of the same patient/lesion) is undetectable - add to the dataset-level caveats.
* **KC:** video id is exact at video level (`exact`), but patient identity across the 43 videos is unknown (not shipped); say so in `group_quality` docs.
* **ETIS: no sequence information is available.** Only partial: ids 1-6, 7-12, 13-18 look like consecutive views, but ids 19-24 interleave two scenes and thumbnail clustering gives no stable count (152 ... 49 clusters), so a block-proxy would be wrong. Therefore a single group (`etis-laribpolypdb:all`, `group_kind=dataset`, `group_quality=coarse`) - safe against leakage, not splittable. If you do not want a new kind: `group_id` null + `group_quality=none` is the fallback, but then the R6 "null = own group" interpretation would leak ETIS.

### 2.6 Mask / box columns (ETIS)
* `bbox_source = mask-derived`: fine, but (a) define the convention: **8-connected components of `value == 255`, one box per component, inclusive max, union box in `bbox_*`**; (b) ETIS boxes are not an annotation (see change 7); (c) for the 6 multi-polyp images the union box (e.g. 102,234,1091,603) is mostly background - consumers should use `bboxes_json`; (d) `mask_tight_*` equals `bbox_*` (fill both for parity or leave `mask_tight_*` null - I prefer fill, it is free); (e) `mask_in_bbox_fraction`, `mask_json_bbox_max_diff_px`, `mask_corner_pixel_removed` null (change 7); (f) touching polyps merge into one component, so `n_boxes` is a lower bound of polyps.
* `mask_encoding` strings: HK `gray>127 white=polyp` (JPEG, noisy), ETIS `png-L value==255 white=polyp`.
* `mask_format` (un-numbered in the draft) duplicates the information in `annotation_format` (`mask-jpeg`, `mask-png`); keep one.

## 3. Information without a column

| dataset | information | proposal |
|---|---|---|
| HK | per-clip `Classification 2` without `Finding 2` (4 clips) | existing `category_2`; fine |
| HK | UC grade, esophagitis LA grade | `finding_subtype` (draft has it) |
| HK | site for ~25 upper-GI clips from `description` | `site` + `location_source=description` (new allowed value) |
| HK | **12 clips whose CSV label disagrees with the folder**, 9 `frames_suspect` clips | already columns (`label_*_mismatch`, `frames_suspect`, `timestamp_note`) |
| HK | overlays on stills (text, green ScopeGuide box, black rectangle) | dataset-level only; `extra_json` key `overlay` is NOT worth 10,662 rows |
| HK | `extra_json` keys I would use | none (null on all rows) |
| KC | second folder of the 9 doubles | `extra_json.alt_paths`, `extra_json.alt_dir_finding`; flag `multi-folder-label` |
| KC | field of view: octagon, black corners 5 % of pixels + 1-px frame | dataset-level (registry); not per row |
| KC | landmark context used for `region_derived` | none per row; rule documented in the column definition |
| KC | device (Olympus capsule, literature only - unverified) | registry only |
| ETIS | per-component pixel counts, connectivity | `extra_json.component_pixels`, `extra_json.connectivity` (optional) |
| ETIS | duplicate partner + mask IoU for the 3 conflicting pairs | `dup_group_id` + `qa_flags=dup-label-conflict` + `extra_json.dup_partner_ids`, `extra_json.mask_iou_with_partner` |
| ETIS | black margins (ids 177-182: 66 rows top, 34 cols left; id 14: 15 cols) | `extra_json.black_margin_px` optional; or ignore |
| all | **field-of-view shape / black-corner fraction** (KC octagon, ETIS round, Crohn circular, HK octagon + overlay) | other datasets share it; deserves a dataset-level registry field (`fov_shape`) rather than a row column (pixel work per image otherwise) |

## 4. Opinions on the open decisions and rules

* **Decision 1 (KC regions): accept the draft default.** Pylorus `upper-gi-tract` / site `pylorus`; Ampulla `upper-gi-tract` / `duodenum`; Ileocecal valve `lower-gi-tract` / `ileocecal-valve`; 11 classes `unknown` + `region_derived`. This replaces my report's `small-bowel` shortcut (I accept dropping it: R5 consistency; only 94 % of the 24,713 locatable KC frames are small bowel; 1,342 are stomach, 44 colon). Consequences to document: (a) `region = small-bowel` will select see-ai and Crohn but almost no KC row; capsule data are selected by `procedure`; (b) `region` of the 3 landmark classes is exact but the other 11 classes are `unknown` -> 41,502 of 47,229 KC rows (88 %) have `region = unknown`, so `region`-based filters drop most of KC; (c) `ileocecal valve` is the border: lower per the draft's own #12 definition.
* **Decision 2 (see-ai / Crohn `small-bowel`)**: consistent with decision 1 as long as `procedure` distinguishes `capsule-small-bowel` from KC's `capsule-whole-gi`.
* **Decision 4 (`foreign-body` pathological)**: acceptable for KC with `label_confidence=medium`; it is not a pathology but a capsule-lumen object. Alternative `category=artefact`? In this table `artefact` means EAD2020 image artefacts, so no.
* **Decision 5 (capsule `Polyp` -> `polyps`)**: acceptable (55 frames from one video). Condition: document that equal `finding_harmonized` does not mean visually/clinically equal; `polyps` must always be combined with `procedure` when training a colonoscopy detector (KC polyps are small-bowel; ETIS/HK/PolypsSet are colon).
* **Decision 6**: no objection (KC `Angiectasia` = `angiectasia`). Suggest `finding_parent=bleeding` for KC `blood-fresh`, `blood-hematin` and see-ai `bleeding`; HK has no counterpart.
* **Decision 7 (mask rows):** parity (default) is acceptable because the filter `source_type` already exists and the old table is cell-comparable; but I would prefer **not** to emit mask rows for 1:1 sets (ETIS 196, CVC 612) because they carry no information beyond `mask_path` + `has_mask` on the image row and every naive loader double counts. If kept: put a sentence "iterate `image` / `video_frame` rows for training; `segmentation_mask` rows are annotation records" into the schema doc. Either way, do not change HK (needed for comparability).
* **Decision 8** (block proxy) - not my datasets; note that for ETIS I explicitly do **not** think a block proxy is valid (2.5).
* **R1** fine; add: "`has_mask` and `mask_path` are set on the `image` row, mask row exists only for HK" if decision 7 goes to folding. **R2** KC 47,229 rows with `finding_2`: correct (verified: 47,229 distinct md5, the 9 repeats are exactly the double-labelled frames; no duplicates inside any class). Primary-label rule as in change 5. **R3**: `normal` category for KC `Normal clean mucosa` agrees with my report (note the class means "normal and clean", it also encodes view quality). **R4** n/a. **R5** agree. **R6** agree + null-handling sentence (2.5). **R7** agree: `frame_selection = even-segment-midpoints k=20`, 7,480 frame rows (verified against `merge/merged-labels.csv`; 3,740 at k=10).

## 5. Problems in the draft (wrong, ambiguous, painful for adapters)

1. **Column counts / numbering**: "identity (9)" ok; "WHAT finding (24)" lists #19-#40 = 22; "files and links (15)" ok; "pixel size / video (14)" says `#69 width, #70 height; 71-82` but names only 10 further columns (71-80); "boxes and masks (23)" lists 22 names; the *named* columns add up to 102 (9+2+7+22+6+15+7+12+22), the block headers add up to 107, and the draft says "~107". The boxes/masks block has no numbers. Provide a final ordered list; I will write adapters against that header.
2. **`annotation_format` (#11)**: a row can have several encodings (HK image with mask: csv + json-bbox + mask-jpeg). Define as `|`-separated tagged list `class=csv|bbox=json-bbox|mask=mask-jpeg`, aligned with `annotation_types`. `mask_format` is redundant (2.6).
3. **Dataset naming**: `dataset` registry names are lower-case (`etis-laribpolypdb`, `ead2020-train`, `polypgen-ninja`) but folder names are `ETIS-LaribPolypDB`, `EAD2020_train`, `CVC-ClinicDB`. `file_path` must keep the folder case; `sample_id` uses the registry name. Say so; otherwise adapters will guess. Also: `dup:<md5 prefix>` needs a fixed length (I used 12 hex).
4. **`label_source`** relative-path rule fails for `video-metadata.csv` (change 6); `annotation_source` for HK hard-codes text with `out/`.
5. **R1** says boxes never get their own rows - consistent with my ETIS proposal (boxes in `bboxes_json`, derived).
6. **`#57 frame_index`** documented as "0-based" for video rows; for KC it is the source-video frame number (not 0-based, video not shipped).
7. **`#10 annotation_types`** semantics (shipped vs derived) undefined - change 7.
8. **`#39 label_confidence`**: say it is the confidence of the native class -> unified label mapping (per class, not per image), values from the dataset report tables; HK image/mask rows `high`; KC Ileocecal valve `medium` for region, `high` for class (one value only: choose `medium` if either is uncertain) - alternatively split `label_confidence` into two.
9. **`finding_parent` default** "defaults to `finding_harmonized`": for HK video-only `colitis` and image `ulcerative-colitis-grade-*` the parent differs (2.3); please state that the default is applied only when no coarser class exists in the whole table.
10. **Painful for adapters**: (a) 14 old columns change value or semantics (1.1.2) - an adapter cannot just prefix paths; (b) `image_md5` for all rows adds an I/O pass (HK 4 GB, 7 s); (c) `class_counts_json` and `findings_all` need a vocabulary map at hand when the adapter runs (fine, it exists); (d) group rules for HK need `video_id` only (cheap).

## 6. Open questions for the coordinator
1. Where should `video-metadata.csv` live relative to `data_to_merge/` (or is `../video-metadata.csv` acceptable)?
2. Accept `group_kind=dataset` / `group_quality=coarse` for ETIS (and HK stills `none`)? Or is ETIS meant to be a fixed held-out test set (then `split_official=test` would be a coordinator-assigned value, not shipped)?
3. Mask rows: fold or keep (decision 7), at least for ETIS / CVC?
4. KC `Normal clean mucosa`: `category=normal`, `is_negative=True` is fine for you? (It also means "clean view".)
5. `region_derived` vocabulary: 6 values (my proposal) or only 3 plus `unknown`?
6. KC licence: unverified; keep `unknown` until someone checks the source page?
