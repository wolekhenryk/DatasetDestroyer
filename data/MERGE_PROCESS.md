# Merging nine endoscopy datasets into one label table - process documentation

Everything in this folder (`data_to_merge/`) except the nine dataset folders was produced for this merge; **the datasets themselves were only read, never modified.** Existing folders (`merge/`, `out/`, `data/`) were not touched.

| path | what it is |
|---|---|
| `merge_datasets.ipynb` | runs the merge: executed notebook (outputs saved, ~70 s), the thin driver of the `unify/` package |
| `merged-labels.csv` | **the result: 142,183 rows x 104 columns**, UTF-8, LF, header, no index, 147 MB, byte-for-byte reproducible |
| `MERGE_PROCESS.md` | this document |
| `unify/` | the code: `schema.py` (columns + vocabularies), `common.py` (helpers), `context.py`, `registry.py`, `build.py` (generic post-processing), `validate.py` (121 checks), `adapters/<dataset>.py` x9 + `_template.py`, `vocab/<dataset>.csv` x9 + `_template.csv`, `tools/` (self-test, per-dataset verification scripts), `data/` (Hyper-Kvasir video metadata snapshot), `cache/` (md5 cache, safe to delete) |
| `docs/SCHEMA.md` | column dictionary (generated from `unify/schema.py`) |
| `docs/ADD_A_DATASET.md` | **how to plug in a new dataset** (7 steps + the rules) |
| `docs/datasets/<dataset>.md` | per-dataset facts a user needs when training on it |
| `docs/reports/<dataset>.md` | the readers' full analysis of each dataset (evidence for every claim) |
| `docs/reviews/`, `docs/READER_BRIEF.md`, `docs/ADAPTER_BRIEF.md`, `docs/SCHEMA_DRAFT.md` | the agent process (briefs, schema reviews, the superseded first draft) |

## 1. Result at a glance

One table in which **every row is exactly one of** `image`, `video_frame`, `segmentation_mask` (`source_type`) and belongs to one of nine datasets (`dataset`).

| dataset | image | video_frame | segmentation_mask | total |
|---|--:|--:|--:|--:|
| cvc-clinicdb | 612 | | 612 | 1,224 |
| datacrohnipi | 3,484 | | | 3,484 |
| ead2020-train | 2,531 | | 643 | 3,174 |
| etis-laribpolypdb | 196 | | 196 | 392 |
| hyper-kvasir | 10,662 | 7,480 | 1,000 | 19,142 |
| kvasir-capsule | 47,229 | | | 47,229 |
| polypgen-ninja | 8,037 | | 3,121 | 11,158 |
| polypsset | 37,899 | | | 37,899 |
| see-ai | 18,481 | | | 18,481 |
| **total** | **129,131** | **7,480** | **5,572** | **142,183** |

**Counting images:** filter `source_type == "image"` (129,131 pictures). The 5,572 mask rows describe images that are *also* image rows (explicit duplication, as in the Hyper-Kvasir merge); the 7,480 frame rows are addressed frames of 374 Hyper-Kvasir clips (20 per clip), not extra pictures.

The three things the table makes explicit (image rows):

**WHAT is annotated** (`annotation_types`): class labels only - hyper-kvasir stills, kvasir-capsule, datacrohnipi; boxes - polypsset, see-ai, ead2020-train (+ masks); masks (+ derived boxes) - cvc-clinicdb, etis, polypgen-ninja, hyper-kvasir polyps; clip labels - hyper-kvasir videos.

**WHERE** (`region`):

| dataset | lower-gi-tract | upper-gi-tract | small-bowel | unknown |
|---|--:|--:|--:|--:|
| cvc-clinicdb / etis / polypgen / polypsset | 612 / 196 / 8,037 / 37,899 | | | |
| hyper-kvasir | 7,210 | 3,452 | | |
| kvasir-capsule | 4,189 (ileocecal valve) | 1,538 (pylorus, ampulla) | | 41,502 |
| see-ai / datacrohnipi | | | 18,481 / 3,484 | |
| ead2020-train | | | | 2,531 |

