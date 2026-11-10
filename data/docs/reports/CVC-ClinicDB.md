# Report: `data_to_merge/CVC-ClinicDB/`

Reader 2 of 3. Scripts: scratchpad `.../scratchpad/CVC-ClinicDB/` (run with `python -I`; nothing under `data_to_merge/` was modified).
Tags: **[measured]** computed from the files, **[inferred]** deduced, **[literature]** background knowledge, not verifiable on disk.

## 1. Identity

| item | value |
|---|---|
| name | **CVC-ClinicDB** (Computer Vision Center + Hospital Clinic, Barcelona; Bernal et al., *WM-DOVA maps for accurate polyp highlighting in colonoscopy*, 2015) **[literature]**. Confirmed on disk by the TIFF `Copyright` tags: originals "Copyright Hospital Clinic, Barcelona, Spain ... only permitted for research and educational purposes", masks "Copyright Computer Vision Center, Barcelona, Spain ...". |
| modality | white-light colonoscopy still frames extracted from video sequences **[literature + inferred from the images]** |
| licence / readme | **No README.** Licence statement only in the TIFF copyright tag: research and educational use only. |
| size on disk | 317 MB (`PNG/` 54 MB, `TIF/` 263 MB) |
| files | 2 `.csv`, 1,224 `.png`, 1,224 `.tif`, 3 `.DS_Store` (junk) |

```
CVC-ClinicDB/
  class_dict.csv              3 lines
  metadata.csv                613 lines (header + 612)
  PNG/Original/<id>.png       612   384x288 RGB, 8-bit
  PNG/Ground Truth/<id>.png   612   384x288 RGB (3 identical channels), the polyp mask
  TIF/Original/<id>.tif       612   same pixels as PNG/Original, uncompressed TIFF (non-standard, see 7)
  TIF/Ground Truth/<id>.tif   612   same pixels as PNG/Ground Truth (1 channel)
```
`<id>` = frame id 1..612 (no zero padding, so `ls` order is 1, 10, 100, 101, ...).

## 2. Annotation sources

### 2.1 `metadata.csv`
Comma-separated, UTF-8, **CRLF**, no BOM, header + **612 rows**, trailing CRLF at the end. No quoting needed, no whitespace issues (0 cells differ from their stripped value), no empties, no duplicates.

| column | meaning | dtype / values |
|---|---|---|
| `frame_id` | image number = file stem; unique; contiguous **1..612** | int |
| `sequence_id` | video sequence the frame belongs to; **29 distinct values, 1..29**, 6-26 frames each (mean 21.1, median 22) | int |
| `tif_image_path`, `tif_mask_path` | `TIFF/Original/<id>.tif`, `TIFF/Ground Truth/<id>.tif` | **the folder on disk is `TIF/`, not `TIFF/` -> 0 of 1,224 TIF paths resolve as written** (resolve after replacing the prefix; 612/612 each) |
| `png_image_path`, `png_mask_path` | `PNG/Original/<id>.png`, `PNG/Ground Truth/<id>.png` | all 1,224 resolve |

Rows are sorted as strings by `frame_id` (1, 10, 100, ...), not numerically. Matching metadata <-> disk: for each of the 4 folders, 612 files = 612 metadata rows, **0 files not in metadata, 0 metadata rows without file** [measured].
Frames per sequence (all `frame_id` ranges contiguous; sequences are consecutive blocks of ids): 1: 25 (ids 1-25), 2: 25, 3: 17, 4: 11, 5: 25, 6: 23, 7: 25, 8: 26, 9: 22, 10: 6, 11: 22, 12: 25, 13: 25, 14: 20, 15: 20, 16: 25, 17: 21, 18: 20, 19: 25, 20: 20, 21: 19, 22: 19, 23: 12, 24: 25, 25: 25, 26: 18, 27: 25, 28: 20, 29: 21.

### 2.2 `class_dict.csv`
CSV, CRLF, 3 lines: `class_names,r,g,b` / `background,0,0,0` / `polyp,255,255,255`. It is the (generic, Kaggle-style) colour legend of the mask: **background = black, polyp = white**. It contains no per-image information.

## 3. What the annotation IS

