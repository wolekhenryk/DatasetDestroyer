# Reader 3 - review of `SCHEMA_DRAFT.md` (see-ai, EAD2020_train, DataCrohnIPI)

Scope: review only, no adapter code. Everything marked "verified" was checked with throw-away scripts in `.../scratchpad/review/` (python -I, read-only on the data). Column numbers are those of the draft; the box/mask block is unnumbered in the draft, so I quote column names there.

## 0. Findings that change the draft (ranked)

| # | finding | evidence |
|--:|---|---|
| A | **The YOLO -> pixel formula in "Box convention" is numerically wrong for integer-pixel sources and off by one for EAD.** (1) `floor`/`ceil` of values that are integers up to float noise (`97.99999999999997`, `193.00000000000006`) flips by 1 px: it disagrees with correct rounding on **7,408 of 31,069 EAD boxes (24 %)**, up to 609 of 1,351 boxes for 800x700 images. In EAD **100 %** of box edges are integers within 0.01 px (they were converted from integer boxes); in see-ai only 2 % are (= chance), so see-ai boxes really are continuous. (2) `xmin` has no `max(0, .)` clamp: 8 EAD boxes give negative `xmin` (down to -15) and 657 EAD boxes need a clamp under the corrected rule; 3 see-ai boxes give -1 from `-0.0`-type noise. (3) EAD Phase-II boxes are **1-based inclusive**: the mask tight box (0-based) equals `[round(x0)-1, round(x1)-1]` on all four sides for 76/76 instrument images (99Frames + sequences) and for blood / saturation / instrument / artifact in the worked example `EAD2020_MP10058`; with this rule 100 % of the mask foreground lies inside the same-class boxes. With the draft rule `xmin`,`ymin` are 1 px too large. | `scratchpad/review/boxconv.py`, `boxmask.py`, `ex_ead2.py`, `inbox.py` |
| B | **Multi-class rows: `finding`, `bbox_xmin..ymax`, `is_negative`, `bbox_label` are under-specified** - see section 2. | |
| C | **Slug rule for code-labelled datasets (col 21)**: `slugify("U>10")` = `u-10`, `slugify("U3-10")` = `u3-10`, `E`/`O`/`AU`/`S`/`N` -> `e`,`o`,`au`,`s`,`n` (Crohn). `finding` must be the slug of the *expanded class name* from the dataset legend; the code stays in `finding_raw`. | `CrohnIPI_description.csv`, README legend |
| D | **`group_id` for block-proxy datasets is not defined** (block size, numbering, duplicate pairs). see-ai has 121 byte-identical pairs, far apart in numbering - blocks alone leak them. Proposal in 4.8. | `lag.py`, `comp.py`, `lag2.py` |
| E | EAD masks are **multi-page TIFFs with one page per class**; several mask columns need a definition (section 2.3). `annotation_format`/`annotation_types` must be allowed to hold several values for an image row that has boxes and a mask. | |
| F | `procedure`/`imaging` = `mixed` is wrong on a row that describes one frame (EAD): use `unknown` per row. | |
| G | Missing columns that pay off: **`device`**; `video_id`+`frame_index` also for EAD sequence frames; `source_subset` should be the *origin* subset (EAD). | |

## 1. Example rows

Conventions: `(null)` = the dataset could plausibly have a value but does not; columns not listed are empty for that row. `qa_flags`, `extra_json` content as I would emit it. Values for new rules I propose below are marked **(proposed)**.

### 1.1 see-ai - `image` row, multi-box multi-class (image11944: 6 boxes, 3 classes)

Source: `see-ai/SEE_AI_project_all_txt/SEE_AI_project_all_txt/image11944.txt` (230 bytes), six lines:
```
1 0.476826 0.798773 0.481516 0.226320      erosion
10 0.458613 0.471293 0.079082 0.062063     foreign body
10 0.257747 0.553258 0.079464 0.059808     foreign body
10 0.380034 0.515864 0.049893 0.048922     foreign body
1 0.340607 0.496409 0.557504 0.333891      erosion
2 0.500337 0.497079 0.928210 0.932282      stenosis
```
(class ids from `all_annotation.csv` header rows; per-class counts equal the CSV row 11944.)

