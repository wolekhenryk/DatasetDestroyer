# polypsset (`PolypsSet/`)

Adapter `unify/adapters/polypsset.py`, vocabulary `unify/vocab/polypsset.csv`. Analysis and evidence: `docs/reports/PolypsSet.md`. Overlay/independent check: `unify/tools/polyp_adapters_check.py`.

## Source
Li K., Fathan M.I., Patel K. et al., *Colonoscopy polyp detection and classification: Dataset creation and comparative evaluations*, PLOS ONE 2021 (arXiv 2104.10824). The folder has no README and no licence file -> `license = unknown` (the data merge several public polyp video sets, each with its own terms: MICCAI/GIANA 2017, CVC-ColonDB, KUMC videos, NBI sets). Colonoscopy video frames with Pascal-VOC boxes and a polyp histology class.

## Layout used / ignored
```
PolypsSet/<split>/Image/[<k>/]<n>.jpg        used   (split = train2019 | val2019 | test2019; train flat, val/test one sub-folder k per video)
PolypsSet/<split>/Annotation/[<k>/]<n>.xml   used   (Pascal-VOC, one per image)
.DS_Store                                     ignored
```
* Pairing key = `<split>/<k>/<n>`. 37,899 JPEGs, all with an XML. **798 XMLs (val 376, test 422) have no JPEG -> no rows** (`ctx.warn`; they hold 790 boxes that are lost; the delivered val/test are sub-sampled copies of the original ones).
* The XML `<path>` (author machine paths with user names), `<folder>`, `<database>`, `pose/truncated/difficult/segmented` are NOT stored. `<path>` is parsed only to derive sub-set, case and source frame number (regexes in the adapter); every one of the 37,899 paths matches a rule.

## Row units and counts (`META["expected"]`)
| source_type | rows |
|---|--:|
| image | **37,899** (train 28,773, val 4,254, test 4,872) |

No mask rows (no masks), no video frames. One row per image, the box (max one per image) lives in the row.

## Label semantics
| native | rows | category | finding / harmonized / subtype | notes |
|---|--:|---|---|---|
| `<object><name>adenomatous` | 19,240 | pathological-findings | `adenomatous` / `polyps` / subtype `adenomatous` | polyp with adenomatous histology; **histology is constant per video/case** (0 of 153 cases mix both), not verified per frame |
| `<object><name>hyperplastic` | 16,741 | pathological-findings | `hyperplastic` / `polyps` / `hyperplastic` | idem |
| XML without `<object>` | 1,918 | **background** | `no-polyp-annotated` (derived, confidence medium) | frame of a polyp video where no polyp was boxed. `annotation_types = bbox`, `n_boxes = 0` (annotated-empty), `class_counts_json = {}`. NOT verified normal mucosa; may contain an unannotated polyp. `finding_raw = no-object-in-xml` (a convention: the column must be non-null) |

`finding_parent = polyps`, `is_negative` False / True derived. Boxes: Pascal-VOC with **half-open max edges** (measured on this data: `xmax==W` 60 boxes vs `W-1` 5, `ymax==H` 312 vs `H-1` 61, never above) -> `c.voc_to_box` subtracts 1 from xmax/ymax; numbers are stripped (` 113`). `bbox_source = annotator`, `annotation_format = voc-xml`, `bboxes_json` items `{"label": "adenomatous", "finding": "polyps", ...}`.

## Location / imaging
Dataset-constant colon / lower-gi-tract (`location_source = dataset-constant`); no segment per file. `procedure = colonoscopy`. `imaging = nbi` for `nbi_adenoma` and `set1_hyperplastic` (5,917 rows; named NBI in the source folders), **`unknown` for the rest** (white light for MICCAI/CVC-ColonDB sets and a mixture incl. cyan frames for `videos80`, but not recorded per file -> not guessed).

