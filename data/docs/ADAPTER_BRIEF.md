# Adapter brief - implementing the unified-table adapter for your datasets

You analysed the datasets (`docs/reports/`) and reviewed the draft schema (`docs/reviews/`). The schema is now locked in code. Your job: implement, run and document the adapter of each of your datasets, following `docs/ADD_A_DATASET.md` (which is itself under test - report every place where it or the template misled you or was painful).

## Read first (in this order)
1. `docs/ADD_A_DATASET.md` - process + rules (row units, location, findings, geometry, groups, paths).
2. `docs/SCHEMA.md` - the 104 columns (generated from `unify/schema.py`; controlled vocabularies are at the top of that file).
3. `unify/adapters/_template.py` + `unify/vocab/_template.csv`; `unify/common.py` (helpers), `unify/context.py` (`ctx`), `unify/build.py::postprocess` (what is filled FOR you), `unify/validate.py` (what is checked).
4. Your own report and your review (your dataset-specific example rows are the specification of what each row should contain).

## What changed since the draft you reviewed
* 104 columns. New/changed: `centre` (acquisition site, e.g. PolypGen C1-C6), `device`, `mask_corner_pixel_removed` -> **`mask_noise_pixels_removed`** (Int64), `group_kind` also `dataset`, `group_quality` also `coarse`, `region_derived` has 6 values (`stomach|small-bowel|colon|stomach-or-small-bowel|small-bowel-or-colon|unknown`), `finding_harmonization` also `derived`, `bbox_source` only `annotator|mask-derived` (the file format goes to `annotation_format`, which may be a `|`-list), `group_id` separator is `:` (`<dataset>:<group>`), qa flags `dup-label-conflict` (class sets differ) and `dup-box-conflict` (same classes, different boxes) are set automatically for byte-identical images.
* `is_negative` is tri-state: True normal/background, False pathological-findings, null for landmarks / quality / therapeutic / artefact (derived by the runner). `finding_in_image_vocab` exists only on `video_frame` rows (derived). `n_labels` = filled label slots (`finding_2`/`category_2`), for multi-class detection rows the number of distinct classes; it is derived (`len(findings_all)`) unless you set it (Hyper-Kvasir must set it to reproduce the old values).
* **Mask rows**: one `segmentation_mask` row per image that has a mask annotation, also for embedded masks (PolypGen: `file_path` = the annotation JSON, `mask_format='supervisely-bitmap-in-json'`). Mask rows of normal datasets inherit region/category/finding of the parent image; EAD2020 mask rows take their classes from the non-empty mask pages (validator exception for dataset `ead2020-train`).
* **Boxes**: `yolo_to_box(..., convention="continuous"|"one-based-inclusive")` snaps near-integers first (6-decimal YOLO noise); EAD2020 is `one-based-inclusive` for the Phase-II boxes (assume it for the rest, document it). `voc_to_box` treats VOC max edges as half-open (PolypsSet: subtract 1). The union `bbox_*` columns are always filled when there are boxes (for multi-class rows use `bboxes_json`).
* Multi-class rows: `ctx.multi_label_fields(counts, raw, areas)` - primary = most boxes, then largest total area, then lowest class id; `finding` must come from the vocabulary (an expanded slug such as `ulcer`), the cryptic native code (`U>10`) goes to `finding_raw` - never `slugify()` a code.
* Group ids: `<dataset>:<group>`; merge known-duplicate videos into one group; see-ai blocks of 500 consecutive image numbers and Crohn blocks of 200 (proxy), duplicate pairs merged (union-find); ETIS = one group (`dataset` / `coarse`); EAD2020 `framesOnly` frames: `block-proxy` blocks of 100 consecutive frame numbers (proxy), sequences = exact.
* Licence strings (column `license`): Hyper-Kvasir `CC BY 4.0`; EAD2020 `CC BY-NC-SA 4.0`; DataCrohnIPI `CC BY-NC-ND 2.0 (research use only)`; CVC-ClinicDB `research and educational use only (Hospital Clinic Barcelona / CVC)`; every dataset without a licence file: `unknown`.
* Hyper-Kvasir video metadata snapshot: `unify/data/hyper-kvasir-video-metadata.csv` (copy of the project-root `video-metadata.csv`; regenerate with `video_meta.py` if the videos change).