**WHAT finding** (`category`, images): pathological-findings 61,139 - normal 36,462 (Crohn `N` 2,124 + Kvasir-Capsule `Normal clean mucosa` 34,338) - background 12,354 (frames without an annotation of the target class: polypsset 1,918, polypgen 4,275, see-ai 6,161) - anatomical-landmarks 9,823 - quality-of-mucosal-views 4,831 - therapeutic-interventions 1,991 - artefact 2,531 (EAD2020 only). Most frequent `finding_parent`: polyps 43,707 - normal-mucosa 36,462 - no-polyp-annotated 6,193 - no-lesion-annotated 6,161 - erosion 4,434 - ileocecal-valve 4,189 - reduced-view 2,906 - ulcer 1,810 - angiectasia 1,596 (full per-class table: notebook section 6).

Procedure x imaging (images): colonoscopy 53,954 (white light 6,027, chromoscopy 1,991, NBI 5,917, unknown 40,019) - capsule whole-GI 47,229 - capsule small-bowel 21,965 - gastroscopy 3,452 - unknown 2,531.

## 2. How it was made - agents and decisions

1. **Three reader agents** analysed three datasets each in parallel (checklist: `docs/READER_BRIEF.md`; reports in `docs/reports/`): layout, every annotation source with exact columns and quirks, *what each annotation is*, *location*, *findings*, linking keys, grouping ids, duplicates (within and across datasets), proposed mapping. All claims were verified by scripts, not README text.
2. **Consolidation of the columns.** I drafted the unified schema as a superset of the 76 Hyper-Kvasir columns (`docs/SCHEMA_DRAFT.md`) with default rules and 8 open decisions; each reader reviewed it against its own datasets by filling concrete example rows (`docs/reviews/reader{1,2,3}-schema-review.md`). **Changes the reviews forced:**
   * Reader 3 found my YOLO conversion wrong for integer-pixel sources (6-decimal noise flipped `floor`/`ceil` on 7,408 of 31,069 EAD boxes, i.e. 24 %) and that EAD2020 boxes are 1-based inclusive -> `yolo_to_box` snaps near-integers and has a `one-based-inclusive` convention.
   * Reader 2 measured that PolypsSet's VOC max edges are half-open (`xmax == W` in 60 boxes vs `W-1` in 5) -> `voc_to_box` subtracts 1; my first rule would have shifted 356 boxes.
   * `is_negative` became tri-state (landmarks / quality / therapeutic are not "positive"); `finding_in_image_vocab` only on video frames (it was trivially true elsewhere); `region_derived` got 6 values; `group_kind` `dataset`, `group_quality` `coarse`; `n_labels` counts label slots; `mask_corner_pixel_removed` -> `mask_noise_pixels_removed`; `bbox_source` reduced to `annotator`/`mask-derived`; new columns `centre`, `device`; `group_id` separator `:`; qa flags split into `dup-label-conflict` / `dup-box-conflict`; `item_id` unique per dataset.
   * **Declined:** Readers 1 and 2 proposed folding mask rows into the image rows. I kept one `segmentation_mask` row per image with a mask - for *every* dataset including embedded masks (PolypGen) - because the old table has them, the user asked for "what something is (label, mask)" to be explicit, and filtering on `source_type` undoes it.
3. **Adapters.** The readers then implemented one adapter + vocabulary + doc per dataset following `docs/ADD_A_DATASET.md`, each verified against the raw files (>= 5 random rows per row type, box/mask overlays, byte-identical reruns). Their friction logs fixed the validator (an empty-mask crash, `none` wrongly treated as NA-like), the duplicate-box flag (now IoU based: slightly different outlines of one object are not a conflict), made `META["expected"]` follow build parameters and added the "notes from the first adapters" to the guide.
4. **Hyper-Kvasir** was re-created by porting `merge/merge_labels.ipynb`; the result equals the old `merge/merged-labels.csv` column by column (75 columns identical or mechanically mapped; the only value change is `bbox_xmax/ymax`, see section 8).

## 3. The nine datasets (details: `docs/datasets/<dataset>.md`)

