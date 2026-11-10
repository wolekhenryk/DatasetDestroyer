# Report: `data_to_merge/PolypsSet/`

Reader 2 of 3. Everything below was measured with scripts (scratchpad `.../scratchpad/PolypsSet/`, run with `python -I`); nothing under `data_to_merge/` was modified.
Evidence tags: **[measured]** = computed from the files, **[inferred]** = deduced from the data (no README ships with the dataset), **[literature]** = web search / background knowledge, not verifiable on disk.

## 1. Identity

| item | value |
|---|---|
| name | **PolypsSet** (splits `train2019` / `val2019` / `test2019`) |
| origin **[inferred + literature]** | Li K., Fathan M.I., Patel K., et al., *"Colonoscopy polyp detection and classification: Dataset creation and comparative evaluations"*, **PLOS ONE 2021** (arXiv 2104.10824, PMC8370621). NOT "Scientific Data" as guessed in the task. Evidence on disk: `<path>` fields of the XMLs point to `/scratch/mfathan/Thesis/...` and `/Users/krushipatel/Desktop/...` (authors Fathan, Patel). The paper merges public polyp video datasets (MICCAI/GIANA 2017, CVC-ColonDB, a GLRC-like NBI set, KUMC 80 videos) plus own annotations, adding a histology class to each box. I could not confirm the paper's own image/video totals; the numbers below are what is on disk. |
| modality **[inferred]** | Colonoscopy video frames. Mostly white light; sub-sets named `NBI` (`nbi_adenoma`, `set1_hyperplastic`, see 3) are narrow-band; some `videos80` frames are blue/cyan (NBI/BLI-like) - modality is not recorded per file. |
| licence / readme | **No README, no licence file** in the folder. Licence of the paper's data release unknown (the parts come from several public sources with their own terms). |
| size on disk | 2.6 GB (train 1.9 GB, val 333 MB, test 326 MB) |
| files | 76,604 incl. 8 `.DS_Store` junk files; **37,899 `.jpg`**, **38,697 `.xml`**, nothing else |
| image format **[measured]** | all 37,899 are baseline JPEG, JFIF, RGB, decode OK (no corrupt file), 6 KB - 127 KB each (median 85 KB) |

### Layout (counts measured)

```
PolypsSet/
  train2019/Image/<n>.jpg            28,773 flat files, n = 1..28773 (numbering is RANDOM, not temporal)
  train2019/Annotation/<n>.xml       28,773 flat files, 1:1 with the images
  val2019/Image/<k>/<n>.jpg          17 sub-folders (k = 1..17), 4,254 images ; <n> = frame order inside the case
  val2019/Annotation/<k>/<n>.xml     17 sub-folders, 4,630 XMLs  (376 XMLs without image)
  test2019/Image/<k>/<n>.jpg         22 sub-folders (k = 1..24 minus 2, 7), 4,872 images
  test2019/Annotation/<k>/<n>.xml    22 sub-folders, 5,294 XMLs  (422 XMLs without image)
```
Sub-folder `<k>` of val/test is **one video/case each** (39 sub-folders = 39 distinct cases, no case spans two folders; within a folder `<n>` runs 1..N in temporal order, correlation of `<n>` with the original frame number 0.9999). The sub-folder numbering is arbitrary (not the original video id). `train2019` has no sub-folders, so the case can only be recovered from the XML (see 6).

## 2. Annotation sources

Only one annotation source: **Pascal-VOC XML**, one XML per image (`Annotation/.../<same stem>.xml`). 38,697 XMLs, all parse, UTF-8/ASCII, LF, no BOM, pretty-printed with 4-space indent.
Tags (always the same): `annotation > folder, filename, path, source>database, size>(width,height,depth), segmented, [object>(name, pose, truncated, difficult, bndbox>(xmin,ymin,xmax,ymax))]*`. The `object` element is missing in 1,927 XMLs (= no annotated polyp, see 5).

