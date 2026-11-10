# Plugging a new dataset into the unified table

Goal: a new dataset folder in `data_to_merge/` becomes rows of `merged-labels.csv` with **one adapter file + one vocabulary CSV** (+ one short doc).
No schema change, no notebook edit, no change to any other dataset. Time budget: an hour for a simple dataset, most of it spent *understanding* the data, not coding.

```
data_to_merge/
  <NewDataset>/                      the data, read-only
  unify/adapters/<new_dataset>.py    1. adapter  (copy _template.py)
  unify/vocab/<new-dataset>.csv      2. native class -> unified label  (copy vocab/_template.csv)
  docs/datasets/<new-dataset>.md     3. facts + decisions (what you found, what you chose and why)
```

## The 7 steps

1. **Analyse the data** with `docs/READER_BRIEF.md` (10-point checklist; verify with scripts, not from the README). Write the result to `docs/reports/<NewDataset>.md`. The three questions that must be answered before any code:
   **what is annotated** (class label / box / mask / clip label), **where in the body** (colon, stomach, small bowel, unknown - and *how you know*), **which findings** (polyp, normal mucosa, ulcer, artefact, ... with counts, and how negatives are marked).
2. **Check the unregistered-folder warning**: running the build prints `folder 'X' has no adapter` until step 4 is done.
3. **Write the vocabulary CSV** `unify/vocab/<dataset>.csv`, one row per native class (spreadsheet-editable). Required: `native_key`, `category`, `finding`. Optional: `region`, `site`, `finding_harmonized`, `finding_parent`, `finding_subtype`, `finding_harmonization`, `label_confidence`, `imaging`, `procedure`, `location_source`, `note`. Empty cells fall back to the adapter's META defaults.
   Re-use an existing `finding_harmonized` slug **only if the meaning is the same** (see `docs/SCHEMA.md` and the other vocab CSVs: `polyps`, `erosion`, `angiectasia`, `ulcer`, `normal-mucosa`, ...). Put a coarser pooling key in `finding_parent`, a grade/size/histology in `finding_subtype`.
4. **Write the adapter** `unify/adapters/<dataset>.py` from `_template.py`: fill `META`, implement `build(ctx)`. Only emit what the dataset knows; leave the rest out (the runner fills file size, image size, md5, duplicates, `sample_id`, `findings_all`, `is_negative`, `file_exists`, schema order and dtypes).
5. **Run just your dataset** until clean:
   `cd data_to_merge && ../.venv/bin/python -m unify --only <dataset> --out dev.csv --no-md5` (add `--no-validate` while the row counts in `META["expected"]` are still 0). A new class that is not in the vocabulary stops the build with the CSV row to add.
6. **Set `META["expected"]`** to the verified row counts per `source_type`; from now on the build fails when the dataset changes.
7. **Run everything** (`python -m unify` or the notebook `merge_datasets.ipynb`) - all validation checks must pass - and write `docs/datasets/<dataset>.md` (see "What to document").

Python helpers you will use (all in `unify/common.py`): `slugify`, `read_csv_safe`, `natural_key`, `yolo_to_box`, `voc_to_box`, `clip_box`, `box_columns`, `load_mask`, `clean_mask`, `mask_columns`, `mask_derived_boxes`, `connected_components_boxes`, `make_sample_id`, `compact_json`, `pipe_join`; from `ctx`: `ctx.root`, `ctx.rel`, `ctx.label`, `ctx.multi_label_fields`, `ctx.row`, `ctx.md5`, `ctx.warn`, `ctx.params`.

## Rules (decisions already taken - follow them so datasets stay comparable)

**Row units.** `image` = one picture file (or one addressed video frame is `video_frame`, only for frames that live inside a video file and are *not* extracted). `segmentation_mask` = one row per image that has a mask annotation, *also when the mask is embedded in a JSON/XML* (then `file_path` = the annotation file and `mask_format` says how to decode); the image row is annotated too (`has_mask`, `mask_path`, `mask_sample_id`, mask statistics) and both rows link to each other. Boxes never get their own rows: they live in `bboxes_json` of the image row.
**Never create rows for orphans** (labels without file, file without label): call `ctx.warn(...)`.
**Duplicated pictures** (overlapping folders, same bytes stored twice): ingest the canonical copy only, document it; byte-identical images that remain are flagged automatically (`dup_group_id`, `dup-label-conflict`).

**Location.** `region` is the dataset's *authoritative* knowledge: `lower-gi-tract` (colon, rectum, terminal ileum/ileocecal valve), `upper-gi-tract` (oesophagus, stomach, duodenum), `small-bowel` (capsule/enteroscopy, segment unknown), `unknown`. Never guess: a heuristic goes into `region_derived` (Kvasir-Capsule only) or `extra_json`. `location_source` says how you know (`dataset-constant`, `folder`, `label-column`, `class-name`, `readme`, `unknown`). `procedure` and `imaging` describe how the picture was made.

**Findings.**
* `category`: the four Hyper-Kvasir categories plus `normal` (an explicit normal class, finding `normal-mucosa`), `background` (a frame *without* an annotation of the target class: finding `no-polyp-annotated` / `no-lesion-annotated`, `finding_harmonization = derived` - it is **not** verified normal mucosa), `artefact` (image-quality classes, not pathology).
* `finding` = slug of the native name, `finding_raw` = native text, `finding_harmonized` = canonical lesion type (only equal across datasets when the meaning is the same), `finding_parent` for pooling (`polyps` for `polyp-like-lesion`), `finding_subtype` for histology/grade/size.
* Several classes in one image: `ctx.multi_label_fields(counts)` fills `finding*` with the primary class (most boxes) and `findings_all` / `class_counts_json` / `n_labels` with all of them. A second label slot (`finding_2`) is for datasets that really have two label slots.
* `is_negative` is derived: True normal/background, False pathological-findings, null otherwise.