| dataset | what it is | annotation | location | findings | grouping for splits | licence |
|---|---|---|---|---|---|---|
| hyper-kvasir | Hyper-Kvasir labelled part | 10,662 image classes (23), 374 clip labels (+ 20 frames each), 1,000 polyp masks + boxes | Organ column: lower 7,210 / upper 3,452 stills | landmarks, polyps, UC grades, oesophagitis, Barrett, BBPS, dyed polyps, therapeutic video classes | clips: `video` exact; stills: none | CC BY 4.0 |
| kvasir-capsule | capsule endoscopy frames | class = folder (14 classes), 9 frames in two folders | whole GI; only 3 landmark classes carry a location (`region_derived` = heuristic zone from landmark order) | normal clean mucosa 34,338, 10 lesion/blood/foreign-body classes, reduced view | source video, 43 groups, exact | unknown |
| etis-laribpolypdb | 196 colonoscopy frames, all with polyp | binary masks (0/255), boxes derived | colon | polyp only | one group (`dataset`/`coarse`); 3 identical images with different masks | unknown |
| polypsset | video frames of polyp sets (MICCAI 2017, KUMC 80 videos, NBI sets, CVC-ColonDB) | VOC boxes, 1 per image | colon | polyp (adenomatous / hyperplastic in `finding_subtype`), 1,918 frames without box | 151 case groups exact; shipped train/val/test; 14 + 926 flagged leak/duplicate-video rows | unknown |
| polypgen-ninja | PolypGen as Dataset Ninja export | per-instance bitmaps inside JSON (3,121 mask rows), boxes derived | colon | polyp; 4,275 negatives; 641 positives without mask (`annotation-missing`) | 23 sequences exact, C1/C4 cases proxy, centres coarse | unknown |
| cvc-clinicdb | 612 frames, 29 sequences | binary masks, boxes derived | colon | polyp, always positive | sequence, exact | research / educational use only |
| see-ai | PillCam SB3 small-bowel capsule | YOLO boxes, 12 classes, up to 3 per image | small bowel (segment unknown) | angiectasia, erosion, stenosis, lymphangiectasia, lymph follicle, SMT, polyp-like lesion, bleeding, diverticulum, erythema, foreign body, vein; 6,161 without lesion | blocks of 500, proxy; 121 duplicate pairs merged | unknown |
| ead2020-train | endoscopy artefact challenge | YOLO boxes (8 artefact classes) + 5-6 page masks | not annotated (mixed, incl. bladder) | **no pathology**: specularity, saturation, artifact, blur, contrast, bubbles, instrument, blood | 5 sequences exact, rest proxy | CC BY-NC-SA 4.0 |
| datacrohnipi | Crohn's disease capsule frames | image class (7) | small bowel | normal 2,124, erythema, oedema, aphthoid ulceration, ulcer 3-10 mm / >10 mm, stenosis | blocks of 200, proxy; shipped 5-fold leaks (47 near-duplicate pairs flagged) | CC BY-NC-ND 2.0 |

Ingested once only: EAD2020's 5,606 JPEGs are 2,531 pictures in overlapping folders (canonical folder `allDetection_training/bbox_images`); the 474 renamed `EAD2020_semantic_*` copies are linked to their canonical image by MD5. Not ingested: orphans (798 PolypsSet XMLs without image, 14 CrohnIPI images without row), SEE-AI's five `detected_*.mp4` (model predictions, not labels), Hyper-Kvasir's `unlabeled-images` (99,417 JPEGs, still in `out/`, not part of this folder).

## 4. Design and rationale

1. **One wide table, three explicit row types**, as in the Hyper-Kvasir merge; every row is self-explanatory (`dataset`, `label_source`, `label_level`, `row_description`, `license`).
2. **Adapters do only what is dataset-specific; the runner does the rest.** An adapter lists files, looks native classes up in a **vocabulary CSV** (one row per class: region, site, category, finding, harmonised finding, parent, subtype, confidence), and returns the columns it knows. `unify/build.py` fills file size/existence, image size, MD5 (cached), duplicates, `findings_all`, `is_negative`, `finding_in_image_vocab`, `sample_id`, defaults, schema order and dtypes. A class missing from the vocabulary stops the build with the row to add; `META["expected"]` row counts stop it when a dataset changes.
3. **Location is never guessed.** `region` holds what the dataset knows (`dataset-constant`, `folder`, `label-column`, `class-name`, `readme`); `unknown` is a value. The only heuristic (Kvasir-Capsule landmark order) lives in `region_derived`.
4. **Negatives are typed.** `normal` = an explicit normal class; `background` = a frame without an annotation of the target class ("no polyp annotated", *not* verified normal mucosa, `finding_harmonization = derived`).
5. **Raw and normalised side by side** (`finding_raw`/`finding`/`finding_harmonized`/`finding_parent`/`finding_subtype`); nothing is silently corrected. `finding_harmonized` is equal across datasets only where the meaning is the same (`polyps`, `erosion`, `angiectasia`, `ulcer`, `pylorus`, ...); `finding_parent` pools coarser (`ulcerative-colitis`, `esophagitis`, `ulcer`, `polyps` incl. `polyp-like-lesion`). Capsule and colonoscopy classes with the same slug are told apart by `procedure`/`region`.
6. **Geometry in one convention**: integer pixels, top-left origin, corner format, `xmax`/`ymax` inclusive; `bboxes_json` keeps per-box labels; `bbox_source` says annotator vs mask-derived (8-connected components >= 10 px); masks carry `mask_format` and `mask_encoding` (how to binarise) and noise handling is reported (`mask_noise_pixels_removed`).
7. **Leakage is a first-class concern.** `group_id` (`<dataset>:<group>`) + `group_kind` + `group_quality` (`exact` / `proxy` / `coarse` / `none`), `split_official`, `centre`, `dup_group_id`, and per-row `qa_flags`. The table never assigns train/val/test itself.
8. **Safe CSV reading/writing**: labels read with `keep_default_na=False`; the output is validated for NA-like strings, embedded newlines, absolute paths / user names; paths are relative POSIX to `data_to_merge/`. Read it with `unify.build.read_csv` or `pd.read_csv(path, keep_default_na=False, na_values=[""])`.
9. **Reproducible**: sorted traversal, no timestamps; the notebook and `python -m unify` produce a byte-identical file (md5 `c889216abbbc9dde8a42afc8ae33e427` at the time of writing).

