# ead2020-train (`dataset = ead2020-train`) - Endoscopy Artefact Detection challenge 2020: ARTEFACT / quality labels, NOT pathology

Adapter `unify/adapters/ead2020_train.py`, vocabulary `unify/vocab/ead2020-train.csv`, analysis `docs/reports/EAD2020_train.md`, overlay check `unify/tools/box_overlay.py`.
`META["expected"] = {"image": 2531, "segmentation_mask": 643}` (verified). Validation: all checks PASS; output byte-identical across runs.

## 1. What it is and what it is NOT
* Training release of EAD2020 / EndoCV2020 (Ali et al., Sci Rep 2020; EAD2019 papers). Licence **CC BY-NC-SA 4.0** (non-commercial, share-alike; `Readme.md`, `license.txt`) -> `license = CC BY-NC-SA 4.0`.
* **There are no polyp / disease / pathology labels at all.** All 8 classes are image-quality artefacts. Every row has `category = artefact`, so `is_negative` is empty (not negative, not positive for pathology). Use the dataset for artefact / quality detection or robustness, never as a pathology source. Every image carries at least one artefact box: there are no artefact-free frames.
* Anatomy is **not annotated**: `region = unknown`, `site = unknown`, `location_source = unknown`, `procedure = unknown`, `imaging = unknown` per frame. Visual inspection shows a mix (about 61 % 512x512 upper-GI-like frames with octagonal corners, colon-like frames, bladder frames with `URO` / `HAL URO` overlays and blue-light fluorescence, patient-data panels). Non-GI frames exist and are not identified.

## 2. Layout: the same 2,531 pictures are stored several times
Verified by md5 / stems (the adapter asserts the first two lines):
| folder | content | use |
|---|---|---|
| `allDetection_training/bbox_images/` | 2,531 jpg + YOLO txt | **canonical copy -> the 2,531 `image` rows** (= framesOnly/frames 2,200 + 99Frames 99 + sequence Detection 232, all byte-identical to their originals) |
| `EAD2020_dataType_framesOnly/frames` + `gt_bbox` | `EAD2020_frameOnly_00001..02200` | duplicate, ignored (gives `source_subset = framesOnly`) |
| `EAD2020-Phase-II-Detection_Segmentation-99Frames/originalImages` + `bbox` + `semanticMasks` | `EAD2020_MP10000..10098` | duplicate images/boxes (-> `source_subset = 99Frames`); masks used |
| `EAD2020-Phase-II_dataType_sequence/Detection/<seq>` + `<seq>_bbox` | 5 sequences `1445-01` (50), `1445-02` (20), `1445-03` (74), `PYL-02` (60), `PYL-N-02` (28) | duplicates (-> `source_subset = sequence-<seq>`) |
| `.../SemanticSegmentation_Sequence/<seq>` + `<seq>_masks` (1445-01, 1445-02) | 70 images + masks | images = copies of the Detection images; masks used |
| `EAD2020_dataType_framesOnly/segmentation/images_ead2020` + `masks_ead2020` | 474 images named `EAD2020_semantic_NNNNN` + masks | **renamed byte-identical copies of 474 `frameOnly` frames** (no filename relation) -> linked by md5; masks used |
| `sequence_onlyData_Detection/` | 232 txt | duplicate of the sequence boxes, ignored |
| `class_list.txt` (+ copies), `class_list_semantic.txt` | class names | read (the adapter stops if they change) |
File arithmetic: 5,606 jpg on disk = 2,531 canonical + 2,200 + 99 + 232 + 474 + 70, i.e. 3,075 byte-identical extra copies. README counts disagree with the data (`Readme.md`: 233 sequence frames / 642 masks; `Readme.pdf`: 573 masks; data: 232 / 643).

## 3. Row units
* `image` (2,531): one per canonical image. `source_subset` = **origin subset** (`framesOnly` 2,200, `99Frames` 99, `sequence-1445-01` 50, `-1445-02` 20, `-1445-03` 74, `-PYL-02` 60, `-PYL-N-02` 28); `file_path` always points at the canonical copy.
* `segmentation_mask` (643): one per multi-page TIFF (framesOnly 474, 99Frames 99, 1445-01 50, 1445-02 20); the image row of a masked image has `has_mask = True`, `mask_path`, `mask_sample_id`, `seg_stem`, `segmented_image_path` (the renamed / original copy) and the mask statistics; the mask row links back with `parent_image_sample_id` and `image_path` = the **canonical** image (for `EAD2020_semantic_*` through the md5 map; `seg_stem` = the mask stem). Mask rows do **not** repeat the box columns.

## 4. Annotations
### Boxes (all 2,531 images, 31,069 boxes)
* YOLO `class_id cx cy w h`, normalised; ids from `class_list.txt`. 133 files use CRLF; 13 boxes protrude slightly over the image; 3 boxes are zero-sized.
* **Convention `one-based-inclusive`**: 100 % of the box edges are integers (the YOLO numbers are float round-trips of integer boxes, so plain `floor`/`ceil` would be wrong for 24 % of the boxes) and they are **1-based inclusive** pixel indices: `xmin = round(x0)-1`, `xmax = round(x1)-1`, clamped to `[0, W-1]` (657 boxes need the clamp). Evidence: on the Phase-II masks (99Frames + sequences 1445-01/02) the fraction of mask foreground inside the same-class boxes is 99.92 % / 100 % with this rule versus 99.8 % / 99.7 % for the 0-based alternatives, and for 76 images with a single instrument box the tight mask box equals the converted box on all four sides. **Verified only for Phase II**; for `framesOnly` box and mask geometry are not pixel-aligned (in-box fraction ~0.82 under every convention), so the rule is assumed there (`extra_json.bbox_convention_verified = assumed`).
* Boxes per image: mean 12.3, max 156; classes per image 1-7 (315 / 515 / 718 / 643 / 264 / 61 / 15 images with 1..7 classes).