| field | meaning | distinct values |
|---|---|---|
| `folder` | **original source folder name of the author's machine - NOT a reliable key** (e.g. `3`, `Original`, `hyperplastic_08_NBI`, `adenoma`, `adenoma_01`) | many |
| `filename` | original filename of the source frame (`245.png`, `1.bmp`, `adenoma_163.jpg`, ...) - extension does **not** match the shipped `.jpg` | many |
| `path` | absolute path on the authors' machines (7 shapes, see 3). Contains user names (`mfathan`, `krushipatel`). **The key to the provenance and the case id.** | 7 patterns |
| `source/database` | `Unknown` (34,962) or empty string (3,735 = the NBI-adenoma group) | 2 |
| `size/width,height,depth` | stored as text; depth always `3` (38,697). **width/height equal the real JPEG size for 37,899/37,899** [measured] | 5 sizes |
| `segmented` | always `0` | 1 |
| `object/name` | **polyp histology class**: `adenomatous` / `hyperplastic` (see 5) | 2 |
| `object/pose` | always `Unspecified` (36,771) | 1 |
| `object/truncated`, `difficult` | always `0` (36,771) | 1 |
| `bndbox/xmin,ymin,xmax,ymax` | integer pixels as text; **leading space** in `ymin`, `xmax`, `ymax` for 33,036 of 36,771 objects (`<ymin> 113</ymin>`), none for `xmin` - cast with `int(s.strip())` | ints |

No NA-like strings, no non-integer coordinates (0 contain `.`), no empty coordinate.

## 3. What each annotation IS

* **Bounding box** (Pascal-VOC `bndbox`), one **axis-aligned corner box** `xmin,ymin,xmax,ymax`, **pixel units of the shipped JPEG, origin top-left**, x to the right. The image size in XML = the JPEG size, so no rescaling is ever needed.
* Value ranges [measured, 36,771 boxes]: xmin 1..645, ymin 0..522, xmax 61..731, ymax 24..564; xmin<xmax and ymin<ymax in 100 %; no negative value; **no box exceeds the image** (xmax==W for 66 boxes, ymax==H for 354 boxes, never above); xmin is never 0, ymin==0 for 15 boxes. => the convention is **Pascal-VOC (probably 1-based inclusive) with a +-1 px ambiguity**. I overlaid boxes on images of every sub-source (montage inspected): they sit exactly on the lesions. Safest handling: treat `[xmin,xmax] x [ymin,ymax]` as pixel edges and clip to `[0,W] x [0,H]`; the error is <= 1 px.
* Box size (all 36,771 boxes incl. orphan XMLs): width median 133 px (5..631), height median 128 px (12..527); area fraction of the image median 6.7 % (0.09 %..88 %); 51 boxes > 50 % of the image, none > 90 %; 2 boxes < 8 px wide.
* **No masks / polygons / keypoints** exist. No image-level label file: the image-level class is implied by the box name; negatives are XMLs without `object`.
* Provenance (from `<path>`, 7 shapes; regexes below) - this is how the 6 original sub-datasets are recognisable **[measured]**:

| `grp` (my name) | `<path>` shape | XML count | JPEG count | cases | image size | boxes (adenomatous / hyperplastic) | neg frames | probable source **[inferred]** |
|---|---|--:|--:|--:|---|---|--:|---|
| `videos80` | `.../Extracted/80_Videos_Frames/{pretest,posttest}/<vid>/<n>.jpg` | 24,961 | 24,412 | 76 | 592x464 (15,728), 544x448 (8,684) | 12,106 / 11,632 | 674 | KUMC "80 videos" (pre-test + post-test sets) |
| `miccai2017_train` | `.../new_dir/Dataset/Image/MICCAI2017/train/<N>/Original/<n>.bmp` | 4,830 | 4,798 | 16 | 384x288 | 1,610 / 2,476 | 712 | MICCAI/GIANA 2017 training videos |
| `miccai2017_test` | `.../Extracted/MICCAI2017_Test/test/<N>/<n>.png` | 2,479 | 2,478 | 7 | 384x288 | 1,625 / 368 | 485 | MICCAI/GIANA 2017 test videos |
| `nbi_adenoma` | `/Users/krushipatel/Desktop/NBI-Dataset/NBI-Frames/adenoma_<NN>` (a folder, no file name; `filename` = `adenoma_<n>.jpg`) | 3,735 | 3,676 | 24 | 768x576 | 3,676 / 0 | 0 | NBI adenoma videos |
| `set1_hyperplastic` | `.../Extracted/Set1_Frames/hyperplastic/hyperplastic_<NN>_NBI/<n>.bmp` | 2,395 | 2,241 | 15 | 768x576 | 0 / 2,194 | 47 | NBI hyperplastic videos |
| `cvc300` | `.../Extracted/CVC-300/<N>/<n>.bmp` | 297 | 294 | 15 | **574x500** | 223 / 71 | 0 | **CVC-ColonDB** (300 frames / 15 short videos) - NOT CVC-ClinicDB |
| **total** | | **38,697** | **37,899** | **153** | 5 sizes | **19,240 / 16,741** | **1,918** | |

