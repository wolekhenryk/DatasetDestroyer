# cvc-clinicdb (`CVC-ClinicDB/`)

Adapter `unify/adapters/cvc_clinicdb.py`, vocabulary `unify/vocab/cvc-clinicdb.csv`. Analysis and evidence: `docs/reports/CVC-ClinicDB.md`. Overlay/independent check: `unify/tools/polyp_adapters_check.py`.

## Source
CVC-ClinicDB (Computer Vision Center + Hospital Clinic, Barcelona; Bernal J. et al., *WM-DOVA maps for accurate polyp highlighting in colonoscopy*, Comput Med Imaging Graph 2015): 612 colonoscopy still frames of 384x288 with a polyp ground-truth mask each. No README; licence from the TIFF `Copyright` tags: **`research and educational use only (Hospital Clinic Barcelona / CVC)`**.

## Layout used / ignored
```
CVC-ClinicDB/PNG/Original/<id>.png        used    612 frames (ids 1..612, no zero padding)
CVC-ClinicDB/PNG/Ground Truth/<id>.png    used    612 masks (RGB PNG, 3 identical channels)
CVC-ClinicDB/metadata.csv                 used    ONLY frame_id -> sequence_id (612 rows, CRLF)
CVC-ClinicDB/class_dict.csv               used    legend: background 0,0,0 / polyp 255,255,255 (the adapter asserts it)
CVC-ClinicDB/TIF/**                       ignored pixel-identical copies of the PNGs (612/612 images and masks); Pillow cannot open the original .tif (non-standard 3-sample TIFF); recorded as extra_json.tif_*_path
metadata.csv path columns                 ignored tif_* say `TIFF/...` but the folder is `TIF/` (all 1,224 TIF paths broken as written); paths are built from the folder layout
```

## Row units and counts (`META["expected"]`)
| source_type | rows |
|---|--:|
| image | **612** |
| segmentation_mask | **612** (one per PNG ground-truth mask; `file_path = mask_path`, linked both ways, `seg_stem` = frame id) |

## Label semantics
Every frame contains a polyp (0 empty masks); there is no negative / normal frame and no histology, size or box file. Class name `polyp` comes from `class_dict.csv` (white pixels) -> category pathological-findings, finding `polyp`, `finding_harmonized = polyps`. `annotation_types = mask` (the class is implied by the mask), `annotation_format = mask-png`.
**Mask rule**: RGB PNG, polyp = white. 138 masks are not strictly binary (91,043 grey pixels in total, typically values 2-64, only 32 pixels in 128..254) -> binarise **gray > 127**, then drop 8-connected components **< 10 px** (`c.clean_mask(min_component_px=10)`): 24 specks of 1-6 px in 23 frames, 39 pixels in total -> `mask_noise_pixels_removed` (0 elsewhere); the smallest real component is 190 px. `mask_foreground_pixels / _fraction` and `mask_tight_*` refer to the cleaned mask; `mask_encoding = gray>127 white=polyp; 8-connected components < 10 px removed`, `mask_format = png-rgb`. The number of grey pixels of the raw mask is in `extra_json.mask_grey_pixels`.
**Boxes** are `mask-derived` (no box file exists): one box per remaining 8-connected component, inclusive pixels: 582 frames with 1 box, 26 with 2, 4 with 3; `bbox_*` = union box = `mask_tight_*`; `mask_in_bbox_fraction` / `mask_json_bbox_max_diff_px` stay empty (no independent annotated box to compare with). The second/third components of a frame can be genuine extra lesions or small separate blobs (e.g. frame 75: 1772 / 748 / 197 px).

## Location / imaging
Dataset-constant colon / lower-gi-tract (`location_source = dataset-constant`); no segment per frame. `procedure = colonoscopy`, `imaging = white-light` (dataset description and inspected frames; not recorded per file).

## Grouping and splits
* `group_id = cvc-clinicdb:seq-NN` from `metadata.csv` (`sequence_id`, zero-padded; also `video_id = seq-NN`), `group_kind = sequence`, `group_quality = exact` (6-26 frames per sequence, ids are contiguous blocks; 29 sequences - not the 31 of the paper-level description). Frames of one sequence are near-identical views of the same polyp: **split by group, never by frame**.
* **No patient id** is shipped: the literature describes 23 patients, so several sequences may belong to one patient and a sequence-level split can still leak a patient. `exact` means "all frames of the sequence share the id", not patient-level.
* `frame_index` is left empty: the order of frames inside a sequence follows `frame_id` but is not proven temporal. No official split (`split_official` empty).

## Duplicates and overlap
No duplicates inside the dataset (612 distinct md5). Against PolypsSet (all sizes) and polypgen-ninja: no identical frame (md5 intersection 0; 32x32 thumbnail nearest-neighbour RMSE minimum 12.3 vs PolypsSet / 19.9 vs PolypGen, genuine copies are < 4; `docs/reports/CVC-ClinicDB.md`). Not tested against ETIS-Larib or Hyper-Kvasir.

## `extra_json` keys
`frame_id`, `sequence_id`, `mask_grey_pixels` (pixels of the raw mask with a value strictly between 0 and 255), `tif_image_path`, `tif_mask_path` (the redundant TIF copies).

## Pitfalls
* Use PNG only; the TIF side and the TIFF-prefixed metadata paths are broken for naive readers.
* Never binarise with `astype(bool)` / `!= 0`: that turns the 91k noise pixels into foreground (one frame has 9,029 such pixels).
* 100 % positives: cannot be used for classification without a negative source.
* Small (612 frames) and heavily reused in public polyp benchmarks - test overlap before mixing with other polyp sets.
