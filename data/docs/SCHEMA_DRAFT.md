> **SUPERSEDED** - this is the first draft that the readers reviewed (`docs/reviews/`). The final schema is `unify/schema.py` / `docs/SCHEMA.md`; the changes made after the reviews are listed in `MERGE_PROCESS.md` section 2. Kept as a record of the consolidation process.

# Unified label table - DRAFT schema (for reader review)

Status: draft by the coordinator, built from the 8 reader reports in `reports/` (ETIS-LaribPolypDB pending). Purpose: ONE CSV over all datasets in `data_to_merge/`, used to train a model.
It is a **superset of the 76 columns of `merge/merged-labels.csv`** (all kept, a few generalised) plus ~31 new ones. Dataset-specific oddities go into `extra_json`, so adding a dataset never changes the column list.

The three things the user asked to be explicit on, and where they live:

| question | columns |
|---|---|
| **WHAT is this annotation / row?** (label, mask, bbox, clip label...) | `source_type`, `label_level`, `annotation_types`, `annotation_format`, `has_mask`, `has_bbox`, `mask_*`, `bbox_*` |
| **WHERE in the body?** (colon, stomach, small bowel...) | `region`, `site`, `location_source`, `region_derived`, `procedure`, `imaging`, `organ_raw` |
| **WHAT finding?** (polyp, normal mucosa, ulcer...) | `category`, `finding`, `finding_harmonized`, `finding_parent`, `finding_subtype`, `findings_all`, `is_negative` |

## Columns (target ~107)

`NEW` = not in the 76-column Hyper-Kvasir table; `GEN` = existing column with a generalised definition.

### identity (9)
1. `sample_id` GEN - globally unique: `image:<dataset>:<item_id>`, `mask:<dataset>:<item_id>`, `frame:<dataset>:<video_id>:<frame_index:06d>` (old ids had no dataset part; bare stems collide across datasets).
2. `source_type` - `image` | `video_frame` | `segmentation_mask` (unchanged; no new row types - boxes live inside the image row).
3. `dataset` NEW - registry name = adapter name (`hyper-kvasir`, `kvasir-capsule`, `etis-laribpolypdb`, `polypsset`, `polypgen-ninja`, `cvc-clinicdb`, `see-ai`, `ead2020-train`, `datacrohnipi`).
4. `source_subset` NEW - part inside the dataset (`labeled-images`, `train2019`, `videos80`, `bbox_images`...), nullable. (Replaces the old meaning of `source_dataset`.)
5. `item_id` - underlying id (uuid, stem, `<video>_<frame>`, frame number).
6. `label_source` - file(s) the labels were read from (path relative to `data_to_merge/`) or `folder-name`.
7. `label_level` - `image` | `clip` | `mask`.
8. `row_description` - verbose sentence.
9. `license` NEW - from the dataset registry (`CC BY 4.0`, `CC BY-NC-SA 4.0`, `CC BY-NC-ND`, `research-only`, `unknown`).

### WHAT: annotation kind (2 + flags further down)
10. `annotation_types` NEW - `|`-separated subset of `class`, `clip-class`, `bbox`, `mask` that exist for the row (e.g. `class|bbox|mask`).
11. `annotation_format` NEW - source encoding: `folder-name`, `csv`, `yolo-txt`, `voc-xml`, `supervisely-bitmap-json`, `json-bbox`, `mask-jpeg`, `mask-png`, `mask-multipage-tif`...

### WHERE (7)
12. `region` GEN - `lower-gi-tract` (terminal ileum/ileocecal valve -> anus) | `upper-gi-tract` (oesophagus, stomach, duodenum) | `small-bowel` (jejunum/ileum as seen by capsule/enteroscopy, segment unknown) | `unknown`. Authoritative only: never guessed.
13. `organ_raw` - original organ text if the dataset has one (`Lower GI`), else null.
14. `site` NEW - finer: `colon`, `cecum`, `rectum`, `anorectum`, `terminal-ileum`, `ileocecal-valve`, `stomach`, `pylorus`, `oesophagus`, `z-line`, `duodenum`, `small-bowel`, `unknown`, ...
15. `location_source` NEW - how region/site is known: `dataset-constant`, `folder`, `label-column`, `class-name`, `readme`, `unknown`.
16. `region_derived` NEW - optional heuristic region (only Kvasir-Capsule: from landmark order inside the video: stomach/small-bowel/colon), nullable, never used for `region`.
17. `procedure` NEW - `colonoscopy` | `gastroscopy` | `capsule-small-bowel` | `capsule-whole-gi` | `mixed` | `unknown`.
18. `imaging` NEW - `white-light` | `nbi` | `chromoscopy` | `mixed` | `unknown`.