**Geometry.** Boxes: integer pixels, top-left origin, corner format, **`xmax`/`ymax` inclusive**. Convert with `yolo_to_box` (YOLO normalised) or `voc_to_box` (VOC with half-open max edges - *verify on the data*: count boxes with `xmax == W` vs `xmax == W-1`). `bbox_source` = `annotator` or `mask-derived`; the file format goes to `annotation_format` (`yolo-txt`, `voc-xml`, ...). Masks: binarise explicitly and write the rule to `mask_encoding` (`gray>127 white=polyp`), remove noise only with `clean_mask` and report `mask_noise_pixels_removed`.
`annotation_types` lists what the dataset *provides* for the row; `bbox`/`mask` are also listed when the annotator drew nothing (`n_boxes = 0` = annotated-empty). A positive frame whose geometry is missing: no `bbox`/`mask` in `annotation_types`, `n_boxes` empty, `qa_flags = annotation-missing`.

**Splits and leakage.** Frames of one video are near-duplicates. Give every row the strongest grouping id the data offers: `group_id = "<dataset>:<group>"` with `group_kind`/`group_quality`: `video|sequence|case` + `exact` (all frames of the unit share the id); `block-proxy` + `proxy` (contiguous blocks of chronological file numbers); `dataset` + `coarse` (one group for the whole dataset); none (leave empty). Merge videos known to be duplicated into one group. Shipped splits go to `split_official`, the acquisition site to `centre`. The table itself never assigns train/val/test.

**Paths and ids.** `file_path` etc. are POSIX paths relative to `data_to_merge/` (`ctx.rel`). `item_id` must be unique within (dataset, source_type) for image and mask rows (video-frame rows carry the video id; their `sample_id` adds the frame number): use the file path below the dataset folder without extension (including sub-folders such as `train2019/Image/1`) when file stems repeat. For an embedded mask (JSON/XML) `mask_path` = `annotation_path` = `file_path` of the mask row = the annotation file. `finding_raw` is never null: for a derived label (`no-polyp-annotated`) write the basis, e.g. `no-object-in-xml`. Never copy absolute paths or user names found in annotation files into the table (the validator rejects `/Users/`, `/home/`).
**Extras.** Facts without a column go to `extra_json` (`compact_json({...})`) and are listed in the dataset doc. If two datasets need the same extra, propose a column (one line in `unify/schema.py`).

## What to document in `docs/datasets/<dataset>.md`
Source/paper/licence, the file layout actually used (and what was ignored and why), label semantics (what each native class is), location and how it is known, row counts by `source_type`, grouping/split guidance and known leaks, duplicates and conflicts, `extra_json` keys, pitfalls (BOM/CRLF, bad paths, odd encodings), and the `META["expected"]` numbers.

## Common errors
| message | meaning |
|---|---|
| `UnmappedClass: native class 'x' has no row in <dataset>.csv` | add the row to the vocabulary CSV (the message shows the header) |
| `adapter produced columns that are not in SCHEMA_SPEC` | typo in a column name, or add the column to `unify/schema.py` |
| `<dataset>: expected image rows ... got ...` | the data changed or the adapter skips/doubles files: understand why, then update `META["expected"]` |
| `sample_id unique` fails | `item_id` is not unique within the dataset (use the relative path without extension) |
| `... in controlled vocabulary` | a value outside `schema.py` lists (`region`, `category`, ...): fix the value or extend the list consciously |
| `folder 'X' has no adapter` | a dataset is waiting to be plugged in |

## Notes from the first adapters (conventions that are easy to miss)
* **Vocabulary lookups**: `ctx.label(key)` returns a dict with ONLY the non-empty vocabulary fields - use `lab.get("finding_parent")`, not `lab["finding_parent"]`. Optional columns that are empty in the CSV fall back to the META defaults / the runner defaults.
* **Vocabulary rows that are not classes**: the CSV may also hold auxiliary lookups under your own key scheme (Hyper-Kvasir: `finding_2|<slug>` rows that only carry `finding_harmonized`, for the second video label and its typos). Keep such rows commented in the `note` column.
* **Overriding a vocabulary field**: `ctx.row("image", **lab, finding_harmonization="native")` raises a duplicate-keyword error. Merge instead: `ctx.row("image", **{**lab, "finding_harmonization": "native"}, ...)`.
* **`label_source`** is a path (relative to `data_to_merge/`) or a rule: `folder-name`, or `dataset-constant` when every item has the same label by definition (ETIS: all frames contain a polyp).
* **`META["expected"]`** may be a function of the build parameters: `expected=lambda p: {"image": 10662, "video_frame": 374 * p["FRAMES_PER_VIDEO"]}`.
* **Duplicate flags** (`dup_group_id`, `dup-label-conflict`, `dup-box-conflict`) are set on `image` rows only; the box conflict needs differing box counts or union boxes with IoU < 0.5 (slightly different outlines of the same object are annotation noise).
* **`finding_raw` is never null**; datasets without a native class text use a short description of the basis (`polyp` for ETIS, `no-object-in-xml` for derived negatives).
