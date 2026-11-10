# Column dictionary of `merged-labels.csv`

Generated from `unify/schema.py` (single source of truth) - do not edit by hand: regenerate with `cd data_to_merge && ../.venv/bin/python -m unify.schema` (prepend this header).
Column order = table order. Empty cell = not applicable. Dtypes are pandas nullable dtypes (`string`, `Int64`, `Float64`, `boolean`).

#### identity

| # | column | dtype | description |
|--:|---|---|---|
| 1 | `sample_id` | string | Globally unique, stable, human-readable key: `image:<dataset>:<item_id>`, `mask:<dataset>:<item_id>`, `frame:<dataset>:<video_id>:<frame_index:06d>`. |
| 2 | `source_type` | string | Exactly one of `image`, `video_frame`, `segmentation_mask`. Never null. |
| 3 | `dataset` | string | Registry name of the dataset (= adapter name), e.g. `hyper-kvasir`, `cvc-clinicdb`. Never null. |
| 4 | `source_subset` | string | Origin partition inside the dataset (`labeled-images`, `videos80`, `nbi_adenoma`, `bbox_images`...). NOT the shipped split (that is `split_official`). Nullable. |
| 5 | `item_id` | string | Id of the underlying item, unique within (dataset, source_type): uuid, file stem, or the file path below the dataset folder without extension when stems repeat (PolypsSet). |
| 6 | `label_source` | string | File(s) (relative to `data_to_merge/`) or rule (`folder-name`) the labels were read from. |
| 7 | `label_level` | string | `image` (label of one still), `clip` (frame inherits its video's label), `mask` (mask row, labels inherited from the linked image). |
| 8 | `row_description` | string | Verbose human-readable sentence describing the row (self-explanatory when exported alone). |
| 9 | `license` | string | Licence / usage terms of the dataset (from the adapter META); `unknown` if none is shipped. |

#### WHAT is annotated

| # | column | dtype | description |
|--:|---|---|---|
| 10 | `annotation_types` | string | `|`-separated subset of `class`, `clip-class`, `bbox`, `mask`: the annotation kinds the dataset PROVIDES for this row. `bbox`/`mask` are listed also when the annotator drew nothing (then `n_boxes` = 0 / `has_mask` False = annotated-empty); a missing geometry (positive frame without mask) is NOT listed and `n_boxes` is null. |
| 11 | `annotation_format` | string | Source encoding of the annotation: `folder-name`, `csv`, `yolo-txt`, `voc-xml`, `supervisely-bitmap-json`, `mask-png`, `mask-jpeg`, `mask-multipage-tif`... |

#### WHERE (anatomy / procedure)

| # | column | dtype | description |
|--:|---|---|---|
| 12 | `region` | string | `lower-gi-tract` | `upper-gi-tract` | `small-bowel` | `unknown`. Authoritative only - never guessed (heuristics go to `region_derived`). |
| 13 | `organ_raw` | string | Original organ text if the dataset has one (`Lower GI`), else null. |
| 14 | `site` | string | Finer anatomical site: colon, cecum, rectum, terminal-ileum, ileocecal-valve, stomach, pylorus, oesophagus, z-line, duodenum, small-bowel, unknown... |
| 15 | `location_source` | string | How region/site is known: dataset-constant, folder, label-column, class-name, readme, unknown. |
| 16 | `region_derived` | string | Optional heuristic zone (Kvasir-Capsule only): stomach | small-bowel | colon | stomach-or-small-bowel | small-bowel-or-colon | unknown, from the order of pylorus / ileocecal-valve frames inside the video. Nullable; never used for `region`. |
| 17 | `procedure` | string | colonoscopy | gastroscopy | capsule-small-bowel | capsule-whole-gi | mixed | unknown. |
| 18 | `imaging` | string | white-light | nbi | chromoscopy | mixed | unknown. Use `unknown` for a single frame of an unrecorded type rather than `mixed`. |
| 19 | `device` | string | Endoscope / capsule model if the dataset says so (`PillCam SB3`, `Olympus EC-S10`), else null. |

#### WHAT finding

| # | column | dtype | description |
|--:|---|---|---|
| 20 | `category` | string | anatomical-landmarks, pathological-findings, quality-of-mucosal-views, therapeutic-interventions, normal, background, artefact. Never null. |
| 21 | `category_raw` | string | Original category / classification text if the dataset has one. |
| 22 | `finding` | string | Kebab-case slug of the original finding text (for multi-class rows: the primary class = most boxes, ties by lowest class id). |
| 23 | `finding_raw` | string | Original finding text, whitespace-stripped (native class name). |
| 24 | `finding_harmonized` | string | Canonical lesion-type slug to train/evaluate on across sources; equals `finding` unless an explicit vocabulary rewrite applies. |
| 25 | `finding_parent` | string | Coarse pooling key (`ulcerative-colitis` for the graded UC classes, `polyps` for `polyp-like-lesion`...). Defaults to `finding_harmonized`. |
| 26 | `finding_subtype` | string | Histology / grade / size class of the finding (`adenomatous`, `grade-2-3`, `la-a`, `3-10mm`, `gt-10mm`). Nullable. |
| 27 | `finding_harmonization` | string | `native` (label already canonical), `identity` (slug used as is), `mapped` (rewritten by an explicit rule), `derived` (label synthesised by the adapter, e.g. `no-polyp-annotated` for a frame without box). |
| 28 | `finding_in_image_vocab` | boolean | `video_frame` rows only (null elsewhere): True if (region, category, finding_harmonized) of the clip also occurs among the `image` rows of the table, i.e. a still-image class with this meaning exists. |
| 29 | `findings_all` | string | `|`-separated sorted distinct `finding_harmonized` of ALL labels of the row (multi-label images, 2nd video label). Equals `finding_harmonized` for single-label rows. |
| 30 | `class_counts_json` | string | Detection datasets: compact JSON `{finding_harmonized: n_boxes}` for the row, else null. |
| 31 | `finding_2` | string | Slug of the second label slot (second video label / second folder of a double-labelled frame). Nullable. |
| 32 | `finding_2_harmonized` | string | `finding_2` after the explicit vocabulary map. |
| 33 | `finding_2_raw` | string | Original second finding text, stripped. |
| 34 | `category_2` | string | Slug of the second classification. |
| 35 | `category_2_raw` | string | Original second classification text, stripped. |
| 36 | `n_labels` | Int64 | Number of label slots filled: 1; 2 when a second label slot (`finding_2` and/or `category_2`) is filled. For multi-class detection rows: the number of distinct classes (`len(findings_all)`). Never counts boxes or instances. |
| 37 | `description` | string | Free-text description of the finding (Hyper-Kvasir videos). Commas occur inside values - never split. |
| 38 | `bbps_score` | Int64 | Boston Bowel Preparation Scale score 0-3 parsed from the description (Hyper-Kvasir BBPS video frames only). |
| 39 | `bbps_range` | string | `0-1` or `2-3` for BBPS rows. |
| 40 | `label_confidence` | string | high | medium | low: confidence of the native class -> unified label mapping (from the vocabulary CSV). |
| 41 | `is_negative` | boolean | Pathology polarity: True for `normal` / `background` (no pathology annotated), False for `pathological-findings`, null for classes that are not about pathology (landmarks, mucosal-view quality, therapeutic interventions, artefacts). |

#### folder provenance

| # | column | dtype | description |
|--:|---|---|---|
| 42 | `dir_region` | string | Region folder the source file really sits in (Hyper-Kvasir). |
| 43 | `dir_category` | string | Category folder as on disk (Hyper-Kvasir). |
| 44 | `dir_finding` | string | Finding / class folder as on disk (Hyper-Kvasir, Kvasir-Capsule). |
| 45 | `label_category_mismatch` | boolean | CSV category differs from the on-disk category folder. |
| 46 | `label_finding_mismatch` | boolean | `finding_harmonized` differs from the lower-cased on-disk finding folder. |
| 47 | `label_folder_mismatch` | boolean | Any of region/category/finding disagrees between CSV label and folder. |

#### files and links

| # | column | dtype | description |
|--:|---|---|---|
| 48 | `file_path` | string | POSIX path relative to `data_to_merge/` of the asset the row is about (image, mask, or the .avi of a frame row). Never null. |
| 49 | `file_ext` | string | Lower-case extension without dot (`jpg`, `png`, `avi`, `tif`). |
| 50 | `file_exists` | boolean | `file_path` verified as an existing file. Never null. |
| 51 | `file_size_bytes` | Int64 | Size of `file_path` in bytes. |
| 52 | `image_path` | string | Path of the image (image + mask rows). For image rows equals `file_path`. |
| 53 | `segmented_image_path` | string | Hyper-Kvasir: path of the renamed byte-identical copy in `segmented-images/images/`. |
| 54 | `mask_path` | string | Path of the mask file (images with a standalone mask file + mask rows). |
| 55 | `annotation_path` | string | Per-item annotation file (xml / json / txt) when the labels are not in a table or folder name. |
| 56 | `image_md5` | string | MD5 of the image bytes (all image rows; cached). Basis for `dup_group_id` and the Hyper-Kvasir segmentation link. |
| 57 | `video_id` | string | Id of the source video / sequence / case when the dataset gives one (Hyper-Kvasir clips; frame images of Kvasir-Capsule, PolypsSet cases, EAD sequences). |
| 58 | `frame_index` | Int64 | Video frame rows: 0-based frame number inside the .avi (frames are addressed, not extracted). Extracted-frame images: the source-defined frame number where the dataset gives one. |
| 59 | `timestamp_s` | Float64 | frame_index / fps_effective in seconds (video_frame rows only). |
| 60 | `seg_stem` | string | Name stem of the segmentation entry (Hyper-Kvasir `cju...`; other datasets: the mask stem). |
| 61 | `parent_image_sample_id` | string | Mask rows: sample_id of the linked image row. |
| 62 | `mask_sample_id` | string | Image rows with a standalone mask file: sample_id of the linked mask row. |

#### split safety and QA

| # | column | dtype | description |
|--:|---|---|---|
| 63 | `centre` | string | Acquisition centre / hospital code if the dataset records it (PolypGen `C1`..`C6`), else null. Enables leave-one-centre-out. |
| 64 | `group_id` | string | Leakage-safe grouping key `<dataset>:<group>`; split by it, never by row. Videos known to be duplicated are merged into one group. Null if no grouping exists. |
| 65 | `group_kind` | string | video | sequence | case | centre | block-proxy | dataset (the whole dataset is one group, e.g. ETIS) | none. |
| 66 | `group_quality` | string | exact (all frames of one video / sequence / case share the id) | proxy (heuristic blocks, may still leak) | coarse (group = whole dataset: safe but cannot be split further) | none (no id: rows cannot be split leak-safely - hold out whole datasets or accept leakage). Never patient-level unless stated in docs/datasets/<dataset>.md. |
| 67 | `split_official` | string | Split shipped with the dataset (`train`, `val`, `test`, `fold-1`..`fold-5`), else null. |
| 68 | `dup_group_id` | string | `dup:<md5 prefix>` for image rows sharing identical bytes (whole table); null if unique. |
| 69 | `qa_flags` | string | `|`-separated flags: annotation-missing, dup-label-conflict, split-leak-known, burned-in-text, non-gi-possible, label-folder-mismatch, frames-suspect, ... |
| 70 | `extra_json` | string | Compact JSON with dataset-specific extras (documented per dataset in docs/datasets/<dataset>.md). |

#### pixel size / video

| # | column | dtype | description |
|--:|---|---|---|
| 71 | `width` | Int64 | Pixel width of the addressed asset (image, mask or video frame). Never null. |
| 72 | `height` | Int64 | Pixel height of the addressed asset. Never null. |
| 73 | `n_frames_total` | Int64 | Frames in the video (video_frame rows). |
| 74 | `fps` | Float64 | Frame rate as stored in the video metadata. |
| 75 | `fps_effective` | Float64 | Frame rate used for `timestamp_s`. |
| 76 | `duration_s` | Float64 | Clip duration in seconds from the video metadata. |
| 77 | `codec` | string | Video codec. |
| 78 | `frames_suspect` | boolean | True for videos whose frame count disagrees with duration*fps by more than 2 frames. |
| 79 | `timestamp_note` | string | Why a suspect clip's frame count / duration / timestamps need care. |
| 80 | `frame_rank` | Int64 | 0-based rank of the frame among the sampled frames of its video. |
| 81 | `frames_sampled_in_video` | Int64 | How many frames of this video are present as rows. |
| 82 | `frame_selection` | string | Sampling rule, e.g. `even-segment-midpoints k=20`. |

#### boxes and masks

| # | column | dtype | description |
|--:|---|---|---|
| 83 | `has_mask` | boolean | A segmentation mask exists for this row's image (standalone file or embedded). Never null. |
| 84 | `has_bbox` | boolean | At least one bounding box exists (annotated or derived). Never null. |
| 85 | `n_boxes` | Int64 | Number of boxes (0 for annotated negatives, null when the dataset has no box/mask annotation). |
| 86 | `bboxes_json` | string | Compact JSON list `[{"label","finding","xmin","ymin","xmax","ymax"},...]`: pixels, top-left origin, corner format, xmax/ymax INCLUSIVE. |
| 87 | `bbox_label` | string | Distinct box labels, `|`-separated (Hyper-Kvasir/CVC/ETIS: `polyp`). |
| 88 | `bbox_xmin` | Int64 | Union of all boxes (a convenience; for multi-class rows use `bboxes_json`): min xmin. |
| 89 | `bbox_ymin` | Int64 | Union of all boxes: min ymin. |
| 90 | `bbox_xmax` | Int64 | Union of all boxes: max xmax (inclusive). |
| 91 | `bbox_ymax` | Int64 | Union of all boxes: max ymax (inclusive). |
| 92 | `bbox_source` | string | annotator (drawn by the dataset authors; the source encoding is in `annotation_format`) | mask-derived (computed from the mask: 8-connected components). |
| 93 | `mask_format` | string | File / storage format of the mask (`jpeg-rgb`, `png-gray`, `png-rgb`, `tif-multipage-class-pages`, `supervisely-bitmap-in-json`). |
| 94 | `mask_encoding` | string | How to binarise the mask, e.g. `gray>127 white=polyp`, `value==1`, `tif-page>127 (last row ignored)`. |
| 95 | `mask_foreground_pixels` | Int64 | Foreground pixels after binarisation (and noise removal). |
| 96 | `mask_foreground_fraction` | Float64 | mask_foreground_pixels / (width*height), 6 decimals. |
| 97 | `mask_tight_xmin` | Int64 | Tight bounding box of the mask foreground, min column. |
| 98 | `mask_tight_ymin` | Int64 | Tight bounding box of the mask foreground, min row. |
| 99 | `mask_tight_xmax` | Int64 | Tight bounding box, max column (inclusive). |
| 100 | `mask_tight_ymax` | Int64 | Tight bounding box, max row (inclusive). |
| 101 | `mask_in_bbox_fraction` | Float64 | QA: share of mask foreground lying inside the annotated boxes (xmax/ymax inclusive). EAD2020: each mask page is paired with the boxes of its own class. |
| 102 | `mask_json_bbox_max_diff_px` | Int64 | QA: largest coordinate difference between the tight mask box and the union of the annotated boxes. |
| 103 | `mask_noise_pixels_removed` | Int64 | Foreground pixels dropped as noise before the mask statistics (Hyper-Kvasir: the isolated JPEG pixel at (0,0) = 1; CVC-ClinicDB: components < 10 px; EAD2020: the sentinel last row of 255s; clean masks: 0). |
| 104 | `annotation_source` | string | Where the mask / box annotations come from (file or rule). |