(For the NBI group the `folder` field is useless; the case is the last component of `<path>`.)
Case-id regexes: `80_Videos_Frames/(pretest|posttest)/(\d+)/(\d+)\.jpg`, `MICCAI2017/train/(\d+)/Original/(\d+)\.bmp`, `MICCAI2017_Test/test/(\d+)/(\d+)\.png`, `NBI-Frames/(adenoma_\d+)$`, `Set1_Frames/hyperplastic/(hyperplastic_\d+_NBI)/(\d+)\.bmp`, `CVC-300/(\d+)/(\d+)\.bmp`. 100 % of 38,697 XMLs match exactly one pattern; case = (group, pre/post, id).

## 4. LOCATION (anatomy)

Dataset-wide constant: **colon / lower GI tract** (colonoscopy; the paper and every source dataset are colonoscopy polyp sets). Basis: file provenance + paper title; **no per-file segment (cecum, rectum, ...) is recorded anywhere** -> site = "colon, unspecified". Confidence high for region, none for sub-site.

## 5. FINDING (content)

| native value | where | images (shipped JPEGs) | boxes | category | note |
|---|---|--:|--:|---|---|
| `adenomatous` | `object/name` | 19,240 | 19,240 | pathological | polyp with adenomatous histology (neoplastic) |
| `hyperplastic` | `object/name` | 16,741 | 16,741 | pathological | polyp with hyperplastic histology (non-neoplastic) |
| *(no `object`)* | XML without object | **1,918** (train 1,725, val 40, test 153) | 0 | negative / background | "no annotated polyp in this frame" |

* Images with a box: **35,981** (every one has exactly **1** box); images without box: **1,918**. Images with >= 2 boxes: **0** on shipped images (a single orphan XML has 2 boxes). So `boxes-per-image` = {0: 1,918; 1: 35,981}.
* **The histology class is a property of the case (video), not of the frame**: 0 of 153 cases contain both classes (adenomatous 85 cases, hyperplastic 68). `nbi_adenoma` is all adenomatous, `set1_hyperplastic` all hyperplastic.
* Per split (shipped images; boxes): train 27,048 (14,269 adenomatous / 12,779 hyperplastic) + 1,725 negatives; val 4,214 (2,081 / 2,133) + 40 neg; test 4,719 (2,890 / 1,829) + 153 neg. Cases: train 114, val 17, test 22.
* **Negatives are not a separate class or folder**: they are frames of the same videos where no polyp was boxed (can be sections where the polyp left the view, or - risk - missed annotations). Concentrated in `miccai2017_*` (1,197) and `videos80` (674); 0 in `nbi_adenoma`/`cvc300`. 52 of 153 cases have at least 1 negative; in the extreme `miccai2017_test` case 1 has 67 % negatives. Clinically they are "no polyp annotated", **not** verified normal mucosa.
* No instrument / artefact / quality class.

Orphans (images missing but XML present): **798 XMLs without JPEG** (val 376, test 422; all of them in val/test, none in train) with 790 boxes (adenomatous 327, hyperplastic 463) and 9 empty XMLs. They are scattered through the sequences (single frames and short runs), so the delivered val/test are **sub-sampled copies** of the original val/test; the XMLs are unusable without the images. There is **0 JPEG without XML**.

## 6. Linking keys, grouping ids, splits

