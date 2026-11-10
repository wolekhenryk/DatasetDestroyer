# etis-laribpolypdb (dataset `etis-laribpolypdb`, folder `ETIS-LaribPolypDB`)

Adapter `unify/adapters/etis_laribpolypdb.py`, vocabulary `unify/vocab/etis-laribpolypdb.csv`. Analysis: `docs/reports/ETIS-LaribPolypDB.md`; schema review: `docs/reviews/reader1-schema-review.md`.

## Source
ETIS-Larib Polyp DB (Silva et al., IJCARS 9, 2014; used in the MICCAI 2015 polyp-detection challenge). Colonoscopy, white light (visual check; no NBI seen). The literature gives 196 frames from 34 sequences /
44 polyps - **not verifiable in this copy** (no ids). **Licence: none shipped -> `license = unknown`.** No README, no device information.

## Layout used
`ETIS-LaribPolypDB/images/<n>.png` (RGB, 1225 x 966) and `ETIS-LaribPolypDB/masks/<n>.png` (mode L, 1225 x 966), n = 1..196, 392 PNG; no label file. Names are bare integers - `item_id` is the stem, `sample_id`
`image:etis-laribpolypdb:<n>` / `mask:etis-laribpolypdb:<n>`. Rows: **196 `image` + 196 `segmentation_mask`** (one per image, linked both ways). `META["expected"] = {image: 196, segmentation_mask: 196}`.

## Label semantics
* **Binary semantic mask**, PNG, values **exactly {0, 255}** in 196/196 masks (lossless, no noise), **white (255) = polyp** (checked on overlays and by foreground fraction 0.11-29 %, median 2.0 %). `mask_encoding = value==255 white=polyp`,
  `mask_format = png-gray`, `mask_noise_pixels_removed = 0` everywhere. Not per instance.
* **Every image is polyp-positive** (no empty mask, no negatives): the class `polyp` -> `polyps` (parent `polyps`, `pathological-findings`) is a dataset constant (`label_source = dataset-constant ...`,
  `annotation_types = mask`, `annotation_format = mask-png`). `finding` = `polyp`, `finding_harmonized` = `polyps` (`mapped`), `finding_raw` = `polyp` (synthetic: there is no label text).
* **Boxes are NOT shipped**: derived from the mask (`bbox_source = mask-derived`): tight box of each **8-connected component of at least 10 px** (all components are >= 1,257 px, so nothing is dropped),
  inclusive max, sorted by (ymin, xmin); `n_boxes` = number of components (190 images: 1, **6 images (ids 43-48): 3** -> 208 boxes); `bbox_*` = union box (for the multi-polyp images mostly background -
  use `bboxes_json`); `class_counts_json = {"polyps": n}`. Touching polyps merge into one component, so `n_boxes` is a lower bound of the polyp count. `mask_tight_*` equals the union box by construction;
  `mask_in_bbox_fraction` / `mask_json_bbox_max_diff_px` are empty (no annotator box).

## Location
Colon (lower GI), dataset-wide constant (`location_source = dataset-constant`: ETIS-Larib is a colonoscopy polyp database and the images show colonic mucosa); no finer site. `procedure = colonoscopy`,
`imaging = white-light`.

## Grouping and splits
**No sequence / polyp / patient id exists.** Content check: ids 1-6, 7-12, 13-18 are near-identical consecutive views of one polyp, but the numbering is not strictly sequential (ids 19-24 interleave two scenes) and
thumbnail clustering gives no stable sequence count -> a block proxy would be wrong. `group_id = etis-laribpolypdb:all`, `group_kind = dataset`, `group_quality = coarse`: the whole dataset is one group (safe against
leakage, **cannot be split further**; hold it out as an external test set or use it entirely in training). No official split (`split_official` empty).

## Duplicates and conflicts
* **3 pairs of byte-identical images carry different masks**: (20, 22) IoU 0.80, (127, 131) 0.93, (172, 175) 0.92. The runner flags the 6 image rows: `dup_group_id = dup:<md5 prefix>` and
  `qa_flags = dup-box-conflict` (same class, different boxes). Keep both members of a pair in the same split; decide which mask to trust.
* Many near-duplicate consecutive frames (see above). No overlap with CVC-ClinicDB, PolypGen, PolypsSet or Hyper-Kvasir found (24x24 grey-thumbnail correlation of all 196 images against 53,758 candidates:
  maximum 0.947, no pair >= 0.95; scale-/crop-changed copies are not excluded).

## Technical facts
All images 1225 x 966 RGB PNG (aspect ratio 1.268), masks the same size. **Circular field of view with black corners** (5.7 % of the pixels are black in >= 95 % of the images); extra black margins in ids 177-182
(up to 66 rows top, 34 columns left; 18 % dark pixels) and a 1-2 px black left column in ~50 more images. No text overlays seen. No unreadable file.

## extra_json keys
`component_px` (list of the pixel areas of the mask components, same order as `bboxes_json`), on image and mask rows.

## Pitfalls
1. Identical images with different masks (6 image rows flagged).
2. No grouping information: treat the dataset as one unit.
3. Only positive images: no false-positive measurement possible on this set.
4. Bare-integer names collide across datasets (`1.png` ...): always use `sample_id` / the dataset prefix.
5. `n_boxes` counts mask components, not verified polyps; the union `bbox_*` of a multi-polyp image is not a polyp box.
6. Mask value is 255 (not 1); black corners / margins are part of the images.

## Verification (done)
`python -m unify --only etis-laribpolypdb ...`: 392 rows, 113/113 validation checks PASS, byte-identical across two runs, ~2 s. Spot checks: 8 images (6 random + 43 + 20) - components, boxes, foreground pixels, md5,
file size recomputed independently from the raw PNGs (0 mismatches); box overlay of 8 images viewed (boxes sit on the polyps, including the 3-polyp scene and the image with black margins).
