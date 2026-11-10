# ETIS-LaribPolypDB (data_to_merge/ETIS-LaribPolypDB) - reader report

Reader 1 of 3. Scripts in the scratchpad (`.../scratchpad/etis/`), python `-I`; folder read-only.

## 0. Short summary

196 colonoscopy (white-light) frames, **every one contains at least one polyp** (no negatives), each with a pixel-exact **binary mask** (PNG, 0/255, **white = polyp**, same size as the image). One image size for everything (**1225 x 966**). Names `1.png`-`196.png` in `images/` and `masks/` (same names). No sequence / polyp / patient ids, no splits, no labels file. Masks are semantic (one white region per polyp; 6 images contain 3 separate regions -> 208 connected components in total). Traps: **3 pairs of byte-identical images carry different masks**, frames are near-duplicate sequences without a sequence id, ~5.7 % of every image is black corner mask.

## 1. Identity

* **ETIS-Larib Polyp DB** (Silva et al., IJCARS 2014; used in the MICCAI 2015 endoscopic vision polyp-detection challenge; literature knowledge, no README/licence in the folder). Colonoscopy, white light (visual check of 24 images; no NBI seen). Literature: 196 frames from 34 sequences / 44 distinct polyps - **not verifiable in this copy** (no ids). Licence: none shipped (unknown; research dataset, check before redistribution).
* Size 177 MiB on disk (`du`): images 184.8 MB (196 PNG, RGB 8-bit, no metadata chunks), masks 0.51 MB (196 PNG, mode L), plus 1 `.DS_Store`. 392 PNG files + the `.DS_Store` = the 393 files of the task description.
* Layout:

```
ETIS-LaribPolypDB/
  images/ 1.png ... 196.png     (196)   RGB 1225x966
  masks/  1.png ... 196.png     (196)   L   1225x966
```
(no leading zeros -> sort numerically, not lexicographically; stems 1..196 all present, none missing, none extra).

## 2. Annotation sources

Only the mask PNGs (no CSV/JSON/XML). Per mask: PNG, 8-bit grayscale (`L`), **unique values exactly {0, 255} in 196/196 masks** (lossless, no anti-aliasing / noise / JPEG artefacts, no palette), size identical to its image (196/196), no alpha, no EXIF.

## 3. What the annotation is

* **Binary semantic segmentation mask**, polarity **white (255) = polyp, black (0) = background** (checked visually: 24 outlines overlaid on the images fall exactly on the polyps; and quantitatively: foreground fraction 0.11 % - 29.1 %, median 2.0 %, 10th/90th percentile 0.53 % / 12.4 % - a background-white mask would be > 50 %).
* **Not per instance**: no instance ids. Connected components (8-connectivity, full resolution): 190 images have 1 region, **6 images have 3 regions** (ids 43-48, one scene with 3 polyps) -> 208 regions. Touching polyps would be merged, so 208 is a lower bound of the polyp count.
* Mask foreground per image: 1,257 px (smallest) - 343,815 px (largest region); median whole-mask foreground 23,376 px (1.98 %).
* Bounding boxes are not shipped but derivable per component from the masks (tight box, corner xyxy, **inclusive** max index if computed like the HK `mask_tight_*`).

## 4. Location (anatomy)

Colon (lower GI) for the whole dataset: ETIS-Larib is a colonoscopy polyp database and the images show haustral folds/colonic mucosa (24 viewed). No finer site (caecum/sigmoid...) available -> `region = lower-gi-tract`, `site = colon` (dataset-wide constant, source: dataset identity + visual check, not a column).

## 5. Findings

* One class only: **polyp** - 196/196 images positive (min foreground 0.11 %, no empty mask), 208 regions. Normal/negative images: none; instruments: none annotated; no artefact labels.
* No histology / size / morphology (Paris) labels.

## 6. Linking keys, grouping, splits

* Join: **file name** identical in `images/` and `masks/` (196 / 196 matched, 0 orphans either way; sorted lists equal).
* Grouping ids: **none shipped.** Content analysis: frames come in bursts of near-identical views of the same polyp (e.g. ids 1-6, 7-12, 13-18 are consecutive views, 43-48 show a 3-polyp scene), but the numbering is **not strictly sequential** (ids 19-24 interleave two scenes). Heuristic clustering by thumbnail distance does not give a clean sequence count (no plateau: 152 ... 49 clusters for thresholds 8-32), so I could **not reconstruct the 34 sequences**; treat the dataset as one group.
* Official splits: none shipped. It is a tiny set normally used as a *test* set; recommended: put the whole dataset into one split (test / external validation), never split it randomly.

## 7. Technical facts

* Images: PNG RGB 1225 x 966 for 196/196; masks L 1225 x 966 for 196/196 (one size - no resizing questions; aspect ratio 1.268, CVC-ClinicDB for comparison is 384x288 = 1.333).
* Image borders: **circular/octagonal endoscope field of view with black corners**, 5.73 % of the pixels (67,787 of 1,183,350) are black in >= 95 % of images (all four 60x60 corner windows 100 % dark); no text overlays seen. Additional black margins in a few images: ids 177-182 (up to 66 black rows at the top, 34 black columns left, 18 % dark pixels in total), id 14 (15 black columns left), a 1-2 px black left column in ~50 more images (57 images have at least one black left column, 14 at least one black top row). Mask/crop if the model should not see them.
* No unreadable or corrupt files; all PNG decode OK (all 196 images and 196 masks were fully decoded).

## 8. Duplicates and overlap (what was actually tested)