| col | column | value |
|--:|---|---|
| 1 | sample_id | `image:see-ai:image11944` |
| 2 | source_type | `image` |
| 3 | dataset | `see-ai` |
| 4 | source_subset | `SEE_AI_project_all_images` |
| 5 | item_id | `image11944` |
| 6 | label_source | `see-ai/SEE_AI_project_all_txt/SEE_AI_project_all_txt/image11944.txt` (the CSV is only a cross-check) |
| 7 | label_level | `image` |
| 8 | row_description | "SEE-AI small-bowel capsule frame image11944 (PillCam SB3, 576x576) with 6 YOLO boxes: 2 erosion, 3 foreign body, 1 stenosis" |
| 9 | license | `unknown` |
| 10 | annotation_types | `bbox` (class labels are *derived* from boxes, see 2.4) |
| 11 | annotation_format | `yolo-txt` |
| 12 | region | `small-bowel` |
| 13 | organ_raw | (null) |
| 14 | site | `small-bowel` |
| 15 | location_source | `dataset-constant` |
| 17 | procedure | `capsule-small-bowel` |
| 18 | imaging | `white-light` |
| 19 | category | `pathological-findings` |
| 20 | category_raw | (null) |
| 21 | finding | `foreign-body` **(proposed rule: class with most boxes; tie -> larger summed box area; tie -> lower native id)** |
| 22 | finding_raw | `foreign body` |
| 23 | finding_harmonized | `foreign-body` |
| 24 | finding_parent | `foreign-body` |
| 26 | finding_harmonization | `identity` |
| 27 | finding_in_image_vocab | `True` (trivially, it is an `image` row - see 5.3) |
| 28 | findings_all | `erosion\|foreign-body\|stenosis` |
| 29 | class_counts_json | `{"erosion":2,"foreign-body":3,"stenosis":1}` (keys = `finding_harmonized`) |
| 30-34 | finding_2 / _harmonized / _raw, category_2 / _raw | `erosion` / `erosion` / `erosion` / `pathological-findings` / (null); third class only in `findings_all` |
| 35 | n_labels | `3` |
| 39 | label_confidence | `medium` (**proposed: minimum over the row's classes**; foreign-body is medium) |
| 40 | is_negative | `False` |
| 47-50 | file_path / file_ext / file_exists / file_size_bytes | `see-ai/SEE_AI_project_all_images/SEE_AI_project_all_images/image11944.jpg` / `jpg` / `True` / `63510` |
| 51 | image_path | same as `file_path` |
| 54 | annotation_path | `see-ai/SEE_AI_project_all_txt/SEE_AI_project_all_txt/image11944.txt` |
| 55 | image_md5 | `78f9e5daa3d8de8267df76601dd8e9eb` |
| 56 | video_id | (null) |
| 62-64 | group_id / group_kind / group_quality | `see-ai\|b500-024` / `block-proxy` / `proxy` (rule in 4.8) |
| 65 | split_official | (null) |
| 66 | dup_group_id | (null) (md5 unique) |
| 67 | qa_flags | `burned-in-text\|multi-class` (**multi-class is proposed**) |
| 68 | extra_json | `{"export_batch":1,"native_class_ids":{"erosion":1,"foreign-body":10,"stenosis":2},"black_level":16}` |
| 69-70 | width / height | `576` / `576` |
| | has_mask / has_bbox | `False` / `True` |
| | n_boxes | `6` |
| | bboxes_json | `[{"label":"erosion","finding":"erosion","native_id":1,"xmin":135,"ymin":394,"xmax":413,"ymax":525,"yolo":[0.476826,0.798773,0.481516,0.22632]}, {"label":"foreign-body",...,"xmin":241,"ymin":253,"xmax":286,"ymax":289,...}, {"label":"foreign-body",...,"xmin":125,"ymin":301,"xmax":171,"ymax":335,...}, {"label":"foreign-body",...,"xmin":204,"ymin":283,"xmax":233,"ymax":311,...}, {"label":"erosion",...,"xmin":35,"ymin":189,"xmax":356,"ymax":382,...}, {"label":"stenosis",...,"xmin":20,"ymin":17,"xmax":555,"ymax":554,...}]` (`native_id` and `yolo` are **proposed item keys**, see 3) |
| | bbox_label | `erosion\|foreign-body\|stenosis` (native slugs) |
| | bbox_xmin/ymin/xmax/ymax | (null) **(proposed: union box only when the row has a single class; here 3 classes and the stenosis box spans 93 % of the frame, the union (20,17,555,554) says nothing)** |
| | bbox_source | `yolo-converted` |
| | annotation_source | `see-ai YOLO txt (SEE_AI_project_all_txt)` |

Edge boxes checked (all give exact results with the corrected rule): image01879 `1 0.148289 0.466104 0.296579 0.341111` -> x edges `[-0.0, 170.829]` -> `xmin=0,xmax=170`; image01839 `1 0.715622 0.200579 0.568756 0.266433` -> `x1=576.0` -> `xmax=575`; image05809 box with `y0=0.0` -> `ymin=0`.
A **negative** see-ai row (empty txt) differs by: `annotation_types=bbox` (empty list), `category=background`, `finding=no-lesion-annotated`, `findings_all=no-lesion-annotated`, `is_negative=True`, `has_bbox=False`, `n_boxes=0`, `bboxes_json=[]` (or null), `class_counts_json={}`.

### 1.2 EAD2020 - `image` row, multi-box multi-class (EAD2020_MP10058, 14 boxes, 6 classes, has a mask)

Source (canonical copy, byte-identical to `EAD2020-Phase-II-Detection_Segmentation-99Frames/originalImages/EAD2020_MP10058.jpg`, md5 equal): 259x243 RGB JPEG, 22,339 bytes. `bbox_images/EAD2020_MP10058.txt` holds 14 YOLO lines (class counts: specularity 5, contrast 3, artifact 2, blood 2, saturation 1, instrument 1).

| col | column | value |
|--:|---|---|
| 1 | sample_id | `image:ead2020-train:EAD2020_MP10058` |
| 2 | source_type | `image` |
| 3 | dataset | `ead2020-train` |
| 4 | source_subset | `99Frames` (**proposed: the ORIGIN subset** - `framesOnly` / `99Frames` / `sequence-1445-01` ... - instead of the canonical folder `bbox_images`, because the origin carries the box-convention and quality information; the canonical folder is in `file_path`) |
| 5 | item_id | `EAD2020_MP10058` |
| 6 | label_source | `EAD2020_train/allDetection_training/bbox_images/EAD2020_MP10058.txt\|EAD2020_train/class_list.txt` |
| 7 | label_level | `image` |
| 8 | row_description | "EAD2020 artefact-annotated endoscopic frame (259x243) with 14 artefact boxes of 6 classes and a 6-page artefact mask; no pathology label" |
| 9 | license | `CC BY-NC-SA 4.0` |
| 10-11 | annotation_types / annotation_format | `bbox\|mask` / `yolo-txt\|mask-multipage-tif` (**needs `\|`-lists, aligned with annotation_types**) |
| 12-16 | region / site / location_source | `unknown` / `unknown` / `unknown` (organ (null) in `organ_raw`; `region_derived` (null)) |
| 17-18 | procedure / imaging | `unknown` / `unknown` (per-frame; dataset-wide it is mixed, see F) |
| 19 | category | `artefact` |
| 21-23 | finding / finding_raw / finding_harmonized | `specularity` / `specularity` / `specular-reflection` (**primary = class with most boxes**, same rule as see-ai) |
| 24 | finding_parent | `specular-reflection` |
| 26-27 | finding_harmonization / finding_in_image_vocab | `mapped` / `False` |
| 28 | findings_all | `blood-in-view\|instrument\|low-contrast\|other-artefact\|saturation\|specular-reflection` |
| 29 | class_counts_json | `{"specular-reflection":5,"low-contrast":3,"other-artefact":2,"blood-in-view":2,"saturation":1,"instrument":1}` |
| 30-34 | finding_2 / _harmonized / _raw / category_2 / _raw | `contrast` (slug) / `low-contrast` / `contrast` / `artefact` / (null); other four classes only in `findings_all` |
| 35 | n_labels | `6` |
| 39 | label_confidence | `medium` (min over classes: contrast, instrument, blood are medium) |
| 40 | is_negative | `False` (but see 5.4: the row is *not* a pathology positive) |
| 47-50 | file_path / ext / exists / size | `EAD2020_train/allDetection_training/bbox_images/EAD2020_MP10058.jpg` / `jpg` / `True` / `22339` |
| 51-53 | image_path / segmented_image_path / mask_path | same as file_path / `EAD2020_train/EAD2020-Phase-II-Detection_Segmentation-99Frames/originalImages/EAD2020_MP10058.jpg` (identical bytes, other folder) / `EAD2020_train/EAD2020-Phase-II-Detection_Segmentation-99Frames/semanticMasks/EAD2020_MP10058_mask.tif` |
| 54 | annotation_path | `EAD2020_train/allDetection_training/bbox_images/EAD2020_MP10058.txt` |
| 55 | image_md5 | `adf1d1470a01ab074c66faf6938afafd` |
| 56-57 | video_id / frame_index | (null) (not a sequence frame) |
| 59, 61 | seg_stem / mask_sample_id | `EAD2020_MP10058_mask` / `mask:ead2020-train:EAD2020_MP10058_mask` |
| 62-64 | group_id / group_kind / group_quality | (null) / `none` / `none` (the 99 Phase-II frames are independent; adjacent-frame thumbnail difference equals random pairs) |
| 65-66 | split_official / dup_group_id | (null) / (null) |
| 67 | qa_flags | `non-gi-possible\|multi-class` |
| 68 | extra_json | `{"origin_subset":"99Frames","bbox_index_base":1,"bbox_convention_verified":"phase2-masks","canonical_folder":"allDetection_training/bbox_images","other_copies":["EAD2020-Phase-II-Detection_Segmentation-99Frames/originalImages","EAD2020-Phase-II-Detection_Segmentation-99Frames/bbox"],"native_class_ids":{"specularity":0,"saturation":1,"artifact":2,"contrast":4,"instrument":6,"blood":7}}` |
| 69-70 | width / height | `259` / `243` |
| | has_mask / has_bbox | `True` / `True` |
| | n_boxes | `14` |
| | bbox_label | `artifact\|blood\|contrast\|instrument\|saturation\|specularity` |
| | bbox_xmin..ymax | (null) (**proposed**; with the correct rule the union would be `9,28,249,242`, with the draft rule `10,29,249,242`) |
| | bbox_source | `yolo-converted` |
| | bboxes_json | 14 items, e.g. specularity `{"xmin":225,"ymin":93,"xmax":229,"ymax":96}` (raw edges `226,94,230,97` -> `-1` -> **draft rule would give `226,94,229,96`**), instrument `{"xmin":143,"ymin":173,"xmax":184,"ymax":242}` (draft rule: `144,174,184,242`), blood `{"xmin":93,"ymin":60,"xmax":137,"ymax":115}` and `{"xmin":167,"ymin":87,"xmax":246,"ymax":176}`, saturation `{"xmin":10,"ymin":28,"xmax":56,"ymax":93}` |
| | mask_format / mask_encoding | `multipage-tif` / `tif-page>127 white=artefact; page order Instrument,Specularity,Artefact,Bubbles,Saturation,blood` |
| | mask_foreground_pixels / _fraction | `8415` / `0.133705` (**union over the 6 pages**; per page in `extra_json`) |
| | mask_tight_xmin/ymin/xmax/ymax | `9`,`28`,`249`,`242` (union) |
| | mask_in_bbox_fraction | `1.0` (pages vs boxes of the *same* class, corrected rule) |
| | mask_json_bbox_max_diff_px | (null) (no JSON; undefined for multi-class masks) |
| | mask_corner_pixel_removed | `False` |
| | annotation_source | `EAD2020 challenge (Ali et al.): YOLO txt boxes + multipage TIFF masks` |

### 1.3 EAD2020 - `segmentation_mask` row (same frame)

| col | column | value |
|--:|---|---|
| 1 | sample_id | `mask:ead2020-train:EAD2020_MP10058_mask` |
| 2-5 | source_type / dataset / source_subset / item_id | `segmentation_mask` / `ead2020-train` / `99Frames` / `EAD2020_MP10058_mask` |
| 6 | label_source | `EAD2020_train/EAD2020-Phase-II-Detection_Segmentation-99Frames/semanticMasks/EAD2020_MP10058_mask.tif\|EAD2020_train/EAD2020-Phase-II_dataType_sequence/class_list_semantic.txt` |
| 7 | label_level | `mask` |
| 10-11 | annotation_types / annotation_format | `mask` / `mask-multipage-tif` |
| 12-18 | region .. imaging | as the image row |
| 19 | category | `artefact` |
| 21-23 | finding / finding_raw / finding_harmonized | `blood` / `blood` / `blood-in-view` (**primary = page with most foreground pixels: blood 4,541 px**) |
| 28 | findings_all | `blood-in-view\|instrument\|other-artefact\|saturation\|specular-reflection` (**non-empty pages only; the image row has 6 classes (adds low-contrast)** - the mask row must not "inherit" the image's class list, because masks exist for 5-6 of the 8 classes and across the 474 `framesOnly` masks 45 pages are non-empty without a box of that class) |
| 29 | class_counts_json | (null) (counts are boxes; per-page pixels in `extra_json`) |
| 30-34 | finding_2 ... | `instrument` / `instrument` / `instrument` / `artefact` / (null) (2nd largest page, 1,967 px) |
| 35 | n_labels | `5` |
| 47-50 | file_path / ext / exists / size | `EAD2020_train/EAD2020-Phase-II-Detection_Segmentation-99Frames/semanticMasks/EAD2020_MP10058_mask.tif` / `tif` / `True` / `378908` |
| 51-53 | image_path / segmented_image_path / mask_path | canonical image path / `.../originalImages/EAD2020_MP10058.jpg` / = file_path |
| 55 | image_md5 | `adf1d1470a01ab074c66faf6938afafd` |
| 59-60 | seg_stem / parent_image_sample_id | `EAD2020_MP10058_mask` / `image:ead2020-train:EAD2020_MP10058` |
| 62-64 | group_* | (null) / `none` / `none` |
| 67-68 | qa_flags / extra_json | `non-gi-possible` / `{"mask_pages":["instrument","specularity","artifact","bubbles","saturation","blood"],"mask_page_px":{"instrument":1967,"specularity":119,"artifact":631,"bubbles":0,"saturation":1176,"blood":4541},"mask_page_tight":{"instrument":[143,173,184,242],"saturation":[10,28,56,93],"blood":[93,60,246,176]}}` |
| 69-70 | width / height | `259` / `243` |
| | has_mask / has_bbox | `True` / `True` (box columns repeated from the parent, parity with HK; they are redundant for EAD) |
| | mask_format, mask_encoding, mask_foreground_pixels, mask_foreground_fraction, mask_tight_*, mask_in_bbox_fraction, mask_corner_pixel_removed | as in the image row |

Variant for the 474 `framesOnly` masks: file `.../segmentation/masks_ead2020/EAD2020_semantic_00000.tif` has **5 pages** (no blood); `seg_stem=EAD2020_semantic_00000`; `parent_image_sample_id=image:ead2020-train:EAD2020_frameOnly_01308` (found through md5; `EAD2020_semantic_00000.jpg` is a byte-identical copy of `EAD2020_frameOnly_01308.jpg`) and `segmented_image_path` = the `images_ead2020/EAD2020_semantic_00000.jpg`; `mask_encoding` = `tif-page>127 after zeroing the last pixel row; page order Instrument,Specularity,Artefact,Bubbles,Saturation`; `qa_flags` adds `mask-sentinel-row` when the last row is 255 (1,050 of 2,370 pages); `extra_json.mask_pages` has 5 names; `mask_foreground_*` measured after zeroing the last row. Sequence masks (`1445-01`, `1445-02`, 70 files, 6 pages) link to the same-named image in `Detection/<seq>` = canonical `allDetection_training` copy.

### 1.4 DataCrohnIPI - `image` row (01184.jpg, label `U3-10`, fold 3)

| col | column | value |
|--:|---|---|
| 1 | sample_id | `image:datacrohnipi:01184` |
| 2-5 | source_type / dataset / source_subset / item_id | `image` / `datacrohnipi` / `imgs` / `01184` |
| 6 | label_source | `DataCrohnIPI/CrohnIPI_description.csv` |
| 7 | label_level | `image` |
| 8 | row_description | "CrohnIPI small-bowel capsule frame 01184 (320x320), expert label U3-10 (ulceration 3-10 mm), official CV test fold 3" |
| 9 | license | `CC BY-NC-ND` |
| 10-11 | annotation_types / annotation_format | `class` / `csv` |
| 12-15 | region / organ_raw / site / location_source | `small-bowel` / (null) / `small-bowel` / `readme` |
| 17-18 | procedure / imaging | `capsule-small-bowel` / `white-light` |
| 19-20 | category / category_raw | `pathological-findings` / (null) |
| 21-22 | finding / finding_raw | `ulcer-3-10mm` (**expanded name, not `u3-10`**) / `U3-10` |
| 23-24 | finding_harmonized / finding_parent | `ulcer` / `ulcer` |
| 25 | finding_subtype | `3-10mm` |
| 26-27 | finding_harmonization / finding_in_image_vocab | `mapped` / `True` |
| 28 | findings_all | `ulcer` |
| 29 | class_counts_json | (null) |
| 35 | n_labels | `1` |
| 39-40 | label_confidence / is_negative | `high` / `False` |
| 47-51 | file_path / ext / exists / size / image_path | `DataCrohnIPI/imgs/01184.jpg` / `jpg` / `True` / `18706` / same |
| 55 | image_md5 | `a1f18bc1b2fa738e610a2ba89596722b` |
| 62-64 | group_id / group_kind / group_quality | `datacrohnipi\|b200-006` / `block-proxy` / `proxy` (images 1001-1200) |
| 65 | split_official | `fold-3` (**define: image is in the held-out set of CV round 3**) |
| 66 | dup_group_id | (null) |
| 67 | qa_flags | `split-leak-known` |
| 68 | extra_json | `{"native_code":"U3-10","disease_context":"crohns-disease","fold_semantics":"test-fold"}` |
| 69-70 | width / height | `320` / `320` |
| | has_mask / has_bbox | `False` / `False` |

A normal row (`00001.jpg`, `N`, fold 2): `category=normal`, `finding=normal`, `finding_raw=N`, `finding_harmonized=normal-mucosa`, `findings_all=normal-mucosa`, `is_negative=True`, `split_official=fold-2`, `finding_subtype`/`finding_parent` -> parent = `normal-mucosa`.

## 2. Columns that cannot be filled correctly / would mislead / are defined wrongly

### 2.1 Box convention (block "boxes and masks", last paragraph) - **wrong, must change**

Verified facts:
* see-ai: 23,033 boxes, continuous normalised values (6 decimals). Edges are not integers (2 % within 0.01 px = chance). Draft floor/ceil is the right idea for these (outer rounding; a box can grow by < 1 px per side). Edge handling is right when `x1 = 576.0` -> `xmax = 575`, but `x0 = -0.0`-like noise gives `-1` for 3 boxes -> clamp.
* EAD: 31,069 boxes, **100 % integer edges** (within 0.01 px, even at 1349x1079, 800x700, 675x540), i.e. the YOLO numbers are float round-trips of integer pixel boxes. floor/ceil then flips by 1 whenever the float lands just below/above the integer: `(0.365625-0.48625/2)*800 = 97.99999999999997` -> floor 97 instead of 98; `(cx+w/2)*W = 487.0000000000001` -> ceil-1 = 487 instead of 486. Disagreement with correct rounding: 7,408 boxes (24 %); 4 of 14,668 for 512x512 (powers of two are exact), 609/1,351 for 800x700, 1,255/2,818 for 675x540, 3,352/7,286 for 1349x1079.
* EAD index base: for the Phase-II data (99 frames + the 2 masked sequences = 169 masked images) the mask tight box (0-based, inclusive) equals `[round(x0)-1, round(y0)-1, round(x1)-1, round(y1)-1]` **on all four sides for 76/76 images** with a single instrument box (and exactly for blood/saturation/instrument in MP10058). I.e. the source boxes are 1-based inclusive (VOC style) and were exported as `cx=(xmin+xmax)/2W, w=(xmax-xmin)/W`. The draft formula keeps `xmin/ymin` one pixel too large. For the 2,200 `framesOnly` frames box vs mask could be compared only for 158 images with one instrument box (the `framesOnly` masks are resampled and noisy) and the offset is not constant there, so the 1-based rule is *verified for Phase II only* and assumed for `framesOnly`; record `bbox_index_base`/`bbox_convention_verified` in `extra_json`.

Replacement text I propose for the draft:
```
snap(v)  = round(v) if abs(v - round(v)) < 1e-3 else v          # kills float noise of integer-pixel sources
x0 = snap((cx-w/2)*W)   x1 = snap((cx+w/2)*W)    (same for y with H)
continuous YOLO (see-ai):          xmin = max(0, floor(x0))     xmax = min(W-1, ceil(x1)-1)
integer-derived YOLO, 1-based (EAD): xmin = max(0, round(x0)-1)  xmax = min(W-1, round(x1)-1)
the per-dataset adapter states which branch it uses and writes it into extra_json / bbox_source
```
After clamping 0 of 31,069 EAD boxes and 0 of 23,033 see-ai boxes are degenerate (`xmin > xmax`), so no extra rule is needed, but the adapter should assert `xmin<=xmax` (the draft rule gives 3 degenerate EAD boxes). Count of boxes touched by the clamp: EAD 657 (1-based `x0=0` boxes and the 13 slightly-outside boxes), see-ai 0 genuinely (3 noise cases).
`bboxes_json` items should additionally carry `native_id` and the original normalised `yolo` list: see-ai boxes are continuous so the pixel box is a lossy outer rounding (up to 2 px wider than the annotation), and `native_id` makes the file round-trippable (1 extra key, ~35 bytes/box, 23,033 + 31,069 boxes -> ~2 MB).

### 2.2 Multi-class rows (cols 21-23, 28-35, 39, `bbox_label`, `bbox_*`)

* **Col 21-23 `finding*` for a multi-class image is arbitrary unless a rule is written down.** I propose: primary class = most boxes, tie -> larger summed box area, tie -> lowest native class id; `finding_2` = next by the same order; classes 3..n only in `findings_all`; add `qa_flags=multi-class` so that nobody trains a single-label model on `finding` without noticing. (Alternative: null `finding` for multi-class rows - rejected because many tools key on `finding`.)
* Col 28 `findings_all`: good as defined (sorted distinct `finding_harmonized`). Col 29 `class_counts_json`: say explicitly that **keys are `finding_harmonized`** (the draft example is ambiguous) - for see-ai/EAD each native class maps to its own harmonized slug so nothing is merged.
* Col 35 `n_labels` = `len(findings_all)` is fine, but note it is *classes*, `n_boxes` is *instances*.
* Col 39 `label_confidence`: define for multi-class rows (min over classes).
* `bbox_label`: say "distinct **native** slugs" (the draft text is silent while `bboxes_json.label` is native).
* **`bbox_xmin..ymax` (union box) misleads for multi-class / many-box rows**: EAD rows have up to 156 boxes (mean 12) and the union is practically the frame; see-ai multi-class rows contain frame-sized stenosis/erythema boxes. Rule: fill only when `n distinct classes == 1`, else null; consumers use `bboxes_json`.
* Col 40 `is_negative`: see 5.4.

### 2.3 Mask columns for EAD2020's multi-page TIFFs

* Draft `annotation_format` has `mask-multipage-tif`; good, but the **page -> class mapping is not derivable from the file** (no metadata) and is **not** the bbox class order. The mapping comes from `class_list_semantic.txt` ("Instrument ", "Specularity", "Artefact", "Bubbles", "Saturation", "blood"; trailing blank/space, different spelling from `class_list.txt`) and I verified it independently against the boxes; 5-page files drop `blood`. It must be hard-coded in the adapter and written into `mask_encoding` (and `extra_json.mask_pages`).
* `mask_encoding` text for the three mask sets: Phase-II / sequences `tif-page>127 white=artefact`; framesOnly `tif-page>127, last pixel row zeroed (255 sentinel row in 1,050/2,370 pages; 524 foreground pages also carry non-binary values on 0.0-1.6 % of the pixels)`.
* `mask_foreground_pixels/_fraction`, `mask_tight_*`: define as **union over all pages** (pixel is foreground if any page > 127) and put per-page values in `extra_json` (`mask_page_px`, `mask_page_tight`). The union tight box says little but is well-defined; per-class is where the information is.
* `mask_in_bbox_fraction`: define as foreground of page k inside boxes of the *corresponding* class (union over pages). 1.0 for MP10058 with the corrected convention.
* `mask_json_bbox_max_diff_px`: not applicable (null); `mask_corner_pixel_removed`: `False` (the HK noise pixel does not exist here; the EAD artefact is the sentinel row, flag `mask-sentinel-row`).
* A mask row's labels must come from the **non-empty pages**, not from the parent image (draft HK rule "labels inherited"): the image row of MP10058 has 6 classes, its mask row 5; across the 474 `framesOnly` masks 16+14+7+7+1 pages are non-empty without a box of that class and 91+136+42+99+6 box-class/page pairs have an empty page.
* `has_mask` on the image row is true for 643 of 2,531 EAD images (474 framesOnly via md5 link, 99, 70).

### 2.4 `annotation_types` (col 10) / `annotation_format` (col 11)

* `class` should mean "the dataset ships a native image-level label". see-ai and EAD ship only boxes (labels are derived): `annotation_types=bbox`. Please state this in the definition; otherwise consumers filtering `class` find see-ai/EAD rows missing.
* `annotation_format` must accept the same `|`-list as `annotation_types` (image rows with box + mask: `yolo-txt|mask-multipage-tif`).

### 2.5 Other draft cells

* **Col 21 `finding`** definition ("kebab-case slug of the original finding text") fails for code labels (Crohn) - see finding C. Proposed wording: "slug of the dataset's native class *name*; when the native value is a code, the name from the dataset legend; `finding_raw` keeps the native value verbatim". Crohn: `normal`, `erythema`, `edema`, `aphthoid-ulceration`, `ulcer-3-10mm`, `ulcer-over-10mm`, `stenosis`.
* **Col 17-18 `procedure`/`imaging` value `mixed`**: valid only for rows that span several (clips); EAD single frames -> `unknown`.
* **Col 15 `location_source`**: see-ai has no README; location is known from the burned-in `PillCam SB3` text and the dataset concept. `dataset-constant` is right; no new value needed, but say so in the registry.
* **Col 27 `finding_in_image_vocab`**: for `image` rows it is always True (it counts itself). Say "evaluated against the other rows" or restrict to video/mask rows, otherwise it carries no information for see-ai/EAD/Crohn.
* **Col 56-58**: also use `video_id` + `frame_index` for the EAD sequence frames (232 rows): `video_id=1445-03`, `frame_index=21` from `1445-03_clipSB_avi_21` (as written in the file name; numbering starts at 0 for 1445-xx and `Pylseg2`, at 1 for `PYL-02`, at 168 for `PYL-N-02`; spacing unknown) and `group_id=ead2020-train|1445-03`.
* **Col 62 `group_id`** "null if none" is not safe for consumers (R6: "split by group_id"): a null group means "cannot be grouped", not "own group". State explicitly: rows with `group_kind=none` must be treated as ungroupable; consumers choose how to split them. For EAD `framesOnly` I propose `cluster-proxy` (4.8).
* **Numbering**: the draft says 107 columns but numbers 1-82 + an unnumbered block; "71-82 (+ any existing ones)" names only 10 video columns for 12 slots. Please list the final column order explicitly in the schema.

## 3. Information with no column, and `extra_json` keys

| dataset | key | should it become a column? |
|---|---|---|
| see-ai | `export_batch` (1 = images 1-17,085, black level 16; 2 = 17,086-18,481, black level 0, 8.5 % vs 35 % negatives) | **a generic `domain_id` column (free text) would serve see-ai batch, PolypGen centre, EAD size-run, Kvasir-Capsule video device**; each is a shortcut / domain-shift variable you want to stratify on |
| see-ai | `native_class_ids`, `black_level` | no (`native_id` inside `bboxes_json`) |
| see-ai | image number | = `item_id` |
| all three | **device** (see-ai `PillCam SB3` read from the overlay; Kvasir-Capsule Olympus; Crohn unknown; EAD unknown) | **yes - `device` column** (draft only mentions "device names" in `extra_json`; it is shared by at least 3 datasets) |
| EAD | `origin_subset`, `bbox_index_base`, `bbox_convention_verified`, `canonical_folder`, `other_copies`, `native_class_ids` | `origin_subset` -> `source_subset` (proposed); rest `extra_json` |
| EAD | sequence name + frame number | `video_id` + `frame_index` + `group_id` (existing columns) |
| EAD masks | `mask_pages`, `mask_page_px`, `mask_page_tight`, sentinel info | `extra_json` (+ `mask_encoding` text) |
| Crohn | `native_code`, `disease_context`, `fold_semantics` | `extra_json` |
| Crohn / PolypsSet / HK | official fold number | `split_official` (exists) |
| all | burned-in text | `qa_flags=burned-in-text` (see-ai: the `PillCam SB3` overlay was present on every image I looked at, ~30 across both export batches, so set it on all rows; EAD: only some frames, not computed - do not set) |

Lost without a place: the 14 Crohn orphan images (logged per R2, fine), the see-ai `all_annotation.csv` redundancy (verify only), the five see-ai prediction videos (not ingested, fine).

## 4. Opinions on rules and decisions

1. **R1 (row units)**: agree. Boxes inside the image row works for see-ai and EAD. 643 EAD mask rows are acceptable only with the label rule of 2.3 (mask labels from pages) - otherwise they are pure duplicates.
2. **R2 (duplicates)**: agree (EAD canonical `allDetection_training/bbox_images`, 2,531 rows; masks from the other folders; see-ai keeps all 18,481). Add two flags for see-ai: **`dup-label-conflict`** (class counts differ: 28 pairs = 56 images; includes the one positive/negative pair) and **`dup-box-conflict`** (same class counts, different coordinates: 84 pairs = 168 images); 9 pairs have identical txt. `dup_group_id`: specify the prefix length (I suggest 16 hex chars). In training, keep one member per `dup_group_id` or both in one fold.
3. **R3 (negatives)**: agree. `background` + `no-lesion-annotated` for see-ai empty txt is acceptable (better than my `no-annotated-finding`, symmetric with `no-polyp-annotated`). Crohn `N` -> `normal` / `normal-mucosa` agreed.
4. **R4**: n/a to my datasets.
5. **R5 (never guess location)**: agree. EAD `region=unknown` only; no bladder/colon tagging.
6. **R6 (splits)**: agree, with the addition that null `group_id` means ungroupable, and `split_official` for Crohn is known to leak (flag `split-leak-known`: 99 of 127 near-duplicate labelled pairs sit in different folds).
7. **R7**: n/a.
8. **Open decision 8 (contiguous-block `group_id`): acceptable, but it needs a spec.** Evidence: see-ai label agreement between frames `k` apart (both positive, share a class) falls from 0.87 (k=1) to 0.29 (k=100), 0.22 (k=500) = baseline 0.21; Crohn same-label probability 0.85 (k=1) -> 0.40 (k=100) = baseline 0.40, lesion-vs-lesion 0.78 -> 0.18 (k=100, baseline 0.20). Proposed definition: `b500` for see-ai (`ceil(image_number/500)`, 37 blocks) and `b200` for Crohn (`ceil(file_number/200)`, 18 blocks), **then merge blocks that contain the two members of a byte-identical pair (union-find)**: see-ai -> 31 groups, largest component 4 blocks = 2,000 images (without the merge, 121 exact duplicate pairs - gaps up to 15,683 - cross block boundaries). `group_quality=proxy`. For EAD `framesOnly`: numbering alone is not enough (only 53-61 % of near-duplicate partners lie within 50 numbers, 57-68 % within 200); `group_kind=cluster-proxy` (new value) = connected components of 24x24 RGB thumbnail cosine > 0.98 (1,373 components, largest 127 images), `group_quality=proxy`; 99Frames -> `none`; sequences -> `sequence`/`exact`. If the coordinator prefers fewer kinds, give `framesOnly` `group_kind=none` and document the leakage.
9. **Open decision 2 (capsule `region=small-bowel`, `site=small-bowel`)**: accept for see-ai and Crohn (`location_source=dataset-constant` / `readme`). Both are small-bowel capsule sets; per-image segment unknown. Early see-ai frames may come from stomach/oesophagus (e.g. image00001 is non-diagnostic); not identifiable, accept.
10. **Open decision 3 (EAD2020)**: `region=unknown`, `category=artefact` accepted; `blood-in-view` for `blood` accepted; `instrument` fine as an artefact-category finding. Add: (a) `is_negative` semantics (5.4); (b) EAD stays in the table only as quality/artefact data: all 2,531 rows have `category=artefact`, so any pathology consumer excludes them by category; (c) licence CC BY-NC-SA: non-commercial and share-alike obligations should be visible via `license` (col 9) since the merged table derives labels from it; (d) every EAD row has `non-gi-possible` (bladder frames exist, not identified). I would **include** EAD2020 (3,174 rows) but not as a pathology source.
11. **Open decision 4 (`lymph-follicle`, `vein`, `foreign-body`)**: `pathological-findings` + `label_confidence=low` acceptable as a default, with one addition: add `qa_flags=benign-variant` on `lymph-follicle` (6,788 boxes in 1,788 images = the largest see-ai class; 1,594 single-class images) and `vein`, otherwise a "pathological vs normal" model silently learns normal lymphoid tissue as disease. `label_confidence` is about the mapping, not clinical significance. `foreign-body` as pathological: acceptable (listed as lesion class in see-ai and Kvasir-Capsule).
12. **Open decision 5**: `polyp-like-lesion` with `finding_parent=polyps` is acceptable provided consumers always read `finding_parent` together with `region`; `polyp-like` in see-ai includes non-polyp protrusions, so it should not be pooled blindly with colonic polyps.
13. **Open decision 6**: accept `angiectasia` for see-ai `angiodysplasia` (keep `finding_raw=angiodysplasia`, `finding_harmonization=mapped`); `aphthoid-ulceration` separate from `erosion` with `finding_parent=ulcer` accepted; Crohn `U3-10`/`U>10` -> `finding_harmonized=ulcer`, `finding_subtype=3-10mm` / `gt-10mm`, `finding_parent=ulcer`, with `finding` = `ulcer-3-10mm` / `ulcer-over-10mm` (C). `finding_subtype` for `AU` stays null (the dataset does not give a size).
14. **Open decision 7 (mask rows)**: keep parity (1,000 + 612 + 196 + 643). For EAD it adds only the per-page label set and stats; if the coordinator wants fewer rows, EAD is the dataset where folding masks into the image row loses least. Document "filter `source_type=='image'` when counting images" prominently.
15. **R2 for Crohn orphans** (14 images without CSV row): agree they are not rows; log them.

## 5. Wrong / ambiguous / painful for the adapter

1. **Box formula** (finding A, 2.1) - must be replaced before any adapter is written; it silently damages 24 % of EAD boxes.
2. **Columns 71-82 and the unnumbered mask/box block**: no explicit order/names for 2 video columns; "(+ any existing ones)" is not implementable. The final column order should be one fenced list.
3. **Col 27 `finding_in_image_vocab`** is tautological for image rows (2.5).
4. **Col 40 `is_negative` is False for every EAD row**, which reads as "positive". A pathology consumer must use `category=='pathological-findings'` as the positive definition; say so in the definition, or make the column null for `artefact` rows. (HK anatomical/quality/therapeutic rows have the same issue.)
5. **Col 6 `label_source` multi-file separator** is not defined (`|` assumed); EAD and see-ai need two files (labels + class list / CSV).
6. **Col 62-64** unspecified algorithm for proxy groups; **col 66** prefix length unspecified.
7. Dataset names: registry names (`ead2020-train`, `datacrohnipi`) differ from folder names (`EAD2020_train`, `DataCrohnIPI`); `file_path` must keep the folder names, `dataset` the registry name - fine, but the draft should say it once.
8. EAD adapter pains (all solvable but non-obvious): md5 map for the 474 renamed `framesOnly` mask images (no filename relation; `image_md5` for all rows is anyway required); mask page order differs from box class order and from the file spelling; two mask page counts; `framesOnly` sentinel rows; masks and boxes live in different folders from the canonical images; README counts disagree with the data (642 / 573 vs 643 masks; 233 vs 232 sequence frames).
9. see-ai adapter pain: `all_annotation.csv` has a BOM, CRLF, a second header row and a final sum row (wrong by the class id); use the `.txt` files as source, the CSV only for the id -> name map and a count cross-check (0 mismatches over 18,481 x 12).
10. Crohn: `Fold` semantics (test fold) must be written into `split_official`'s definition; folds are random per frame and leak.

## 6. Verification log (scripts, all read-only)

`boxconv.py` (edge integrality + draft vs rounding), `boxmask.py` / `fo.py` (box vs mask offset, Phase-II exact, framesOnly inconclusive), `min01.py`, `ex_see2.py` / `ex_ead2.py` / `inbox.py` (worked examples, per-page mask stats, in-box fraction 1.0), `degen.py` (clamp/degenerate counts), `lag.py` / `comp.py` / `lag2.py` / `fo_lag.py` (block size, duplicate union-find, near-duplicate lags). One caveat on the near-duplicate thumbnail statistics for see-ai (16x16, shared overlay) - I did not use them, only label-agreement-vs-lag.