* **Image <-> label**: identical relative path with `.jpg`->`.xml`, `Image`->`Annotation` (`split/<sub>/<stem>`). Matched 37,899; unmatched JPEG 0; unmatched XML 798 (above). No duplicated keys. XML `size` == JPEG size 37,899/37,899.
* **Official splits: yes** - the three top folders. Frames of one video are never split across them [measured: reconstructing the case id from `<path>`: 153 cases, 0 cases in more than one split]. => the shipped split is **case-wise (video-wise)**.
* **BUT leakage inside the shipped split** [measured, md5 + 32x32 thumbnail NN]:
  * `videos80|posttest|16` (449 train frames) and `videos80|pretest|11` (443 train frames) are the **same video**: 442 byte-identical frame pairs; both in **train**, so no val/test leakage, but they count as two cases.
  * `cvc300||11` (**test**, 18 frames) and `cvc300||13` (**train**, 16 frames): **7 byte-identical images -> 7 test images are also in train**.
  * Excluding those, no other pair of cases from different splits has a near-duplicate (nearest-neighbour RMSE on 32x32 gray thumbnails, all same-size pairs of images from different cases; 901 images below RMSE 4, all explained by the two case pairs above; val shows none).
* **Grouping id for own splits**: `case_id` = `grp|phase|id` from `<path>` (153 values; merge the duplicate pairs above into one group). `train2019` file numbers are random (corr with frame number ~0; train runs of the same case are not contiguous) -> never split train by file number. For val/test the folder number also identifies the case.
* Frames come from videos: yes. Per case 4..557 images (median 250); consecutive frames are near-identical -> **split by case, never by frame**. Frame order within a case is only recoverable for val/test (`<n>`), and for all splits from `fno` in `<path>` where it exists (`nbi_adenoma` has `adenoma_<n>.jpg` in `filename`).
* Patient id: **unknown**. `pretest`/`posttest` of `videos80` may contain the same patient (one duplicated video proven); NBI/Set1/MICCAI case ids are video ids.

## 7. Technical facts

| size (WxH) | images | groups |
|---|--:|---|
| 592x464 | 15,728 | videos80 |
| 544x448 | 8,684 | videos80 |
| 768x576 | 5,917 | nbi_adenoma, set1_hyperplastic |
| 384x288 | 7,276 | miccai2017_* |
| 574x500 | 294 | cvc300 |

All RGB JPEG; no EXIF; no corrupt files. Frames are octagonal/rounded endoscope views with **black borders**; the NBI sub-sets (and some MICCAI frames) show **text overlays** (patient-info labels, "NBI" tag) at the left/right edge - visible in the montage; they are baked into the pixels. Images are re-encoded JPEGs of frames originally `.bmp/.png/.jpg`. Read time: parsing 38,697 XMLs + opening 37,899 JPEG headers = 11 s; md5 + 32x32 thumbnails of all images (12 cores) = 5 s.

## 8. Duplicates and overlap

Tested **[measured]**:
1. md5 of all 37,899 JPEGs: **37,437 distinct**; 461 duplicate groups (923 files): 454 inside train, 7 train+test (all `cvc300` 11/13), none involving val. 449 of the groups join different cases (442 = videos80 posttest/16 vs pretest/11, 7 = cvc300 11/13), 12 are identical frames inside one case (static scenes).
2. Thumbnail NN (32x32 gray, RMSE, nearest image of any *other* case with the same pixel size; median NN distance 25, genuine copies < 4, only 27 more images fall in 4..8): 901 images below 4 - all explained above (train-train 887, test<->train 7+7, val none).
3. **Against CVC-ClinicDB** (612 frames, 384x288): same-size candidates = the 7,276 `miccai2017_*` images; all-vs-all NN over every PolypsSet image regardless of size: **min RMSE 12.3, 0 pairs < 8** (visual check of the 3 closest pairs: different frames). md5 intersection PNG/TIF vs JPEG: 0 (formats differ). => **no CVC-ClinicDB frame is in PolypsSet** (same-video different frames cannot be excluded, e.g. GIANA videos come from the same clinic family; nothing found at frame level).
4. **Against polypgen-ninja** (8,037 frames): no image size is shared (PolypGen sizes 1350x1080, 1245x1050, ... vs PolypsSet five sizes), md5 intersection 0, thumbnail NN min RMSE 17.2, 0 pairs < 8 => **no overlap**.
5. `cvc300` is **CVC-ColonDB** (574x500, 15 videos): it is a different dataset from CVC-ClinicDB (not tested against ETIS-Larib or Hyper-Kvasir; PolypsSet has no 1225x966 images, so a same-resolution ETIS copy is impossible, a resized one not tested). Hyper-Kvasir (`out/`) not tested.

## 9. PROPOSED MAPPING to the unified table