### WHAT finding (24)
19. `category` GEN - `anatomical-landmarks`, `pathological-findings`, `quality-of-mucosal-views`, `therapeutic-interventions` (existing) + NEW `normal` (explicit normal class: `normal-mucosa`), `background` (frame without annotation of the target class: `no-polyp-annotated`, `no-lesion-annotated`), `artefact` (EAD2020: image artefacts, instrument, blood-in-view).
20. `category_raw`; 21. `finding`; 22. `finding_raw`; 23. `finding_harmonized` GEN - canonical lesion-type slug (kebab-case); equal across datasets only when the meaning is the same (modality kept apart by `procedure`/`region`).
24. `finding_parent` NEW - coarse pooling key that keeps the detailed `finding_harmonized` intact: `ulcerative-colitis` for `ulcerative-colitis-grade-*`, `esophagitis` for `esophagitis-a`/`esophagitis-b-d`, `polyps` for `polyps` and `polyp-like-lesion`, `ulcer` for `ulcer` and `aphthoid-ulceration`. Defaults to `finding_harmonized` when there is no coarser parent.
25. `finding_subtype` NEW - histology / grade / size class: `adenomatous`, `hyperplastic`, `grade-2-3`, `la-a`, `3-10mm`, `gt-10mm`.
26. `finding_harmonization` - `native` | `identity` | `mapped`; 27. `finding_in_image_vocab` GEN - (region, category, finding_harmonized) occurs among `image` rows of the whole table.
28. `findings_all` NEW - `|`-separated sorted distinct `finding_harmonized` of ALL labels of the row (equals `finding_harmonized` for single-label). Authoritative for multi-label images (see-ai: up to 3, EAD: up to 8, 9 Kvasir-Capsule double-labelled frames).
29. `class_counts_json` NEW - `{"erosion": 2, "bleeding": 1}` boxes per class for detection datasets, else null.
30-34. `finding_2`, `finding_2_harmonized`, `finding_2_raw`, `category_2`, `category_2_raw` (existing; used for video second label and double-labelled images).
35. `n_labels` GEN - number of distinct labels attached to the row (1; 2 with a second slot; `len(findings_all)` for multi-class).
36. `description` - free text (HK videos). 37-38. `bbps_score`, `bbps_range` (HK only).
39. `label_confidence` NEW - `high` | `medium` | `low` from the vocabulary map (how sure the native class -> unified label mapping is).
40. `is_negative` NEW - True when `category` in (`normal`, `background`).

### folder provenance (6, existing)
41-46. `dir_region`, `dir_category`, `dir_finding`, `label_category_mismatch`, `label_finding_mismatch`, `label_folder_mismatch`. Filled for datasets whose labels are also folder names (Hyper-Kvasir, Kvasir-Capsule `dir_finding`); null otherwise.

### files and links (15)
47. `file_path` - **relative to `data_to_merge/`** (e.g. `hyper-kvasir/labeled-images/...`), POSIX. 48. `file_ext`, 49. `file_exists`, 50. `file_size_bytes`.
51. `image_path`, 52. `segmented_image_path` (HK), 53. `mask_path`, 54. `annotation_path` NEW (per-item label file: xml / json / txt; null for folder- or csv-labelled).
55. `image_md5` GEN - filled for ALL image rows (cached; used for duplicate detection).
56. `video_id`, 57. `frame_index`, 58. `timestamp_s` - video rows; `video_id` and `frame_index` are also filled for Kvasir-Capsule image rows (provenance).
59. `seg_stem`, 60. `parent_image_sample_id`, 61. `mask_sample_id` (image <-> mask links).

### split safety and QA (7, NEW)
62. `group_id` - leakage-safe grouping key, globally unique (`<dataset>|<group>`): HK clips `video_id`; Kvasir-Capsule video; PolypsSet `case`; PolypGen sequence/case/centre; CVC `sequence_id`; EAD sequence; see-ai / Crohn contiguous-block proxy; null if none.
63. `group_kind` - `video` | `sequence` | `case` | `centre` | `block-proxy` | `none`.
64. `group_quality` - `exact` | `proxy` | `none` (how safe it is to split by `group_id`).
65. `split_official` - split shipped by the dataset (`train`, `val`, `test`, `fold-1`..`fold-5`), else null.
66. `dup_group_id` - `dup:<md5 prefix>` for rows sharing identical image bytes (whole table), else null.
67. `qa_flags` - `|`-separated flags: `annotation-missing`, `dup-label-conflict`, `split-leak-known`, `burned-in-text`, `non-gi-possible`, `orphan`, `label-folder-mismatch`, ...
68. `extra_json` - compact JSON with dataset-specific extras (PolypsSet `sub_source`/`histology_case`; PolypGen `centre`/`sequence`; EAD `sequence_id`/`mask_pages`; see-ai `export_batch`; Crohn `disease_context`; device names...).

