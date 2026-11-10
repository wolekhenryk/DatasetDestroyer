# Reader 2 - review of `docs/SCHEMA_DRAFT.md`

Datasets: PolypsSet, polypgen-ninja, CVC-ClinicDB (reports in `docs/reports/`). Numbers like `#47` refer to the draft's column numbers; unnumbered columns (boxes/masks) are quoted by name.
Scripts used only to verify claims (scratchpad `.../scratchpad/{PolypsSet,polypgen-ninja,CVC-ClinicDB}/`, `python -I`): `conv.py` (VOC box edges), `cc_full.py` (CVC full-resolution components), `examples.py` (example values). Evidence tags: **[measured]**, **[inferred]**.

## 0. Requested changes, ranked

1. **Box convention for VOC (PolypsSet).** The data say the XML boxes are *edge coordinates in [0,W]x[0,H]* (half-open), not inclusive pixel indices: of 35,981 boxes, `xmax==W` 60 vs `xmax==W-1` 5; `ymax==H` 312 vs `ymax==H-1` 61 (a clamp pile-up exactly at W/H, never above), `ymin==0` 15x, `xmin==0` 0x. The draft's "VOC: as shipped, clipped to `[0,W-1]`" is off by one on the max edges and silently changes 356 boxes. Use `xmax_incl = xmax-1`, `ymax_incl = ymax-1` (min edges unchanged); all boxes stay valid (min box size 5x12 px). Details in 2.9.
2. **Row-unit consistency / decision 7.** R1 makes the number of `segmentation_mask` rows depend on *how* a mask is stored (file -> row, embedded JSON -> no row). Pick one rule for all datasets; I recommend **folding mask rows into image rows** (lossless, see 4). If mask rows stay, `#66 dup_group_id` must be null on mask rows (they share `image_md5` with their parent, as in HK), else every image/mask pair becomes a "duplicate group".
3. **`#27 finding_in_image_vocab` is trivially True** for every image row under the new definition ("occurs among `image` rows of the whole table"). Redefine (other dataset / other source_type) or drop.
4. **Need explicit semantics for empty and missing geometry:** `n_boxes` must be **0 for an annotated-empty image** and **null for a positive without geometry** (PolypGen's 641); `annotation_types` must say what a negative XML is; add `finding_harmonization = derived` for labels synthesised from absence.
5. **Generalise `mask_corner_pixel_removed`** (HK-only) to `mask_noise_pixels_removed` Int64; CVC needs specks removed (24 components of 1-6 px).
6. **`bbox_source` values overlap** (`annotator` vs `voc`, `yolo-converted`); keep `annotator` | `mask-derived`, put the format in `annotation_format`.
7. **`#62 group_id` format `<dataset>|<group>`** collides with `|` inside group names; use `-`. Merge known duplicate videos into one group id.
8. **`#4 source_subset`** must be the origin partition (PolypsSet `videos80`, ...), the shipped split goes to `#65`.
9. **`#56/#57 video_id` / `frame_index`**: also fill for extracted-frame datasets (PolypsSet, CVC) with documented "source-defined" semantics; PolypGen cannot fill `frame_index`.
10. **New column `centre`** (PolypGen C1-C6; needed for `group_kind=centre`).
11. Machine-readable schema (name, dtype, nullability, allowed values) instead of the prose list ("+ any existing ones" for #71-82 is not implementable).

---

## 1. Example rows

Conventions: `(null)` = plausible but not available for this dataset; columns not listed are empty by definition (video columns, `bbps_*`, `finding_2*`, `dir_*`, `description`, `region_derived`, `segmented_image_path`, `timestamp_s`). Values for md5/size/box are the real ones from the files. Where my value differs from the draft's default, the draft value is shown in `[draft: ...]`.

### 1.1 PolypsSet - only `image` rows (37,899)

**(A) positive: `PolypsSet/train2019/Image/1.jpg`**
```
sample_id            image:polypsset:train2019/1
source_type          image
dataset              polypsset
source_subset        miccai2017_test                      [draft example would suggest train2019]
item_id              train2019/1                           (image path under the dataset image root, no extension)
label_source         PolypsSet/train2019/Annotation/1.xml
label_level          image
row_description      Colonoscopy frame (MICCAI2017 test video 3, source frame 245.png) with one adenomatous polyp box; VOC XML from PolypsSet (Li et al., PLOS ONE 2021); shipped in train2019.
license              unknown
annotation_types     class|bbox
annotation_format    voc-xml
region               lower-gi-tract
organ_raw            (null)
site                 colon
location_source      dataset-constant
procedure            colonoscopy
imaging              white-light                           (inferred: GIANA/MICCAI frames; not recorded per file)
category             pathological-findings
category_raw         (null)                                (dataset has no category text)
finding              adenomatous
finding_raw          adenomatous
finding_harmonized   polyps
finding_harmonization mapped
finding_in_image_vocab True
finding_parent       polyps
finding_subtype      adenomatous
findings_all         polyps
class_counts_json    {"adenomatous": 1}
n_labels             1
label_confidence     high
is_negative          False
file_path            PolypsSet/train2019/Image/1.jpg
file_ext             jpg
file_exists          True
file_size_bytes      7745
image_path           PolypsSet/train2019/Image/1.jpg
annotation_path      PolypsSet/train2019/Annotation/1.xml
image_md5            98246182f620407ba6620bc54d156e6c
video_id             miccai2017_test-3                     (from XML <path>, see 3)
frame_index          245                                   (source frame number of 245.png)
group_id             polypsset|miccai2017_test-3           [draft format: polypsset|miccai2017_test||3 would contain extra '|']
group_kind           video
group_quality        exact                                 (video-level; patient unknown)
split_official       train
dup_group_id         (null)
qa_flags             (null)
extra_json           {"case_raw":"MICCAI2017_Test/test/3","orig_filename":"245.png","orig_folder":"3"}
width / height       384 / 288
has_mask             False
has_bbox             True
n_boxes              1
bboxes_json          [{"label":"adenomatous","finding":"polyps","xmin":164,"ymin":113,"xmax":342,"ymax":278}]   [draft: xmax 343, ymax 279]
bbox_label           adenomatous
bbox_xmin/ymin/xmax/ymax 164 / 113 / 342 / 278            [draft: 343 / 279 for xmax/ymax]
bbox_source          annotator                             [draft: voc]
annotation_source    PolypsSet VOC XML (Li et al., PLOS ONE 2021)
mask_* , mask_format, mask_encoding   (empty: no mask exists)
```
Raw XML: `xmin 164, ymin " 113", xmax " 343", ymax " 279"`, image 384x288.

**(B) negative: `PolypsSet/val2019/Image/6/8.jpg`** (differences to A only)
```
sample_id            image:polypsset:val2019/6/8
source_subset        videos80
item_id              val2019/6/8
label_source         PolypsSet/val2019/Annotation/6/8.xml
annotation_types     bbox                                  (explicit empty annotation - needs decision 4 below)
imaging              unknown
category             background
category_raw         (null)
finding              no-polyp-annotated
finding_raw          (null)
finding_harmonized   no-polyp-annotated
finding_harmonization derived                              [draft has no value for this]
finding_parent       no-polyp-annotated
finding_subtype      (null)
findings_all         no-polyp-annotated
class_counts_json    {}
label_confidence     medium
is_negative          True
file_path/image_path PolypsSet/val2019/Image/6/8.jpg ; file_size_bytes 78919
image_md5            de9dbce70bcec4a79259effa09a1f560
video_id / frame_index  videos80-posttest-31 / 8
group_id             polypsset|videos80-posttest-31 ; group_quality exact ; split_official val
extra_json           {"case_raw":"80_Videos_Frames/posttest/31","orig_filename":"8.jpg","histology_case":"hyperplastic","negative_basis":"empty-xml"}
width / height       592 / 464
has_bbox False ; n_boxes 0 ; bboxes_json []                (bbox_label, bbox_*, bbox_source: null)
```

**(C) known-leak row: `PolypsSet/test2019/Image/20/17.jpg`** (byte-identical to `train2019/Image/10844.jpg`)
`source_subset=cvc300`, `imaging=white-light` (CVC-ColonDB), `dup_group_id=dup:bd08d900...`, `qa_flags=split-leak-known`, `group_id=polypsset|cvc300-11+13` (cases 11 and 13 merged), `split_official=test`, `extra_json={"case_raw":"CVC-300/11","orig_filename":"242.bmp","dup_partner":"train2019/10844"}`.

### 1.2 polypgen-ninja - only `image` rows (8,037); no mask rows (R1)

**(A) positive with masks: `polypgen-ninja/img/C3_C3_EndoCV2021_00108.jpg`** (3 instances)
```
sample_id            image:polypgen-ninja:C3_C3_EndoCV2021_00108
source_type          image
dataset              polypgen-ninja
source_subset        single-frame                          (vs `sequence`)
item_id              C3_C3_EndoCV2021_00108
label_source         polypgen-ninja/ann/C3_C3_EndoCV2021_00108.jpg.json
label_level          image
license              unknown
annotation_types     class|mask                            (the boxes are derived, see 2.8)
annotation_format    supervisely-bitmap-json
region lower-gi-tract ; site colon ; location_source dataset-constant ; procedure colonoscopy ; imaging unknown ; organ_raw (null)
category             pathological-findings ; category_raw (null)
finding              polyp ; finding_raw polyp (classTitle) ; finding_harmonized polyps ; finding_harmonization mapped
finding_parent polyps ; finding_subtype (null) ; findings_all polyps ; class_counts_json {"polyp": 3} ; n_labels 1
label_confidence     high ; is_negative False ; finding_in_image_vocab True
file_path / image_path polypgen-ninja/img/C3_C3_EndoCV2021_00108.jpg ; file_ext jpg ; file_exists True ; file_size_bytes 176199
mask_path            (null)                                (mask is embedded in the JSON)
annotation_path      polypgen-ninja/ann/C3_C3_EndoCV2021_00108.jpg.json
image_md5            4db0cd5d3393b8f59ac63a47b56a94ef
video_id / frame_index (null) / (null)                    (single frame)
group_id             polypgen-ninja|centre-C3 ; group_kind centre ; group_quality proxy ; split_official (null)
dup_group_id         (null) ; qa_flags (null)
extra_json           {"centre":"C3","name_prefix":"C3","orig_name":"C3_EndoCV2021_00108","instance_areas_px":[3759,7550,18980]}
width / height       1350 / 1080
has_mask True ; has_bbox True ; n_boxes 3
bboxes_json          [{"label":"polyp","finding":"polyps","xmin":381,"ymin":235,"xmax":454,"ymax":307},
                      {"label":"polyp","finding":"polyps","xmin":539,"ymin":495,"xmax":714,"ymax":570},
                      {"label":"polyp","finding":"polyps","xmin":479,"ymin":599,"xmax":672,"ymax":747}]
bbox_label polyp ; bbox_xmin/ymin/xmax/ymax 381 / 235 / 714 / 747 (union) ; bbox_source mask-derived
mask_format          supervisely-bitmap
mask_encoding        bitmap PNG value==1, crop pasted at origin (x,y), OR over instances
mask_foreground_pixels 30289 ; mask_foreground_fraction 0.020774
mask_tight_xmin/ymin/xmax/ymax 381 / 235 / 714 / 747 ; mask_in_bbox_fraction 1.0
mask_json_bbox_max_diff_px (null) ; mask_corner_pixel_removed False  (see 2.8: becomes mask_noise_pixels_removed = 0)
annotation_source    Dataset Ninja export of PolypGen (Supervisely JSON)
```

**(B) positive without geometry: `C2_EndoCV2021_001002.jpg`** (differences)
`annotation_types=class`; `finding=positive`, `finding_raw=positive` (image tag; there is no `polyp` object), `finding_harmonized=polyps`, `finding_harmonization=mapped`; `class_counts_json=(null)`; `label_confidence=low`; `qa_flags=annotation-missing`; `file_size_bytes=505083`; `image_md5=1c62cf2bc868b63c1a96210204e7e764`; `width/height=1360/1064`; `group_id=polypgen-ninja|centre-C2`; `has_mask=False`, `has_bbox=False`, **`n_boxes=(null)`** (unknown, NOT 0), `bboxes_json=(null)`; all `bbox_*`/`mask_*` empty; `extra_json={"centre":"C2",...}`.

**(C) negative: `seq14_seq14_neg_00150.jpg`** (differences to A)
`source_subset=sequence`; `item_id=seq14_seq14_neg_00150`; `annotation_types=class` (image tag `negative`); `category=background`; `finding=negative`, `finding_raw=negative`, `finding_harmonized=no-polyp-annotated`, `finding_harmonization=mapped`; `finding_parent=no-polyp-annotated`; `class_counts_json={}`; `label_confidence=high` (explicit tag); `is_negative=True`; `file_size_bytes=181525`; `image_md5=6889e29177c745a69abbc6b9a738df6d`; `width/height=1245/1050`; `video_id=seq14`, `frame_index=(null)`; `group_id=polypgen-ninja|seq14`, `group_kind=sequence`, `group_quality=exact`; `has_mask=False`, `has_bbox=False`, `n_boxes=0`, `bboxes_json=[]`; `extra_json={"centre":null,"orig_name":"seq14_neg_00150","sub_sequence":"seq14_neg"}`.

### 1.3 CVC-ClinicDB - `image` (612) and `segmentation_mask` (612) rows under the draft default

**(A) image row, frame 1**
```
sample_id            image:cvc-clinicdb:1
source_type          image ; dataset cvc-clinicdb ; source_subset (null) ; item_id 1
label_source         CVC-ClinicDB/class_dict.csv;CVC-ClinicDB/PNG/Ground Truth/1.png      (class name `polyp` comes from class_dict.csv; presence from the mask)
label_level          image
license              research-only                         (TIFF copyright tag: "only permitted for research and educational purposes")
annotation_types     mask
annotation_format    mask-png
region lower-gi-tract ; site colon ; location_source dataset-constant ; procedure colonoscopy ; imaging white-light
category             pathological-findings ; category_raw (null)
finding polyp ; finding_raw polyp ; finding_harmonized polyps ; finding_harmonization mapped ; finding_parent polyps ; finding_subtype (null)
findings_all polyps ; class_counts_json {"polyp": 1} ; n_labels 1 ; label_confidence high ; is_negative False ; finding_in_image_vocab True
file_path / image_path CVC-ClinicDB/PNG/Original/1.png ; file_ext png ; file_exists True ; file_size_bytes 95563
mask_path            CVC-ClinicDB/PNG/Ground Truth/1.png
seg_stem             1 ; mask_sample_id mask:cvc-clinicdb:1 ; annotation_path (null)
image_md5            5d985f53b9ffb78f3e8ad107ad7e17a6
video_id             seq-01 ; frame_index (null) ; (order inside a sequence is by frame_id, not proven temporal)
group_id             cvc-clinicdb|seq-01 ; group_kind sequence ; group_quality exact (sequence-level; patient unknown) ; split_official (null)
dup_group_id (null) ; qa_flags mask-grey-noise (this mask has non-0/255 pixels)
extra_json           {"frame_id":1,"sequence_id":1,"alt_paths":{"tif_image":"CVC-ClinicDB/TIF/Original/1.tif","tif_mask":"CVC-ClinicDB/TIF/Ground Truth/1.tif"}}
width / height       384 / 288
has_mask True ; has_bbox True ; n_boxes 1
bboxes_json          [{"label":"polyp","finding":"polyps","xmin":40,"ymin":155,"xmax":263,"ymax":279}]
bbox_label polyp ; bbox_xmin/ymin/xmax/ymax 40 / 155 / 263 / 279 ; bbox_source mask-derived
mask_format          png-rgb ; mask_encoding gray>127 white=polyp
mask_foreground_pixels 16978 ; mask_foreground_fraction 0.153519
mask_tight_* 40 / 155 / 263 / 279 ; mask_in_bbox_fraction 1.0 ; mask_json_bbox_max_diff_px (null) ; mask_corner_pixel_removed False
annotation_source    CVC-ClinicDB ground-truth mask (Hospital Clinic / CVC Barcelona)
```
**(B) mask row, frame 1** (differences): `sample_id=mask:cvc-clinicdb:1`, `source_type=segmentation_mask`, `label_level=mask`, `file_path=mask_path=CVC-ClinicDB/PNG/Ground Truth/1.png`, `file_size_bytes=1985`, `image_path=CVC-ClinicDB/PNG/Original/1.png`, `parent_image_sample_id=image:cvc-clinicdb:1`, `mask_sample_id=(null)`, `image_md5=5d985f53...` (parent's md5, HK convention), **`dup_group_id=(null)`** (see 2.15); all labels/boxes/mask statistics inherited.
(For comparison, frame 75 has 3 real components: areas 1772/748/197 px -> `n_boxes=3`, union box = `bbox_*`.)

---

## 2. Columns that cannot be filled correctly / would mislead / are mis-defined

1. **`#4 source_subset`** - PolypsSet has two orthogonal partitions: the shipped split (`train2019|val2019|test2019`) and the origin sub-source (`videos80`, `miccai2017_train`, `miccai2017_test`, `nbi_adenoma`, `set1_hyperplastic`, `cvc300`). The draft lists both kinds as examples. **Define `source_subset` = origin partition**; the split goes to `#65 split_official` (normalise `train2019` -> `train`). Then `extra_json.sub_source` is redundant.
2. **`#5 item_id` / `#1 sample_id` uniqueness** - PolypsSet stems repeat: 37,899 files but only **28,773 distinct stems** [measured]; `1.jpg` exists in train, in every val/test sub-folder. Rule to write into the draft: *`item_id` = image path relative to the dataset's image root, without extension* (`train2019/1`, `val2019/6/8`; HK keeps uuid; PolypGen `C3_C3_EndoCV2021_00108`; CVC `1`). PolypGen names may contain a space (`C4_31_endocv2021_positive_329 2`); no `:` or `|` occurs in any PolypGen/PolypsSet/CVC name [measured: 0 names contain them].
3. **`#10 annotation_types`** - undefined for (a) an XML/txt with **zero objects** (PolypsSet 1,918 negatives): I propose `bbox` is listed and `n_boxes=0` = "annotated as empty", which is the only way to tell a checked negative from an unlabeled image (see-ai empty txt has the same issue); (b) **derived boxes** (PolypGen/CVC masks): list only *source* annotations (`class|mask`), the derived boxes are visible through `has_bbox` + `bbox_source=mask-derived`. State both rules.
4. **`#26 finding_harmonization`** - no value for labels synthesised from absence (PolypsSet empty XML -> `no-polyp-annotated`): add **`derived`**. (PolypGen's negative *tag* is an explicit label -> `mapped`.)
5. **`#20 category_raw` / `#22 finding_raw`** - null for all three datasets' categories (no category text anywhere) and for PolypsSet negatives; state "null when the source has no such text". For CVC the native class name is `polyp` from `class_dict.csv` (usable as `finding_raw`).
6. **`#6 label_source`** - for CVC the class is *implied* by the mask plus `class_dict.csv`; allow a list of files separated by `;` (I use that) and say what to write for dataset-constant labels.
7. **`#27 finding_in_image_vocab`** (see 0.3) - with "occurs among `image` rows of the whole table" every image row is True by construction. If the intent is video-vs-image pooling it only matters for video rows; otherwise redefine as "also occurs in at least one other dataset".
8. **Boxes / masks block (unnumbered)**:
   * `has_bbox` - define as "at least one box is available (annotator or mask-derived)" and keep `n_boxes` consistent: `has_bbox <=> n_boxes>0`; `n_boxes=0` for annotated-empty; `n_boxes=null` when geometry is unknown (PolypGen 641).
   * `bbox_source` - see 0.6. For VOC and YOLO the *format* is `annotation_format`; `bbox_source` only needs `annotator` | `mask-derived`.
   * **Mask-derived boxes rule (CVC; PolypGen is already per instance):** boxes = 8-connected components of the binarised mask, **after removing components < 10 px**. Evidence [measured, full resolution, 612 masks]: 670 components, 24 of them are 1-6 px specks, the next smaller real component is 190 px, so any threshold 7-189 px gives the same result. Result: 582 frames with 1 box, 26 with 2, 4 with 3; `bbox_*` = union.
   * `mask_corner_pixel_removed` is HK-specific (isolated pixel at (0,0)). CVC needs to remove 24 specks (not at the corner) -> keeping the boolean would say "False" while pixels were removed. **Generalise to `mask_noise_pixels_removed` Int64** (HK: 0/1, CVC: count, PolypGen: 0).
   * `mask_json_bbox_max_diff_px` and `mask_in_bbox_fraction` are HK-specific QA (independent JSON box vs mask). For mask-derived boxes they are trivially (null / 1.0); say so (I leave the first null, fill the second 1.0).
   * `mask_tight_*` duplicates `bbox_*` when boxes are mask-derived - harmless, but say it is expected.
   * `mask_encoding` - my values: CVC `gray>127 white=polyp`; PolypGen `bitmap PNG value==1, crop at origin (x,y), OR over instances`. Fine; please make it a small controlled list.
   * `mask_path` / `annotation_path` (#53/#54) - define `mask_path` = a standalone raster file only. Embedded masks (PolypGen) -> `mask_path` null, `annotation_path` = the JSON, `mask_format=supervisely-bitmap`.
9. **VOC box convention (draft: "as shipped, clipped to `[0,W-1]`").** Evidence [measured, PolypsSet, 35,981 boxes on shipped images]: coordinates are clamped at **W and H** (`xmax==W` 60x vs W-1 5x, W-2 16x; `ymax==H` 312x vs H-1 61x, H-2 64x), `ymin==0` 15x, `xmin==0` 0x (xmin 1: 1x, 2: 1x), nothing above W/H. That is the signature of **half-open edge coordinates in [0,W]x[0,H]**. Clipping to W-1/H-1 changes 356 boxes and treats `xmax` as inclusive, which it is not. **Convert: `xmax_incl = xmax - 1`, `ymax_incl = ymax - 1`, keep `xmin`, `ymin`**, strip the leading spaces in the XML. No clipping needed (min box 5x12 px). Even if the convention were 1-based inclusive the error is <= 1 px, so this is cosmetic for training but should be right in the spec; `qa_flags` not needed.
10. **`#18 imaging`** - PolypsSet is mixed *per sub-source*: `nbi` for `nbi_adenoma` and `set1_hyperplastic` (named NBI), `white-light` for `cvc300` (CVC-ColonDB) and `miccai2017_*` (GIANA, literature + inspected frames), `unknown` for `videos80` (mixture incl. cyan/NBI-like frames, not recorded per file). PolypGen `unknown`, CVC `white-light`. The column has no "how do we know" companion; I would put the basis in `extra_json.imaging_basis` or add `imaging_source` (same vocabulary as `location_source`).
11. **`#56/#57 video_id`, `#57 frame_index`** - draft: video rows + Kvasir-Capsule image rows. PolypsSet (XML `<path>` and val/test file numbers) and CVC have a video/sequence id and a source frame number for every frame; this is exactly the "provenance" use. I fill `video_id` for all three and `frame_index` for PolypsSet. Please document `frame_index` as "source-defined frame number (not guaranteed 0-based or contiguous)" for non-video-row datasets. **PolypGen cannot fill `frame_index`**: positive and negative frames of one `seqN` come from different numbering spaces (`seq14_EndoCV2021_seq14_460` vs `seq14_seq14_neg_00150`); single frames have only a running number. CVC: frame order inside a sequence is by `frame_id` but not proven temporal -> null.
12. **`#62 group_id`** - the format `<dataset>|<group>` clashes with groups that contain `|`; use `-`/`:` inside the group name (`polypsset|videos80-posttest-16`). **Merge known duplicate videos/cases into one group id** (PolypsSet `videos80 posttest 16` = `pretest 11`, 442 identical frames, both train; `cvc300` case 11 (test) = case 13 (train), 7 identical images -> `polypsset|cvc300-11+13`); keep the raw case in `extra_json.case_raw`.
13. **`#64 group_quality`** - define `exact`. Proposal: *exact = the group contains every frame of the same video/sequence (no known leakage inside the group), patient-level independence NOT implied*. With that definition PolypsSet cases (after the merges above), PolypGen `seqN` and CVC `sequence_id` are `exact`; PolypGen `centre-Cx` groups and the C1/C4 numeric ids are `proxy`. If `exact` is meant to be patient-level then CVC (31 sequences / 23 patients per literature) and PolypsSet pre/post pairs must be `proxy`.
14. **`#65 split_official`** - fine for PolypsSet (`train|val|test`); PolypGen and CVC null. R6 says the table never contains its own split; keep, but flag the known leaks (14 rows) with `split-leak-known`.
15. **`#55 image_md5` + `#66 dup_group_id` on mask rows** - HK mask rows carry the parent's `image_md5` (verified in `merge/merged-labels.csv`: mask `cju0qkwl...` and its parent have the same md5). If `dup_group_id` is derived from `image_md5` over the whole table, each image/mask pair forms a duplicate group. Define: `dup_group_id` only for `source_type=image` (and `video_frame` if wanted); mask rows null.
16. **`#67 qa_flags` vocabulary** - I need these tokens (please fix a controlled list): `annotation-missing` (641 PolypGen positives), `dup-label-conflict` (PolypGen C5 `..50000140`/`..141`: identical bytes, 4 vs 1 instance), `split-leak-known` (7 test + 7 train PolypsSet images), `mask-grey-noise` (138 CVC masks), `near-dup-cross-group` (2 PolypGen C2 single frames ~ `seq12`/`seq15` frames), `overlay-text-possible`. **Do not use `burned-in-text` per row** unless detected per image: I only saw overlays in samples (NBI sub-sets, PolypGen C3/seq11); a row-level flag would be a guess.
17. **`#35 n_labels` / `#28 findings_all` / `#29 class_counts_json`** - fine for me. For detection images with no boxes use `class_counts_json={}` (annotated-empty) vs null (unknown). Keys = native bbox label (`adenomatous`, `polyp`), not the harmonised slug (the harmonised one is in `bboxes_json[].finding`).
18. **Superset claim** - `source_dataset` (old #3) is not in the draft; `#3 dataset` + `#4 source_subset` replace it. Say "renamed" instead of "all kept".

## 3. Information with no column / `extra_json` keys

| dataset | key (extra_json unless noted) | content | own column? |
|---|---|---|---|
| PolypsSet | `case_raw` | the video/case from the XML `<path>` (`80_Videos_Frames/posttest/31`) | no (group/video ids carry it) |
| PolypsSet | `orig_filename`, `orig_folder` | XML `filename` (`245.png`, `adenoma_163.jpg`) and `folder` | no |
| PolypsSet | `histology_case` | case-level histology, also for negative frames (their `finding_subtype` stays null) | no |
| PolypsSet | `negative_basis` | `empty-xml` | no |
| PolypsSet | `dup_partner` | path of the byte-identical twin | no (`dup_group_id`) |
| PolypsSet | **do not store** `<path>` verbatim | contains local user names (`mfathan`, `krushipatel`) | - |
| PolypsSet | (not stored) `pose`, `truncated`, `difficult`, `segmented`, `depth` | constants | - |
| PolypGen | `centre` (C1..C6, only 2,700 of 8,037 rows have it: 1,537 single frames + C5 negatives 731 + C6 positives 432) | acquisition centre | **YES, column `centre`**: needed by `group_kind=centre`, domain-shift splits; PolypsSet/others could use it too |
| PolypGen | `name_prefix`, `orig_name`, `sub_sequence` | file-name parts (`seq14` / `seq14_neg`) | no |
| PolypGen | `instance_areas_px` | per-instance areas | optional: allow `area_px` inside `bboxes_json` items for mask-derived boxes instead |
| PolypGen | tag list | `institute`, `positive`/`negative`, `sequence` | no (mapped to `centre`, `finding`, `group_id`) |
| CVC | `frame_id`, `sequence_id` | native ids | no |
| CVC | `alt_paths` | the redundant TIF copies | no |
| CVC | (qa flag) `mask-grey-noise`; optionally `mask_noise_px` count | | no |
| all three | `n_instances` | = `n_boxes` | no |

Nothing important would be lost; the only item I would promote to a column is **`centre`** (and `n_boxes=null` semantics).

## 4. Opinions on rules and open decisions

* **R1 (row units).** Agree that boxes never get rows and PolypGen gets no mask rows (that was my proposal too). But R1 as written ties `segmentation_mask` rows to the *storage form* of the mask: CVC (612 PNG masks) -> 612 extra rows, PolypGen (3,121 images with masks inside JSON) -> 0 extra rows, although the annotation is the same kind. Then `source_type='segmentation_mask'` counts say nothing about masks. Two coherent options: **(A, my choice) fold**: one `image` row per image, `has_mask`/`mask_path`/`mask_format`/`mask_*` on it - lossless, because the existing HK table already repeats every mask/box column on the image row (verified: image row and mask row of `cju0qkwl...` have identical `has_mask`, boxes, `mask_*`, `image_md5`); the mask row only adds `file_path`/`file_size` of the mask file (use `mask_path`; add `mask_size_bytes` if wanted). It removes double-counting, `parent_image_sample_id`, `mask_sample_id`, `label_level=mask` and the `dup_group_id` problem. (B) keep for HK/ETIS/CVC and add virtual mask rows for PolypGen (3,121, `file_path`=JSON) - consistent but pure duplication. The draft's mixed default is the worst of the three.
* **Decision 7 (keep 1,000+612+196+643 mask rows).** See above: acceptable only with the rules "training counts use `source_type='image'`", `dup_group_id` null on mask rows, and PolypGen handled the same way; otherwise fold.
* **R2.** Agree. PolypsSet orphans (798 XML-only) are logged, not rows; please give the log location/format (e.g. `docs/orphans/polypsset.csv`: xml path, case, class, box). PolypsSet exact duplicates stay as rows with `dup_group_id`.
* **R3 (`background` / `no-polyp-annotated`).** Acceptable for both datasets. Needs: `finding_harmonization=derived` for PolypsSet, `label_confidence=medium` (empty XML may be an unannotated polyp) vs PolypGen explicit negatives `high`. The name is fine; I would not call it `normal`. One caution: `is_negative=True` pools these with Hyper-Kvasir/Crohn `normal-mucosa`; for a classification model the `category` (`background` vs `normal`) must stay visible.
* **R4 (positives without geometry).** Acceptable (`has_mask=False`, `qa_flags=annotation-missing`) **plus** `n_boxes=null`, `annotation_types=class`, `label_confidence=low`; never `is_negative`.
* **R5.** Agree (all three are dataset-constant colon, `location_source=dataset-constant`).
* **R6.** Agree; add that `group_id` must already contain the merges of known duplicate videos (2.12), otherwise "split by group" still leaks. I verified the shipped PolypsSet split is case-disjoint but not duplicate-free.
* **R7.** No opinion (HK).
* **`polyp_histology` (my report) vs `#25 finding_subtype`.** Draft default (`finding_harmonized=polyps`, `finding_subtype=adenomatous|hyperplastic`, `finding_parent=polyps`) is acceptable; no separate column needed. Note: histology is a property of the *case*; negatives get `finding_subtype=null` and the case histology in `extra_json.histology_case`.
* **`no-polyp-annotated`** - accepted as the shared slug for PolypsSet and PolypGen negatives.
* **Box convention** - inclusive pixel indices, top-left origin: agree. VOC rule must be `max-1` not "as shipped + clip" (2.9). Mask-derived boxes: per 8-connected component, >= 10 px (2.8). PolypGen bitmaps are tight per-instance, `xmax = ox+w-1` is already inclusive.
* **Decisions 1-4, 6** concern capsule/EAD data - no opinion. **5**: consistent with mine (all three of my datasets emit `polyps`; `finding_parent=polyps`). **8 (block-proxy groups)**: acceptable; for PolypGen single frames of C2/C3/C5/C6 I use the same idea (`group_kind=centre`, `group_quality=proxy`), and I would additionally keep `centre` as a column.

## 5. Wrong / ambiguous / painful for adapters

1. **No machine-readable column list.** Prose with "target ~107", unnumbered boxes/masks block, "#71-82 ... (+ any existing ones)". The adapter author needs a file (name, dtype, nullable, allowed values/regex, source of truth) and a validator. Without it each adapter will drift.
2. **Redundant representations of one fact**: `has_bbox`/`n_boxes`/`bboxes_json`/`class_counts_json`/`annotation_types`; `has_mask`/`mask_path`/`annotation_types`; `finding_harmonized`/`findings_all`/`finding_2*`/`n_labels`. Add validator rules (`has_bbox <=> n_boxes>0`, `n_boxes` = length of `bboxes_json`, `has_mask <=> mask_format not null`, `findings_all` contains `finding_harmonized`).
3. **`finding_in_image_vocab`** (2.7) - trivially True.
4. **`sample_id` for datasets without a unique stem** - needs the path-based `item_id` rule (2.2).
5. **`group_id` separator** (2.12) and the duplicate-video merge rule.
6. **Orphan log** location/format unspecified (R2).
7. **`file_path` relative to `data_to_merge/`** changes the old table (relative to project root, `out/...`); say that the HK rows are re-pathed (and that `out/` vs `data_to_merge/hyper-kvasir` are different trees).
8. **R7** contradicts `MERGE_PROCESS.md` (10 frames/video) - already noted by the draft; mention which is authoritative.
9. **Enumerations are incomplete**: `qa_flags` (need controlled list), `annotation_format` (add `mask-png` for CVC image rows? it is listed; add `json-polygon`/`png-instance` only if other readers need them), `mask_format` / `mask_encoding` (no value lists), `bbox_source` (0.6), `group_kind` (no `patient`; add it if any dataset has patient ids - none of mine does).
10. **License**: PolypsSet/PolypGen `unknown` is honest (no licence file shipped); CVC `research-only` rests on the TIFF copyright tag - keep the evidence in `extra_json.license_evidence` or the registry.