* **Binary segmentation masks, one per frame** (`Ground Truth/<id>.*`), **semantic** (all polyp pixels of the frame in one mask; separate polyps are just separate blobs).
* **Encoding [measured, all 612 PNG masks]**: RGB PNG with 3 identical channels (612/612); **polyp = 255 (white), background = 0** (polarity confirmed visually on overlays: red overlay sits on the polyp). **Not strictly binary**: 474 masks contain only {0,255}; **138 masks contain additional low grey values** (91,043 px of 67.7 M, 0.13 %; typically values 2-64, e.g. 11 in a 9,029-px zone outside the endoscopic image circle; max value among them 226; only **32 px** are in 128..254). => binarise with `> 127` (identical to `== 255` except for those 32 px). Foreground never touches the image border.
* PNG and TIF masks are **identical pixel-for-pixel including the noise** (612/612).
* Mask statistics: foreground area median 7,558 px (min 373, max 54,148), fraction of the frame median 6.8 % (min 0.34 %, mean 9.2 %, max 49 %); tight box of the foreground median 106 x 102 px (23..313 x 22..270). Connected components (>127, 8-connected, checked at 1/4 resolution): 1 component in 574 frames, 2 in 34, 3 in 4 (frames from 8 sequences, e.g. ids 70-77, 547-571) -> some frames have several lesions or small extra blobs (frame 75 has tiny extra blobs next to the main polyp).
* **No bounding boxes, polygons, class labels, histology, polyp size or free text are shipped** - boxes would have to be derived from the masks.

## 4. LOCATION (anatomy)

Dataset-wide constant: **colon / lower GI tract** (colonoscopy polyp dataset; the images show colonic mucosa). Source: dataset identity [literature] + image inspection. **No segment (cecum, sigmoid, rectum) per frame is available.**

## 5. FINDING

| class | frames | note |
|---|--:|---|
| polyp (mask non-empty) | **612 / 612** | every frame contains a polyp: 0 empty masks (min 373 foreground px) |
| normal / negative frames | **0** | no polyp-free frame is included |
| instrument / artefact / quality | 0 | none labelled |

All 612 are `pathological` (polyp, histology not given). The dataset therefore **cannot serve as a negative class**.

## 6. Linking keys, grouping ids, splits