### pixel size / video (14, existing)
69. `width`, 70. `height`; 71-82. `n_frames_total`, `fps`, `fps_effective`, `duration_s`, `codec`, `frames_suspect`, `timestamp_note`, `frame_rank`, `frames_sampled_in_video`, `frame_selection` (+ any existing ones) - video rows only.

### boxes and masks (23)
`has_mask`, `has_bbox`, `n_boxes`, `bboxes_json` GEN, `bbox_label` GEN (distinct labels, `|`-separated), `bbox_xmin/ymin/xmax/ymax` (union box), `bbox_source` NEW (`annotator` | `mask-derived` | `yolo-converted` | `voc`), `mask_format` NEW, `mask_encoding` NEW (how to binarise, e.g. `gray>127 white=polyp`, `value==1`, `tif-page>127`), `mask_foreground_pixels`, `mask_foreground_fraction`, `mask_tight_xmin/ymin/xmax/ymax`, `mask_in_bbox_fraction`, `mask_json_bbox_max_diff_px`, `mask_corner_pixel_removed`, `annotation_source`.
**Box convention (all datasets):** integer pixels, top-left origin, corner format, `xmax`/`ymax` **inclusive**. YOLO: `xmin=floor((cx-w/2)*W)`, `xmax=min(W-1, ceil((cx+w/2)*W)-1)` (same for y). VOC: as shipped, clipped to `[0, W-1]`, `qa_flags` not needed (+-1 px ambiguity documented). `bboxes_json` items: `{"label": <native slug>, "finding": <finding_harmonized>, "xmin","ymin","xmax","ymax"}`.

## Rules (defaults - reviewers please challenge)

* **R1 row units.** `image` per image file; `segmentation_mask` per standalone mask file (parity with HK: image row annotated + separate linked mask row; polypgen masks live inside JSON -> no mask rows, `has_mask` on the image row); `video_frame` only for addressed frames of .avi (HK). Boxes never get their own rows.
* **R2 duplicates.** Never silently dropped. EAD2020: ingest only `allDetection_training/bbox_images` (2,531 unique). Kvasir-Capsule: 47,229 rows, the 9 double-labelled frames carry `finding_2`. see-ai: all 18,481 kept, 242 duplicate-pair images flagged. PolypsSet/Crohn orphans (XML without image; image without CSV row) are NOT rows, they are logged.
* **R3 negatives.** `normal-mucosa` only for explicit normal classes (Crohn `N`, Kvasir-Capsule `Normal clean mucosa`), category `normal`. Frames of polyp datasets without a box -> category `background`, finding `no-polyp-annotated`. see-ai empty txt -> `background` / `no-lesion-annotated`.
* **R4 positives without geometry.** PolypGen 641 positive images without mask: kept, `has_mask=False`, `qa_flags=annotation-missing`.
* **R5 location is never guessed** in `region`; derived guesses go to `region_derived`.
* **R6 splits.** The table never contains a train/val/test assignment of its own; consumers split by `group_id` (check `group_quality`). Frames of one clip / sequence are near-duplicates.
* **R7 HK frames per video** = 20 (matches the saved `merge/merged-labels.csv`; `MERGE_PROCESS.md` still says 10).

## Open decisions for reviewers (my default in bold)

1. Region of Kvasir-Capsule landmarks: Pylorus **upper-gi-tract**; Ampulla of Vater **upper-gi-tract / duodenum** (HK convention); Ileocecal valve **lower-gi-tract / ileocecal-valve**; the 11 other classes **`unknown`** + `region_derived`.
2. Capsule datasets without segment (see-ai, Crohn): `region = small-bowel`, `site = small-bowel`.
3. EAD2020 `region = unknown`, category **`artefact`** for all 8 classes (blood -> `blood-in-view`, instrument -> `instrument`), not mapped to pathology vocabulary.
4. `lymph-follicle`, `vein` (see-ai): **pathological-findings** with `label_confidence=low`; `foreign-body`: **pathological-findings** (both capsule sets list it among lesion classes).
5. Capsule `Polyp` -> `finding_harmonized=polyps`; see-ai `polyp-like` -> `polyp-like-lesion`; both `finding_parent=polyps`.
6. `angiodysplasia` (see-ai) = `angiectasia` (Kvasir-Capsule): **same slug `angiectasia`**; `aphthoid-ulceration` (Crohn) stays separate from `erosion`, `finding_parent = ulcer`; Crohn `U3-10`/`U>10` -> `ulcer` + `finding_subtype`.
7. Keep 1,000 + 612 + 196 + 643 mask rows as duplicates of image rows (parity) - or fold into image rows only?
8. Is a contiguous-block `group_id` (see-ai, Crohn; `group_quality=proxy`) acceptable?
