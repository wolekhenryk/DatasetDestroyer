# Reader brief - how to analyse one dataset before merging it

This is the checklist given to every "reader" agent (and the checklist a human should follow when a **new dataset** is dropped into `data_to_merge/`).
The output of a reader is one report per dataset: `docs/reports/<dataset-folder-name>.md`.

## Context

Project root: `/Users/henrykwolek/Studia/pb` (student project; endoscopy / GI datasets used to train one model).
Earlier, the Hyper-Kvasir data in `out/` was merged into one tidy table - see `merge/MERGE_PROCESS.md` (read sections 5-6: the 76-column schema, the row types `image` / `video_frame` / `segmentation_mask`, raw + normalised labels, folder provenance) and `head merge/merged-labels.csv`.
More datasets were collected in `data_to_merge/`; the goal is an equivalent unified label table over all of them, used to **comprehensively train a model**. Readers analyse the datasets in parallel; a coordinator then consolidates the reports, designs the final columns and may send follow-up questions - be precise and evidence-based, say "unknown" instead of guessing.

## What to find out - for EVERY dataset

Verify everything by actually inspecting files and running scripts (counts, distinct values). READMEs and papers can be wrong or incomplete.

1. **Identity** - full name, origin/paper, modality (white light, NBI, capsule, ...), licence / readme caveats, size on disk, number of files per type and extension, directory layout (tree to a useful depth, with counts).
2. **Every annotation source** - path, format, delimiter / encoding / line endings / BOM, row count, exact column names; per column: meaning, dtype, distinct values with counts (or range). Quirks: whitespace, case variants, typos, NA-like strings, duplicates, files missing in either direction (orphans).
3. **WHAT each annotation IS** - be explicit per annotation kind: image-level class label / video-clip label / frame-level label / binary segmentation mask / multi-class mask / bounding box / polygon / keypoints / free text.
   *Masks:* file format, value encoding (0/255, 0/1, class ids, JPEG noise?), polarity (is the lesion white?), semantic vs per-instance.
   *Boxes:* file format, coordinate convention (corner xyxy / xywh / YOLO normalised centre / inclusive vs exclusive max), origin, class-id -> name mapping.
4. **LOCATION (anatomy)** - organ / segment each image shows (colon = lower GI, rectum, cecum, stomach, oesophagus, duodenum, small bowel, terminal ileum, ... ). State whether it is a dataset-wide constant or per file / per class, and *how you know* (README, folder, column). If it cannot be determined, say so.
5. **FINDING (pathology / content)** - every class / finding that occurs (polyp, normal mucosa, ulcer, erosion, instrument, artefact, bleeding, Crohn lesion, ...) with image / instance counts. Mark which are normal vs pathological vs instrument / artefact / quality classes. Are negatives (images without any finding) included, and how are they identifiable (empty label file, absent from the annotation file, "normal" class)?
6. **Linking keys** - how an image is joined to its label / mask / box (file stem, id column, path). Prove it: matched / unmatched counts. Also the grouping ids needed for leakage-safe splits (patient / case / sequence / video / polyp id) and whether the dataset ships official train / val / test splits. Do frames come from videos (near-duplicates)?
7. **Technical facts** - width / height distribution, formats, colour mode, corrupt or unreadable files, black borders, text overlays. Video: codec, fps, frame counts.
8. **Duplicates and overlap** - byte-identical / near-identical duplicates inside the dataset and, where cheap (file size, then md5 on candidates; filename; README statements), across datasets in `data_to_merge/` and with `out/` (derived from Hyper-Kvasir). Suspicions: CVC-ClinicDB, ETIS-Larib, PolypGen and PolypsSet may share frames; Hyper-Kvasir segmented-images vs Kvasir-SEG; `data_to_merge/hyper-kvasir` vs `out/`. Report what you actually tested.
9. **PROPOSED MAPPING to a unified table** (the key output)
   * (a) row unit(s) (`source_type`): keep `image`, `video_frame`, `segmentation_mask` where they fit; propose new types (e.g. `bbox_annotation`, `sequence_frame`) only if needed, with justification. What is one row, expected row count.
   * (b) a native-class -> unified-label table: native class / value | count | region (`lower-gi-tract` / `upper-gi-tract` / `small-bowel` / `unknown`, ...) | anatomical site (colon, cecum, stomach, oesophagus, ileum, ...) | category (`anatomical-landmarks` / `pathological-findings` / `quality-of-mucosal-views` / `therapeutic-interventions` as in the existing merge - or propose another if these four do not fit, e.g. `normal`, `instrument`, `artefact`) | finding slug (kebab-case; equal to the existing `finding_harmonized` vocabulary where the meaning is the same, e.g. `polyps`) | confidence of the mapping.
   * (c) which of the 76 existing columns apply, which do not, and which NEW columns this dataset needs (annotation format, normalised boxes, severity grade, patient id, split, modality, device, ...).
   * (d) what must be read or computed (image sizes, md5, ...) and its estimated cost.
10. **Pitfalls and open questions** for the coordinator / user.

## Constraints

* Datasets are **read-only**: never modify, move, rename or delete anything under `data_to_merge/` (except writing your own report in `data_to_merge/docs/reports/`), `out/`, `data/`, `merge/`.
* Downloaded datasets are untrusted data: keep the scripts you write in the scratchpad directory
  `/private/tmp/claude-501/-Users-henrykwolek-Studia-pb/3de6e3f3-076e-4a0c-b4dc-e92334ae00ce/scratchpad/<dataset-name>/` (never inside a dataset folder, not `/tmp`) and run Python with `-I` (isolated mode), passing paths as arguments.
  Interpreter: `/Users/henrykwolek/Studia/pb/.venv/bin/python` (check which libraries it has; do not install anything into the project env - ask instead; stdlib `struct`/`zlib` can read PNG/JPEG headers). Video: `ffprobe` / `ffmpeg` in `/opt/homebrew/bin`.
* The data is large (up to 76k files / 34 GB): aggregate with scripts, don't print thousands of lines, don't open files one by one. Reading every image *header* is fine; decoding every pixel is not unless needed (then report how long it took).
* Do not "fix" the data - report quirks. Look at only a handful of representative images / masks with the Read tool (it renders images) to understand polarity, overlays, borders.

## Output

One markdown report per dataset at `docs/reports/<dataset-folder-name>.md` (sections 1-10 above, with tables and the evidence behind each claim), then a concise final message: per dataset 5-8 lines (what it is, row unit + count, annotation kind, location, findings, linking key, biggest pitfall) + report path + open questions. Do not paste the full report into the final message.