* **Image <-> mask <-> metadata**: by `frame_id` = file stem (identical stem in `Original/` and `Ground Truth/`, in `PNG/` and in `TIF/`). 612 / 612 / 612 matched, 0 orphans in any direction [measured].
* **Grouping id**: `sequence_id` (29 groups). **Frames of one sequence are near-identical views of the same polyp** (thumbnail NN of 91 % of frames lies in the same sequence; RMSE of consecutive ids inside a sequence median 20 vs 49 across a sequence boundary) -> **always split by `sequence_id`** (e.g. 5-fold by sequence), never by frame.
* **Caveats [literature, not provable on disk]**: the original CVC-ClinicDB is described as 612 frames from 31 sequences of 23 patients; this copy has **29** `sequence_id`s (the brief's "31 sequences" does not hold for this metadata) and **no patient id**: several sequences can belong to one patient, so sequence-level splits may still leak the same polyp/patient.
* **No official train/val/test split** is shipped.
* Frames come from colonoscopy videos; only 6-26 frames per sequence were kept.

## 7. Technical facts

* **PNG**: 8-bit RGB, 384 x 288 for all 612 images and 612 masks (non-interlaced); file sizes 49-123 KB (median 87 KB); no corrupt file. md5 of the 612 PNG images: **612 distinct** (no duplicates).
* **TIF**: uncompressed (compression = 1), 384 x 288, images 3 samples/pixel, masks 1 sample/pixel, one strip layout with 16 rows per strip. **Pillow cannot open the original `.tif` images** (`UnidentifiedImageError`): the TIFF has 3 samples with `PhotometricInterpretation = min-is-black` and a BitsPerSample tag that does not match; `tiffinfo` (libtiff) reads it with a warning. I decoded all 612 + 612 TIFFs with a 30-line pure-struct reader (scratchpad `tifread.py`; raw uncompressed strips, RGB order): **TIF images == PNG images for 612/612, TIF masks == PNG masks for 612/612 (max abs diff 0)**. The TIF folder is therefore a redundant, harder-to-read copy (263 MB vs 54 MB) - **use `PNG/` only**. (Masks' TIFFs not tested with Pillow.)
* Content: octagonal / rounded endoscope view on a black background (borders left/right/corners), glare, no text overlay seen in the inspected frames (e.g. ids 1, 2, 75, 100, 300), no black-frame artefacts noticed.
* Reading cost: all 4 x 612 files + stats + connected components took 5 s.

## 8. Duplicates and overlap

Tested [measured]:
1. Inside the dataset: md5 of 612 PNG images = 612 distinct; PNG vs TIF byte md5 differ by format (0 shared) but the **pixels are identical** (see 7).
2. **Against PolypsSet** (37,899 JPEGs): size 384x288 occurs only in `miccai2017_*` (7,276 images); md5 intersection 0 (formats differ); 32x32-gray thumbnail NN, every CVC frame vs every PolypsSet image regardless of size: **min RMSE 12.3, 0 pairs < 8** (reference: same-frame copies give < 4; visual check of the three closest pairs shows different frames) => **no CVC-ClinicDB frame is in PolypsSet**. PolypsSet's `cvc300` group is **CVC-ColonDB** (574x500), a different dataset. Same-video-different-frame overlap (e.g. GIANA 2017 videos from the same clinic family) cannot be excluded, nothing found at frame level.
3. **Against polypgen-ninja** (8,037): 384x288 not present, md5 intersection 0, thumbnail NN min RMSE 19.9, **0 pairs < 8** => no overlap.
4. Not tested: ETIS-LaribPolypDB (different resolution; ask the reader of that folder to run the thumbnail test with `scratchpad/CVC-ClinicDB/cvc_thumb.npz`), `out/` Hyper-Kvasir, Kvasir-SEG (CVC-ClinicDB frames are often included in public polyp benchmark mixes; none of the folders I examined contains them).

## 9. PROPOSED MAPPING to the unified table

**(a) Row units** (same convention as the Hyper-Kvasir merge, where a segmented image yields an `image` row *and* a linked `segmentation_mask` row):
* `image`: **612 rows** (`PNG/Original/<id>.png`), `has_mask = True`, `has_bbox = True` (box derived from the mask), `sequence_id`/`frame_id` filled.
* `segmentation_mask`: **612 rows** (`PNG/Ground Truth/<id>.png`), `parent_image_sample_id` -> the image row, labels inherited.
* Total **1,224 rows** (or 612 if the coordinator decides not to duplicate; flag `has_mask` instead). TIF files are never used as `file_path`. No `video_frame` rows (stills; the video is not shipped). No new row type is needed.

**(b) Native class -> unified label**

| native | count | region | site | category | finding slug | confidence |
|---|--:|---|---|---|---|---|
| mask `polyp` (value 255 > 127) | 612 | lower-gi-tract | colon | pathological-findings | `polyps` (same string as `finding_harmonized` of Hyper-Kvasir polyps) | high |

No negative / normal class in this dataset.

**(c) Columns**: apply (all as in the Hyper-Kvasir merge): `sample_id` (`image:cvc-clinicdb:<id>`, `mask:cvc-clinicdb:<id>`), `source_type`, `source_dataset`, `label_source` (`metadata.csv`), `label_level` (`image`/`mask`), `row_description`, `item_id` (frame id), `seg_stem` (= frame id), `parent_image_sample_id`, `mask_sample_id`, `image_md5` (cheap, all 612), `file_path/ext/exists/size_bytes`, `image_path`, `mask_path`, `region`, `organ_raw`, `category*`, `finding*`, `width`, `height`, `has_mask`, `has_bbox`, `n_boxes`, `bboxes_json`, `bbox_label`, `bbox_xmin..ymax`, `mask_foreground_pixels`, `mask_foreground_fraction`, `mask_tight_*`, `annotation_source`. `mask_in_bbox_fraction` / `mask_json_bbox_max_diff_px` / `mask_corner_pixel_removed`: not applicable (no JSON boxes; the noise here is low-grey values, not a corner pixel). Not applicable: all video columns, `bbps_*`, `finding_2*`, `dir_*` (could be `PNG`/`Original` or `Ground Truth`). **NEW columns**: `dataset_name`, `sequence_id`, `frame_id`, `group_id` (= `cvc-clinicdb|seq<id>`), `n_components` / `n_boxes` (per-component boxes), `mask_polarity` (`white=polyp`), `mask_binarize_threshold` (127), `mask_has_grey_noise` (138 True), `bbox_format` (`mask-derived-inclusive-corner`), `modality` (`WLI`), `split_official` (null).
Boxes: derive from the mask (>127): union box and per-connected-component boxes (full-resolution labelling; < 10 s for 612 masks). Mark them as `mask-derived` (the Hyper-Kvasir boxes are annotator boxes).

**(d) To read/compute**: PNG masks + images (5 s, already done), md5 (instant). TIF decoding not needed.

## 10. Pitfalls and open questions

1. `metadata.csv` TIF paths say `TIFF/...` but the folder is `TIF/` (all 1,224 TIF paths broken as written); original `.tif` images fail in Pillow. Use PNG.
2. Masks are RGB PNGs with grey noise in 138 files - always threshold (`> 127`), never `== 255` or `astype(bool)` (the latter would turn 91k noise pixels into foreground, e.g. 9,029 px in one frame).
3. 29 sequences here (literature: 31 sequences / 23 patients). No patient id -> sequence-level splits can still leak a patient.
4. 100 % positives: cannot be used alone for classification; must be combined with a negative source (e.g. PolypGen/PolypsSet negatives or Hyper-Kvasir normal classes).
5. No official split; no histology; no per-frame anatomical site; a small dataset (612) that is heavily reused in public benchmarks - if the final training pool also includes Kvasir-SEG / ETIS / other polyp sets, test for overlap (I tested only PolypsSet and polypgen-ninja: none).
6. Open: should the 612 duplicate-by-design mask rows be kept (Hyper-Kvasir parity) or folded into the image rows?
