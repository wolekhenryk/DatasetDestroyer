# see-ai (`dataset = see-ai`) - small-bowel capsule endoscopy, 12 lesion classes, YOLO boxes

Adapter `unify/adapters/see_ai.py`, vocabulary `unify/vocab/see-ai.csv`, analysis `docs/reports/see-ai.md`, overlay check `unify/tools/box_overlay.py`.
`META["expected"] = {"image": 18481}` (verified). Validation: all checks PASS; the output CSV is byte-identical across runs.

## 1. What it is
* 18,481 stills (576x576 RGB JPEG, circular field of view, burned-in `PillCam(R)SB3` text bottom-left) from **PillCam SB3 small-bowel capsule** exams, `device = PillCam SB3`, `procedure = capsule-small-bowel`, `imaging = white-light`.
* Source / paper: not named anywhere in the folder; from memory (not verified) Yokote et al., *Small bowel capsule endoscopy examination and open access database with artificial intelligence: the SEE-artificial intelligence project*, DEN Open 2024.
* **Licence: unknown** (no README / LICENSE shipped; `license = unknown`).

## 2. Layout used / ignored
| path | used? | what |
|---|---|---|
| `SEE_AI_project_all_images/SEE_AI_project_all_images/imageNNNNN.jpg` | yes | 18,481 images -> `image` rows (`source_subset = SEE_AI_project_all_images`) |
| `SEE_AI_project_all_txt/SEE_AI_project_all_txt/imageNNNNN.txt` | yes | the annotation: YOLO `class cx cy w h`, normalised, no trailing newline; **an empty file = no lesion annotated** (6,161 files) |
| `all_annotation.csv` | partly | only the class id -> name table (header rows 1-2) and a cross-check of the per-image box counts (0 mismatches). BOM + CRLF; 2 header rows; last row `annotation_sum` is wrong by the class id (it summed the class-number row too) -> warning, not used |
| `detected_samplevideo_short/*.mp4` | **no** | 5 H.264 clips (576x576, 25 fps, 4,905 frames): **model predictions** (class + confidence burned into the frames), not ground truth, no label files |

## 3. Label semantics
* Annotation kind: **bounding boxes** (`annotation_types = bbox`, `annotation_format = yolo-txt`, `bbox_source = annotator`). There is no native image-level label; `category` / `finding*` are derived from the boxes of the image. Rows with a box are `pathological-findings`, rows with an empty file are `background / no-lesion-annotated` (`finding_harmonization = derived`; **not** verified normal mucosa - may contain non-diagnostic frames such as food, bubbles, hair-like debris).
* Class id -> name -> unified label (vocabulary `unify/vocab/see-ai.csv`; counts verified against the table):

| id | native name (`finding_raw`) | `finding_harmonized` | parent | boxes | images | label_confidence |
|--:|---|---|---|--:|--:|---|
| 0 | angiodysplasia | `angiectasia` (= Kvasir-Capsule "Angiectasia") | | 931 | 825 | high |
| 1 | erosion | `erosion` | | 5,987 | 4,390 | high |
| 2 | stenosis | `stenosis` | | 445 | 442 | high |
| 3 | lymphangiectasia | `lymphangiectasia` | | 609 | 572 | high |
| 4 | lymph follicle | `lymph-follicle` | | 6,788 | 1,788 | **low** (benign / normal variant, largest class by boxes) |
| 5 | SMT | `submucosal-tumor` (code expanded) | | 542 | 528 | high |
| 6 | polyp-like | `polyp-like-lesion` | `polyps` | 3,230 | 2,157 | medium |
| 7 | bleeding | `bleeding` | | 868 | 801 | high |
| 8 | diverticulum | `diverticulum` | | 54 | 40 | medium |
| 9 | erythema | `erythema` | | 1,019 | 915 | high |
| 10 | foreign body | `foreign-body` | | 1,646 | 583 | medium |
| 11 | vein | `vein` | | 914 | 723 | **low** (visible vein = normal vascular anatomy / angiectasia mimic) |
| - | empty txt | `no-lesion-annotated` (`background`) | | 0 | 6,161 | medium |
| | total | | | 23,033 | 12,320 positive | |

* **Multi-label rows**: 10,920 images with one class, 1,356 with two, 44 with three. `finding*` = primary class (most boxes, then largest total box area, then lowest class id); **`findings_all` + `class_counts_json` carry all classes** (`n_labels` = number of distinct classes: 1 for 17,081 rows incl. the negatives, 2 for 1,356, 3 for 44). `label_confidence` of a row = the lowest confidence among its classes (not only the primary one). Never train a single-label model on `finding` without reading `findings_all`.
* `is_negative`: True for the 6,161 `background` rows, False for the 12,320 positives.