## 5. Schema

104 columns in 9 groups - identity (9), WHAT is annotated (2), WHERE (8), WHAT finding (22), folder provenance (6), files and links (15), split safety and QA (8), pixel/video (12), boxes and masks (22). The full dictionary with dtypes and rules is **`docs/SCHEMA.md`** (generated from `unify/schema.py`, which also holds the controlled vocabularies: regions, categories, procedures, imaging, group kinds/qualities, qa flags).
All 75 Hyper-Kvasir columns except `source_dataset` (-> `dataset` + `source_subset`) are kept (`mask_corner_pixel_removed` became `mask_noise_pixels_removed`); changed semantics: `sample_id` gains the dataset (`image:hyper-kvasir:<uuid>`), paths are relative to `data_to_merge/`, `n_labels`/`finding_in_image_vocab`/`mask_noise_pixels_removed` as above.
Shortlist for a first training run: `sample_id, source_type, dataset, file_path, image_path, mask_path, region, site, procedure, imaging, category, finding_harmonized, finding_parent, findings_all, is_negative, bboxes_json, has_mask, width, height, group_id, group_quality, split_official, dup_group_id, qa_flags, license`.

## 6. Validation (121 checks, all PASS)

Generic (`unify/validate.py`): schema order and dtypes; `sample_id` non-null/unique/patterned; `label_level` vs `source_type`; frame keys and index range; video-only columns empty elsewhere; every controlled vocabulary; required non-null columns; `is_negative` polarity; group columns consistent and prefixed with the dataset; relative POSIX paths, `file_path`/`image_path`/`mask_path`/... exist on disk; no home paths or user names; no NA-like strings (exactly pandas' list, case-sensitive), no CR/LF, no stray whitespace; boxes parse, match `n_boxes` and the union box and lie inside the image (inclusive); mask statistics present, mask <-> image links 1:1 with equal size and inherited region/category; duplicate groups share one MD5 and appear only on image rows; every adapter's `META["expected"]` row counts. After writing: CSV round trip (schema dtypes, LF only, no BOM) equals the in-memory table.
Beyond that: `python -m unify.tools.selftest` (synthetic dataset through the whole pipeline); validator mutation tests (eight deliberate corruptions - all caught after one gap, `file_path` not checked on disk, was fixed); Hyper-Kvasir old-vs-new comparison script; per-dataset spot checks and overlays by the readers.

## 7. Cross-dataset duplicates and overlap

Exact duplicates (MD5 of all 129,131 image rows): 589 groups / 1,179 rows, **none spans two datasets**: within PolypsSet (461 groups: a duplicated video pair and 7 `cvc300` test images also in train), see-ai (121 pairs; 36 rows carry `dup-label-conflict`, 28 `dup-box-conflict`), PolypGen (4), ETIS (3), Kvasir-Capsule none (the 9 two-folder frames are one row with two labels). Re-encoded/resized copies were tested only by thumbnail similarity between the polyp sets (ETIS, CVC-ClinicDB, PolypGen, PolypsSet, Hyper-Kvasir lower-GI): no pair above the duplicate threshold; same-video-different-frame overlap cannot be excluded.

## 8. Known limitations and gotchas

* **`out/` no longer contains the labelled Hyper-Kvasir data** (moved into `data_to_merge/hyper-kvasir/`, verified byte-exact against the original `data/hk.zip`): `merge/merge_labels.ipynb` cannot be re-run as saved. `merge/MERGE_PROCESS.md` says 15,402 rows (10 frames per clip) but the saved `merge/merged-labels.csv` has 19,142 (20 frames); this build uses 20 (`FRAMES_PER_VIDEO`, one parameter).
* **Hyper-Kvasir boxes**: 116 JSON box edges on 113 images equal the image width/height (the old table kept them; the validator requires inclusive boxes inside the image) - `bbox_xmax/ymax` are clipped to W-1/H-1 and a warning says so.
* **Frames are addressed, not extracted** (Hyper-Kvasir): decode sequentially, never by time-seek; `frames_suspect` clips: see `timestamp_note`.
* **EAD2020 has no pathology labels** (artefact classes only, region unknown, includes non-GI frames) and is **CC BY-NC-SA**; **CrohnIPI is CC BY-NC-ND**; **five datasets state no licence in their folders** (`license = unknown`: Kvasir-Capsule, ETIS, PolypsSet, PolypGen, SEE-AI - check at the source before redistributing the table or derived data). `PolypsSet`/`PolypGen` annotation files contained user names / local paths, which were deliberately not copied.
* **Labels are coarse and sometimes weak**: `background` is not verified normal mucosa; CrohnIPI's `normal` comes from Crohn patients; PolypGen's 641 positive frames have no mask (`annotation-missing`); SEE-AI `lymph follicle` and `vein` are benign structures filed under pathological findings with `label_confidence = low`; Kvasir-Capsule `polyps` (55 frames from one video) is a small-bowel capsule polyp.
* **Split safely**: only `group_quality = exact` is leak-safe at the unit level (still not patient-level - no dataset gives a patient id). `proxy` (SEE-AI, CrohnIPI, EAD framesOnly, PolypGen C1/C4) may still leak; `none` (Hyper-Kvasir stills) cannot be grouped; ETIS is one group. Several Kvasir-Capsule classes live in 1-3 videos; the shipped CrohnIPI folds and PolypsSet splits have documented leaks (`split-leak-known`).
* **Domain gap and shortcuts**: capsule vs colonoscopy vs gastroscopy images differ strongly; burned-in text, ScopeGuide boxes, black corners and borders are dataset-specific (documented per dataset, not removed). SEE-AI's two export batches differ in black level and negative rate.
* **Mask-derived boxes** (CVC, ETIS, PolypGen) are not annotator boxes; EAD2020 `framesOnly` boxes are *assumed* 1-based inclusive (verified only on Phase-II data); SEE-AI boxes use the continuous convention (checked on border boxes).
* The CSV is 147 MB and most columns are empty for most rows by design (a column applies only to the row types / datasets that have it); read selected columns (`usecols`) for quick work.

## 9. How to rerun / extend

```bash
cd data_to_merge
../.venv/bin/python -m unify                       # all datasets -> merged-labels.csv (~1 min; first run also hashes ~10 GB for md5)
../.venv/bin/python -m unify --only cvc-clinicdb --out dev.csv --no-md5   # one dataset while developing
../.venv/bin/python -m unify --param FRAMES_PER_VIDEO=10                  # Hyper-Kvasir sampling (stride: --param FRAME_STRIDE=25)
../.venv/bin/python -m unify.tools.selftest                               # framework self-test, no data needed
../.venv/bin/jupyter nbconvert --to notebook --execute --inplace merge_datasets.ipynb   # the same, with overview tables
```
* **A new dataset**: copy it into `data_to_merge/`, run the build - it warns `folder 'X' has no adapter` - then follow `docs/ADD_A_DATASET.md` (analysis checklist -> vocabulary CSV -> adapter from `unify/adapters/_template.py` -> `META["expected"]` -> docs). No other file changes.
* **A changed dataset** fails loudly: unmapped class (add a vocabulary row), changed row counts (`META["expected"]`), failed validation check (the message names the rows).
* **A new column**: one line in `unify/schema.py`; other datasets leave it empty; regenerate `docs/SCHEMA.md`.
* `unify/cache/md5-cache.csv` is a pure accelerator (keyed by path, size, mtime); delete it to force re-hashing.