## Origin sub-sets (`source_subset`) and videos
| source_subset | images | cases (videos) | size | boxes adenomatous / hyperplastic | negatives |
|---|--:|--:|---|---|--:|
| videos80 (KUMC-like, pre/post-test videos) | 24,412 | 76 | 592x464, 544x448 | 12,106 / 11,632 | 674 |
| miccai2017_train | 4,798 | 16 | 384x288 | 1,610 / 2,476 | 712 |
| miccai2017_test | 2,478 | 7 | 384x288 | 1,625 / 368 | 485 |
| nbi_adenoma | 3,676 | 24 | 768x576 | 3,676 / 0 | 0 |
| set1_hyperplastic | 2,241 | 15 | 768x576 | 0 / 2,194 | 47 |
| cvc300 (= **CVC-ColonDB**, not CVC-ClinicDB) | 294 | 15 | 574x500 | 223 / 71 | 0 |

## Grouping, splits, known leaks
* `video_id` = case (`videos80-posttest-31`, `miccai2017_test-3`, `nbi_adenoma-38`, `set1_hyperplastic-8`, `cvc300-11`), `frame_index` = **source-defined frame number** from the original file name (`245.png` -> 245; NBI: `adenoma_163.jpg` -> 163), not necessarily 0-based or contiguous; never null for the 37,899 rows.
* `group_id = polypsset:<case>`, `group_kind = video`, `group_quality = exact` (all frames of a video share the id; patient identity is NOT known - pre-test / post-test and GIANA videos can share patients). 151 groups.
* **Duplicate videos are merged**: cases that share >= 3 byte-identical images are one video: `videos80-posttest-16 = videos80-pretest-11` (442 identical frame pairs, both in train) and `cvc300-11 = cvc300-13` (7 identical images, case 11 in test, case 13 in train). Group ids: `polypsset:videos80-posttest-16+videos80-pretest-11`, `polypsset:cvc300-11+cvc300-13`. `qa_flags = duplicate-video` on all 926 frames of the merged videos (892 + 34); `video_id`/`extra_json.case` keep the original case.
* `split_official` = `train|val|test` from the folder (train 113 groups, val 17, test 22). The shipped split is case-disjoint **except** the merged group `cvc300-11+13` (test + train). **`split-leak-known`** is set on the 7 test images of cvc300 case 11 and their 7 byte-identical train twins (14 rows). If you respect `split_official`, drop or move those 14 rows; if you split by `group_id`, the leak disappears by construction.
* Frames of a video are near-duplicates: split by `group_id`, never by row. train2019 file numbers are random (not temporal), val/test sub-folders are videos in temporal order.

## Duplicates and conflicts
923 image rows (461 groups) share bytes with another image (`dup_group_id`): 449 groups join two different cases (the two merged pairs), 12 are identical frames inside one case; 454 groups are train-only, 7 train+test. **All 461 groups get `dup-box-conflict`**: the identical pictures carry slightly different boxes (IoU median 0.88, min 0.35, never identical) - this is annotation noise, not a label conflict (classes agree: no `dup-label-conflict`).

## `extra_json` keys
`case` (e.g. `videos80-posttest-31`), `orig_filename` (source file name, e.g. `245.png`), `histology_case` (class of the case, also on its negative frames, whose `finding_subtype` is empty), `merged_group` (merged group name, only for the two merged pairs), `negative_basis` (`xml without object`, negatives only).

## Pitfalls
* Burned-in text (patient-info panels, "NBI" tag, partly blurred) and wide black borders occur in the NBI sub-sets and some MICCAI/other frames (dataset-wide fact, not flagged per row); image sizes differ per sub-set (5 sizes).
* `no-polyp-annotated` frames are polyp-video frames, not clean normal mucosa; do not pool them with `normal-mucosa` without looking at `category`.
* The 798 orphan XMLs mean this copy is not the complete original val/test.
* `cvc300` frames are CVC-ColonDB images: overlap with other CVC-ColonDB copies is possible; no frame equals a CVC-ClinicDB or PolypGen frame (thumbnail test in `docs/reports/PolypsSet.md`).
* Adapter note: it calls `ctx.md5` (cached, ~5 s cold) to find duplicate videos and split leaks, also under `--no-md5`.