## 4. Location
`region = small-bowel`, `site = small-bowel` (segment jejunum / ileum **not recorded**), `location_source = dataset-constant`: the folder has no README; the knowledge comes from the device (burned-in PillCam SB3 text) and the dataset's purpose, it is not a per-image field. The first frames of a capsule transit (stomach / mouth) may occur, e.g. `image00001` is a non-diagnostic hair/fibre-like scene, and cannot be identified.

## 5. Boxes
* YOLO normalised -> inclusive pixel corners with `yolo_to_box(..., convention="continuous")`: the edges are real coordinates (only 2 % are within 0.01 px of an integer = chance), so `xmin = floor(x0)`, `xmax = ceil(x1)-1` after snapping (outer rounding: a box may be up to ~1 px wider than the annotation).
* Edge behaviour checked on real boxes (whole table, 23,033 boxes, against an independent re-implementation: 0 differences with the helper's snap tolerance): 8 boxes start at `xmin = 0`, 5 at `ymin = 0`, 14 end at `xmax = 575`, 3 at `ymax = 575` (e.g. `image01839` `x1 = 576.000` -> `xmax = 575`; `image01879` `x0 = -0.0` -> `xmin = 0`; `image05809` `y0 = 0.0` -> `ymin = 0`). The visual overlay (`python -m unify.tools.box_overlay --dataset see-ai --edge`) shows the rectangles ending on the image border and enclosing the lesions. With a plain 1e-3 px snap 444 boxes (1.9 %) would differ by 1 px; the helper's `1e-5*dim` is used.
* **Zero-area box**: `image07741` line `3 0.114906 0.877222 0.000000 0.000000` (class lymphangiectasia) is kept as the 1-pixel box `(66, 505, 66, 505)`; the row has `extra_json.zero_area_box = true` and a build warning.
* Union `bbox_*` is filled for every positive row, but for multi-class rows (and frame-sized stenosis / erythema boxes) it is not a lesion location - use `bboxes_json`.

## 6. Grouping, leaks, duplicates
* **No patient / exam / video id.** `group_id = see-ai:b500-NNN`, `group_kind = block-proxy`, `group_quality = proxy`: blocks of 500 consecutive image numbers (the numbering follows the capsule videos: share of both-positive frames k apart that share a class falls from 0.87 at k=1 to 0.29 at k=100 and 0.22 at k=500 = chance 0.21), **blocks joined when they contain the two members of a byte-identical image pair** (union-find) -> 37 blocks become **31 groups** (500-2,000 images, largest = 4 blocks). Blocks only approximate exams: frames of one exam can still sit in neighbouring blocks.
* **121 byte-identical image pairs (242 images)**; the pairs are far apart in numbering (gap up to 15,683) and their annotations often differ: 9 pairs have identical txt. The runner flags the conflicts automatically: `dup-label-conflict` on **36 images** (18 pairs whose class sets differ, e.g. `image00225` one large `bleeding` box vs `image13494` one small `erosion` box for the same picture), `dup-box-conflict` on **28 images** (14 pairs with the same classes but a different number of boxes or union boxes with IoU < 0.5); the other 178 images are identical or differ only by slightly different outlines (IoU >= 0.5, treated as annotation noise: 84 pairs have the same classes but not byte-identical boxes). `dup_group_id` links the copies. For training keep one member per `dup_group_id` (or keep both in one fold).
* **Two export batches** (`extra_json.export_batch`): batch 1 = 17,086 images (JPEG comment `Lavc58.134.100`, black level 16 in the top-left patch; images 1-17,085 and 18,424), batch 2 = 1,395 images (no comment, black level 0; 17,086-18,481 except 18,424). Class balance differs: negatives 35 % (6,043 of 17,086) in batch 1 vs 8.5 % (118 of 1,395) in batch 2 - a model can learn the batch as a shortcut for "has lesion".
* No shipped train/val/test split (`split_official` empty).

## 7. `extra_json` keys
`export_batch` (1 / 2), `image_number` (int, = the number in the file name), `native_class_ids` (`{native name: id}` of the classes present; absent for negatives), `zero_area_box` (true, only `image07741`).

## 8. Pitfalls
* `all_annotation.csv` (BOM, CRLF, second header row, wrong sum row) is only a cross-check - never read it with a naive reader as a label table.
* Burned-in text `PillCam(R)SB3` (bottom-left), a dark patch top-left and a white dot top-right in every frame: mask them if the overlay should not be learned (not done here). Boxes touching the text area were not checked.
* `lymph-follicle` and `vein` are benign structures annotated as lesions: filter on `label_confidence` if the target is "pathology vs normal".
* The class `polyp-like` is pooled with colonic polyps only via `finding_parent = polyps`; always read it with `region`.
* Sub-pixel box precision is lost (outer rounding, 6-decimal source).

## 9. Row counts (`META["expected"]`)
`image` 18,481 (12,320 with boxes, 6,161 without); no `segmentation_mask`, no `video_frame` rows.