**(a) Row unit**: `source_type = image`, one row per shipped JPEG: **37,899 rows** (train 28,773, val 4,254, test 4,872). The XML box is attached to the image row (max 1 box per image) -> **no new row type needed** (`has_bbox` True for 35,981 rows, `n_boxes` 1; 1,918 negative rows have `has_bbox=False`, `n_boxes=0`, **not null**). Do not create rows for the 798 orphan XMLs (log them separately if wanted).

**(b) Native class -> unified label**

| native | count (images) | region | site | category | finding slug | confidence |
|---|--:|---|---|---|---|---|
| `adenomatous` | 19,240 | lower-gi-tract | colon | pathological-findings | `polyps` (+ new `polyp_histology = adenomatous`) | high (class), medium (histology is not in the 4-way finding vocabulary of Hyper-Kvasir; keep both) |
| `hyperplastic` | 16,741 | lower-gi-tract | colon | pathological-findings | `polyps` (+ `polyp_histology = hyperplastic`) | high / medium |
| no object | 1,918 | lower-gi-tract | colon | **new category `normal` / `background`** | new slug `no-polyp-annotated` (NOT `normal-mucosa`) | medium: frames of polyp videos with no box; may contain unannotated polyp |

**(c) Columns**: apply: `sample_id` (`image:ps-<split>-<sub>-<stem>`), `source_type`, `source_dataset`, `label_source` (`Annotation/**/*.xml`), `label_level=image`, `row_description`, `item_id`, `file_path/ext/exists/size`, `image_path`, `region`, `organ_raw`, `category`, `category_raw`, `finding*`, `width`, `height`, `has_mask=False`, `has_bbox`, `n_boxes`, `bboxes_json`, `bbox_label`, `bbox_xmin..ymax` (union = the single box; same corner format as the Hyper-Kvasir JSON, so no conversion except noting the inclusive/exclusive ambiguity), `annotation_source`. Do not apply: all video columns, `seg_stem`, `parent_image_sample_id`, `mask_*`, `image_md5` (optional), `bbps_*`, `finding_2*`, `dir_*` (could be filled with split/sub folder). **NEW columns needed**: `dataset_name`, `split_official` (train/val/test), `case_id`, `sub_source` (the 6 `grp` values), `sub_source_path` (the raw `<path>`), `frame_no`, `polyp_histology` (adenomatous/hyperplastic/NA), `is_negative`, `bbox_format` (`voc_corner_px_top_left`), `bbox_xmin_norm..` (normalised by W/H, optional), `modality` (`WLI`/`NBI`/`unknown`; NBI for `nbi_adenoma`,`set1_hyperplastic`, unknown for others), `dup_group_id` (md5 / the two duplicate case pairs), `has_overlay_text`.

**(d) To read/compute**: nothing heavy. XML + header pass 11 s; md5 4.6 s (all images) - both already measured; frame numbers/case ids from `<path>` regexes (instant).

## 10. Pitfalls and open questions

1. Case ids exist **only in the XML `<path>`** (train is flat and shuffled). Without parsing them a random split leaks neighbouring frames.
2. Shipped split leaks: 7 `cvc300` images (test vs train) and the duplicated video pair `posttest/16` = `pretest/11` (both train). Recommend dropping the 7 test images (or moving case `cvc300||11` to train) and merging the video pair into one group.
3. 798 XML-only orphans (val/test): the dataset copy is not the complete release; counts from the paper will not match.
4. Negatives (1,918) are only "no polyp annotated"; treat with care when pooling with other datasets' "normal" classes. Histology (`adenomatous`/`hyperplastic`) is per case, not verified per frame; it does not exist in the other datasets -> the unified class stays `polyps` with an extra column.
5. Box convention: Pascal-VOC with a +-1 px ambiguity (xmax==W allowed); strip the leading spaces in the XML numbers; `<filename>` extension and `<path>` are not the shipped file.
6. `<path>` contains local user names (`mfathan`, `krushipatel`) - do not copy this column verbatim into a published table.
7. `cvc300` is CVC-ColonDB, not ClinicDB; `miccai2017_*` are GIANA-2017 videos; overlap with other polyp benchmarks (ETIS, CVC-ClinicDB videos, Kvasir-SEG) was only tested against the two sibling datasets here.
8. Open questions: is the exact original val/test (with the 798 images) available? Should NBI frames be flagged `modality=NBI` and pooled with white-light polyps? Is `no-polyp-annotated` acceptable as a negative class?