* **Inside, byte level:** md5 of the 196 PNG images -> **3 identical pairs: (20, 22), (127, 131), (172, 175)**; masks md5: no duplicates. The masks of the identical pairs **differ**: IoU 0.80 (20/22), 0.93 (127/131), 0.92 (172/175) -> same frame annotated twice with slightly different outlines (annotation noise). Keep both frames of a pair in the same split; consider dropping one.
* **Inside, near-duplicates:** many (consecutive frames of one polyp); within-ETIS best-match thumbnail correlation median 0.98 (see below).
* **Cross-dataset, size:** no image of any other dataset in `data_to_merge/` has 1225x966 (header scan of 136,904 images). Images with the same aspect ratio (+-0.004): 871 in polypgen-ninja (865 of size 1350x1064, 6 of 1360x1072) and 18 in hyper-kvasir (e.g. 1349x1063 x5).
* **Cross-dataset, content (24x24 grey thumbnails, Pearson correlation, all 196 ETIS images vs 53,758 candidates = CVC-ClinicDB PNG originals 612, polypgen-ninja 8,037, PolypsSet 37,899, hyper-kvasir labelled lower-GI 7,210):** best match per ETIS image 0.71-0.947 (median 0.88); maxima per dataset: CVC 0.89, PolypsSet 0.93, HK 0.94, PolypGen 0.947; **no pair >= 0.95**. Calibration: true duplicates inside ETIS correlate 1.0 and the median near-duplicate (neighbour frame) 0.98. The 3 highest pairs viewed side by side show different scenes. **Verdict: no evidence that ETIS shares frames with CVC-ClinicDB, PolypGen, PolypsSet or Hyper-Kvasir.** Limits: scale-/crop-changed copies with heavy cropping could fall below 0.95; the CVC-ClinicDB TIF originals were not read (Pillow could not open them), the PNG copies were. Not tested vs the PolypGen *positive-only* subset specifically or by feature matching.

## 9. Proposed mapping to the unified table

### 9a. Row unit

The mask exists for every image, so follow the existing HK pattern (`image` row annotated with the mask + a `segmentation_mask` row):

* **196 `image` rows** (`has_mask = True`, `has_bbox = True`/derived) + **196 `segmentation_mask` rows** (`file_path` = the mask) = **392 rows** (same as HK: the mask rows duplicate the image rows). If the coordinator prefers one row per image, use only the 196 image rows with `mask_path`; the information is identical.
* `sample_id`: `image:etis:<n>` / `mask:etis:<n>` (stems are bare integers and collide with nothing only if prefixed).
* No `video_frame` rows (no video).

### 9b. Native class -> unified label

| native | count | region | site | category | finding slug | confidence |
|---|--:|---|---|---|---|---|
| mask value 255 (polyp) / image with mask | 196 images, 208 regions | lower-gi-tract | colon | pathological-findings | `polyps` (= existing HK `polyps`) | high |
| mask value 0 | background | - | - | - | not a class | - |

No other classes. All 196 images share the same label.

### 9c. Columns

* Apply (computable, same definitions as HK): `sample_id`, `source_type`, `source_dataset`, `label_source` (= "masks (all images positive)"), `label_level` (`image` / `mask`), `item_id` (stem), `file_path`, `file_ext`, `file_exists`, `file_size_bytes`, `image_path`, `mask_path`, `parent_image_sample_id`, `mask_sample_id` (name-based link, no md5 needed), `image_md5` (cheap), `region`, `category`, `finding`, `finding_harmonized`, `finding_harmonization`, `width`, `height`, `has_mask`, `has_bbox`, `n_boxes` (= connected components 1 or 3), `bboxes_json` (derived), `bbox_label` (`polyp`), `bbox_xmin/ymin/xmax/ymax` (union of component boxes), `mask_foreground_pixels`, `mask_foreground_fraction`, `mask_tight_*` (here equal to the union of component boxes), `mask_in_bbox_fraction` (1.0 by construction), `annotation_source` (= "derived from mask PNG; boxes computed, not shipped").
* Not applicable: all video columns, `seg_stem` (no separate segmented folder; could be the stem), `mask_json_bbox_max_diff_px`, `mask_corner_pixel_removed` (no JPEG noise), `bbps_*`, `description`, `finding_2*`, `category_raw`/`organ_raw` (no source label text; null), `dir_*`.
* New columns suggested: `dataset`, `modality` (white-light), `site` (colon), `split` / `split_group` (null here, whole set = external test), `polyp_instance_count` (= n components), `mask_encoding` (`png-0/255, white=lesion`), `duplicate_group_id` (ids 20/22, 127/131, 172/175).

### 9d. What must be read / computed

* PNG header read of 392 files and `stat`: < 1 s. md5 of 392 files: < 1 s.
* Mask decoding + connected components + tight boxes: decode 196 masks (1225x966, L) and label components; my pure-Python/numpy flood fill over all masks ran in well under a minute (a library such as scipy/skimage is **not** installed in the project venv - ask before installing; pure numpy is enough).
* Thumbnail/dup detection is optional.

## 10. Pitfalls and open questions

1. **Identical images with different masks** (20/22, 127/131, 172/175): do not put the two members into different splits; decide which mask to keep (IoU 0.80-0.93).
2. **No sequence/patient ids** and visible near-duplicate bursts -> use the whole set as one held-out group, or cluster; random splits would leak.
3. Different geometry from other datasets (1225x966, round FOV with black corners, plus black margins in ids 177-182): resize/crop policy matters; mask value 255 (not 1).
4. Only positive images: cannot measure false-positive rate on this set; detection metrics need negatives from elsewhere.
5. Non-padded numeric names `1.png`..`196.png` collide across datasets (`1.png` also appears elsewhere) -> always prefix with the dataset name.
6. Instance semantics: 208 components are a lower bound of polyp instances (touching polyps merge).
7. Open: is ETIS meant as train data or as a held-out test set in the unified model? That decides the split column. Licence unknown.