### Masks (643, multi-page 8-bit TIFF, one page per class)
* Page order = `class_list_semantic.txt` (Instrument, Specularity, Artefact, Bubbles, Saturation, blood; not the box class order): `framesOnly` masks have **5 pages (no blood)**, Phase-II masks 6. Blur and contrast have boxes only.
* `mask_encoding`: `tif-page>127; pages ...`; foreground (the artefact) = 255. In the 5-page set a page whose **last pixel row is all 255 is an "empty page marker" (1,050 of 2,370 pages) and that row is zeroed** (`mask_noise_pixels_removed` counts the zeroed pixels, non-zero in 210 mask rows; flagged per page in `extra_json.mask_sentinel_pages`). 524 foreground pages of that set also contain interpolated values (0.0-1.6 % of the pixels not 0/255) - hence `> 127`. The Phase-II masks are clean 0/255; the adapter stops if one has an all-255 last row.
* **Mask statistics = union over the non-empty pages** (`mask_foreground_*`, `mask_tight_*`); per-page pixels and tight boxes are in `extra_json`. `mask_in_bbox_fraction` = foreground of page k inside the boxes of the **same class** (sum over pages); `mask_json_bbox_max_diff_px` = largest difference between a page's tight box and the union of the same-class boxes. Phase II: median 1.0; `framesOnly`: median 0.94 (433 of 474 below 0.999), i.e. masks and boxes were annotated separately there.
* **Mask-row labels come from the non-empty pages** (primary = largest foreground), not from the image boxes: `findings_all` = the classes with foreground; `class_counts_json` is empty (pixels, not boxes). One mask (`EAD2020_semantic_00220`) has no foreground in any page: it inherits the image's labels and carries `extra_json.mask_empty = true` (build warning).

## 5. Classes -> unified labels (`category = artefact` for all)
| id | native (`finding_raw`) | `finding_harmonized` | boxes | images | mask page | confidence |
|--:|---|---|--:|--:|---|---|
| 0 | specularity | `specular-reflection` | 11,859 | 1,140 | Specularity | high |
| 1 | saturation | `saturation` | 1,423 | 1,127 | Saturation | high |
| 2 | artifact | `other-artefact` | 8,694 | 1,991 | Artefact | high |
| 3 | blur | `blur` | 749 | 625 | - | high |
| 4 | contrast | `low-contrast` | 1,866 | 1,648 | - | medium |
| 5 | bubbles | `bubbles` | 5,345 | 689 | Bubbles | high |
| 6 | instrument | `instrument` | 605 | 417 | Instrument | medium |
| 7 | blood | `blood-in-view` (a view-quality class, **not** the pathology `bleeding`) | 528 | 225 | blood (6-page masks only) | medium |
`finding` = the primary class of the row (most boxes, then largest total box area, then lowest class id); `findings_all` / `class_counts_json` list all of them. `label_confidence` = lowest among the row's classes.

## 6. Groups, splits, leaks
* Sequences (232 images): `group_id = ead2020-train:<seq>`, `sequence` / `exact`, `video_id = <seq>`, `frame_index` = the number in the file name (starts at 0 for 1445-xx and `1445-03`, at 1 for `PYL-02`, at 168 for `PYL-N-02`; spacing unknown). Consecutive frames are near-duplicates.
* 99 Phase-II frames: one group `ead2020-train:99frames` (`block-proxy` / `proxy`; the frames are independent, a single group is merely safe).
* `framesOnly` (2,200 frames, no ids): `ead2020-train:frames-b100-NN` = blocks of 100 consecutive frame numbers (22 groups, `block-proxy` / `proxy`). **This still leaks**: only ~55-60 % of the near-duplicate partners (24x24 thumbnail cosine > 0.98; 1,092 of 2,200 frames have one) lie within 50 frame numbers; the rest (mostly dark-red saturated frames) are scattered.
* No shipped split. The challenge test sets are not in the folder.

## 7. `extra_json` keys
* image rows: `bbox_convention` (`one-based-inclusive`), `bbox_convention_verified` (`phase2-masks` for 99Frames + sequences 1445-01/02, `assumed` otherwise), `native_class_ids` (`{native name: id}` of the classes present).
* mask rows: `mask_set`, `mask_pages` (page names in order), `mask_page_px` (non-empty pages -> pixels), `mask_page_tight` (-> `[xmin,ymin,xmax,ymax]`), `canonical_image_stem`, `mask_sentinel_pages` (5-page set, when a marker row was zeroed), `mask_empty` (true for `EAD2020_semantic_00220`).

## 8. Pitfalls
* Not a pathology dataset; blood / instrument are artefact classes here. Filter by `category` in any pathology consumer.
* Count images with `source_type == 'image'` (643 images also appear as mask rows).
* Heterogeneous sources: 81 image sizes (259x243 ... 1920x1080), burned-in text and patient-data panels, bladder frames, many almost featureless saturated frames. Share-alike / non-commercial licence.
* Mask page order and page count differ between subsets; `framesOnly` masks need the sentinel-row rule.
* The 1-based box convention is verified on Phase II only.

## 9. Row counts
`image` 2,531, `segmentation_mask` 643 (3,174 rows); no `video_frame` rows. Group ids: 28 (22 + 1 + 5).