## Naming
| folder | META["dataset"] | module in `unify/adapters/` | vocab CSV in `unify/vocab/` |
|---|---|---|---|
| hyper-kvasir | `hyper-kvasir` | `hyper_kvasir.py` | `hyper-kvasir.csv` |
| kvasir-capsule | `kvasir-capsule` | `kvasir_capsule.py` | `kvasir-capsule.csv` |
| ETIS-LaribPolypDB | `etis-laribpolypdb` | `etis_laribpolypdb.py` | `etis-laribpolypdb.csv` |
| PolypsSet | `polypsset` | `polypsset.py` | `polypsset.csv` |
| polypgen-ninja | `polypgen-ninja` | `polypgen_ninja.py` | `polypgen-ninja.csv` |
| CVC-ClinicDB | `cvc-clinicdb` | `cvc_clinicdb.py` | `cvc-clinicdb.csv` |
| see-ai | `see-ai` | `see_ai.py` | `see-ai.csv` |
| EAD2020_train | `ead2020-train` | `ead2020_train.py` | `ead2020-train.csv` |
| DataCrohnIPI | `datacrohnipi` | `datacrohnipi.py` | `datacrohnipi.csv` |

## Deliverables per dataset
1. `unify/adapters/<module>.py` (+ `unify/vocab/<dataset>.csv`) - deterministic (sorted traversal, no timestamps, no random), runs in minutes, reads no pixels more than needed, uses `ctx.warn` for orphans/oddities, never invents rows. `META["expected"]` = the verified row counts.
2. `docs/datasets/<dataset>.md` - the facts a user needs when training on it (see the end of ADD_A_DATASET.md): layout used / ignored, label semantics, location + how known, counts, grouping/split guidance and known leaks, `extra_json` keys, pitfalls, licence, row counts.
3. If you wrote a verification script worth keeping (e.g. old-vs-new Hyper-Kvasir comparison, box-overlay check), put it in `unify/tools/<name>.py`.

## How to run (always write outputs to the scratchpad, never over the real table)
```bash
cd /Users/henrykwolek/Studia/pb/data_to_merge          # NOT inside a dataset folder
../.venv/bin/python -m unify --only <dataset> --out <scratchpad>/<dataset>.csv          # full run incl. md5 + validation
../.venv/bin/python -m unify --only <dataset> --out <scratchpad>/<dataset>.csv --no-md5 --no-validate   # fast iteration
```
Scratchpad: `/private/tmp/claude-501/-Users-henrykwolek-Studia-pb/3de6e3f3-076e-4a0c-b4dc-e92334ae00ce/scratchpad/`. Several of you run builds in parallel: that is safe (the md5 cache merges atomically), but **do not edit shared files** (`unify/schema.py`, `common.py`, `context.py`, `build.py`, `validate.py`, `registry.py`, other datasets' files, `docs/SCHEMA.md`, `docs/ADD_A_DATASET.md`) - write what you need changed as a precise request in your final message (a local workaround meanwhile is fine). The dataset folders stay read-only.

## Acceptance (you are done when)
* `python -m unify --only <dataset> ...` finishes with **all validation checks PASS** (including `META["expected"]`);
* the numbers equal the ones in your report (explain any difference);
* you spot-checked >= 5 random rows per row type against the raw files (and for boxes/masks looked at an overlay of a few);
* the output CSV is byte-identical across two runs;
* Hyper-Kvasir only: new vs old `merge/merged-labels.csv` compared per column with the old->new mapping from your review (61 identical + the 15 documented changes), script kept in `unify/tools/`.

## Final message (plain text, <= 350 words)
Per dataset: rows by `source_type`, validation status, deviations from your report, `extra_json` keys; then **friction log** (what in ADD_A_DATASET.md / the template / helpers was missing, wrong or painful, with concrete suggestions) and your **requests for shared files** (exact change wanted).
