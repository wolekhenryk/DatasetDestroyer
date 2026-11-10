"""Single source of truth for the unified label table: column list, dtypes, controlled vocabularies.

Everything else (validation, docs/SCHEMA.md, the final CSV column order) is derived from SCHEMA_SPEC.
To add a column: add ONE line to SCHEMA_SPEC (name, dtype, group, description). Nothing else has to change;
adapters may simply start filling it and every other dataset leaves it empty.
"""
from __future__ import annotations

import pandas as pd

# --------------------------------------------------------------------------------------
# controlled vocabularies (validated in unify/validate.py)
# --------------------------------------------------------------------------------------
SOURCE_TYPES = ["image", "video_frame", "segmentation_mask"]
LABEL_LEVELS = ["image", "clip", "mask"]
REGIONS = ["lower-gi-tract", "upper-gi-tract", "small-bowel", "unknown"]
CATEGORIES = [
    # the four of the Hyper-Kvasir merge
    "anatomical-landmarks", "pathological-findings", "quality-of-mucosal-views", "therapeutic-interventions",
    # new
    "normal",        # explicit normal class (normal-mucosa)
    "background",    # frame without an annotation of the target class (no-polyp-annotated, no-lesion-annotated)
    "artefact",      # image artefacts / instrument / blood in view (EAD2020)
]
NEGATIVE_CATEGORIES = ["normal", "background"]
PROCEDURES = ["colonoscopy", "gastroscopy", "capsule-small-bowel", "capsule-whole-gi", "mixed", "unknown"]
IMAGING = ["white-light", "nbi", "chromoscopy", "mixed", "unknown"]
LOCATION_SOURCES = ["dataset-constant", "folder", "label-column", "class-name", "readme", "unknown"]
ANNOTATION_TYPES = ["class", "clip-class", "bbox", "mask"]
BBOX_SOURCES = ["annotator", "mask-derived"]
GROUP_KINDS = ["video", "sequence", "case", "centre", "block-proxy", "dataset", "none"]
GROUP_QUALITIES = ["exact", "proxy", "coarse", "none"]
LABEL_CONFIDENCE = ["high", "medium", "low"]
# heuristic zone of a capsule frame from the order of landmark frames inside its video (Kvasir-Capsule); the two "-or-" values
# mean only one of the two landmarks exists in the video, so one side of the zone boundary is unknown
REGION_DERIVED = ["stomach", "small-bowel", "colon", "stomach-or-small-bowel", "small-bowel-or-colon", "unknown"]
FINDING_HARMONIZATION = ["native", "identity", "mapped", "derived"]
# free but documented flags for `qa_flags` (validation only warns on unknown flags)
QA_FLAGS = [
    # only flags that were established PER ROW (dataset-wide facts such as burned-in text live in docs/datasets/<dataset>.md)
    "annotation-missing",          # label says positive but the geometry (mask / box) is absent
    "dup-label-conflict",          # byte-identical image whose class set (`findings_all`) differs between the copies
    "dup-box-conflict",            # byte-identical image, same classes, but different box counts or union boxes with IoU < 0.5
    "split-leak-known",            # row is part of a documented leak between the shipped splits
    "duplicate-video",             # frame of a video that exists twice in the dataset (merged into one group)
    "label-folder-mismatch",       # CSV label and folder disagree (Hyper-Kvasir)
    "frames-suspect",              # video with unreliable header values
    "multi-label-duplicate-file",  # same bytes stored in two class folders (Kvasir-Capsule)
]

# --------------------------------------------------------------------------------------
# the schema: (name, dtype, group, description)
# --------------------------------------------------------------------------------------
_S, _I, _F, _B = "string", "Int64", "Float64", "boolean"

SCHEMA_SPEC: list[tuple[str, str, str, str]] = [
    # ---------------- identity
    ("sample_id", _S, "identity", "Globally unique, stable, human-readable key: `image:<dataset>:<item_id>`, `mask:<dataset>:<item_id>`, `frame:<dataset>:<video_id>:<frame_index:06d>`."),
    ("source_type", _S, "identity", "Exactly one of `image`, `video_frame`, `segmentation_mask`. Never null."),
    ("dataset", _S, "identity", "Registry name of the dataset (= adapter name), e.g. `hyper-kvasir`, `cvc-clinicdb`. Never null."),
    ("source_subset", _S, "identity", "Origin partition inside the dataset (`labeled-images`, `videos80`, `nbi_adenoma`, `bbox_images`...). NOT the shipped split (that is `split_official`). Nullable."),
    ("item_id", _S, "identity", "Id of the underlying item, unique within (dataset, source_type): uuid, file stem, or the file path below the dataset folder without extension when stems repeat (PolypsSet)."),
    ("label_source", _S, "identity", "File(s) (relative to `data_to_merge/`) or rule (`folder-name`) the labels were read from."),
    ("label_level", _S, "identity", "`image` (label of one still), `clip` (frame inherits its video's label), `mask` (mask row, labels inherited from the linked image)."),
    ("row_description", _S, "identity", "Verbose human-readable sentence describing the row (self-explanatory when exported alone)."),
    ("license", _S, "identity", "Licence / usage terms of the dataset (from the adapter META); `unknown` if none is shipped."),
    # ---------------- WHAT is annotated
    ("annotation_types", _S, "what", "`|`-separated subset of `class`, `clip-class`, `bbox`, `mask`: the annotation kinds the dataset PROVIDES for this row. `bbox`/`mask` are listed also when the annotator drew nothing (then `n_boxes` = 0 / `has_mask` False = annotated-empty); a missing geometry (positive frame without mask) is NOT listed and `n_boxes` is null."),
    ("annotation_format", _S, "what", "Source encoding of the annotation: `folder-name`, `csv`, `yolo-txt`, `voc-xml`, `supervisely-bitmap-json`, `mask-png`, `mask-jpeg`, `mask-multipage-tif`..."),
    # ---------------- WHERE
    ("region", _S, "where", "`lower-gi-tract` | `upper-gi-tract` | `small-bowel` | `unknown`. Authoritative only - never guessed (heuristics go to `region_derived`)."),
    ("organ_raw", _S, "where", "Original organ text if the dataset has one (`Lower GI`), else null."),
    ("site", _S, "where", "Finer anatomical site: colon, cecum, rectum, terminal-ileum, ileocecal-valve, stomach, pylorus, oesophagus, z-line, duodenum, small-bowel, unknown..."),
    ("location_source", _S, "where", "How region/site is known: dataset-constant, folder, label-column, class-name, readme, unknown."),
    ("region_derived", _S, "where", "Optional heuristic zone (Kvasir-Capsule only): stomach | small-bowel | colon | stomach-or-small-bowel | small-bowel-or-colon | unknown, from the order of pylorus / ileocecal-valve frames inside the video. Nullable; never used for `region`."),
    ("procedure", _S, "where", "colonoscopy | gastroscopy | capsule-small-bowel | capsule-whole-gi | mixed | unknown."),
    ("imaging", _S, "where", "white-light | nbi | chromoscopy | mixed | unknown. Use `unknown` for a single frame of an unrecorded type rather than `mixed`."),
    ("device", _S, "where", "Endoscope / capsule model if the dataset says so (`PillCam SB3`, `Olympus EC-S10`), else null."),
    # ---------------- WHAT finding
    ("category", _S, "finding", "anatomical-landmarks, pathological-findings, quality-of-mucosal-views, therapeutic-interventions, normal, background, artefact. Never null."),
    ("category_raw", _S, "finding", "Original category / classification text if the dataset has one."),
    ("finding", _S, "finding", "Kebab-case slug of the original finding text (for multi-class rows: the primary class = most boxes, ties by lowest class id)."),
    ("finding_raw", _S, "finding", "Original finding text, whitespace-stripped (native class name)."),
    ("finding_harmonized", _S, "finding", "Canonical lesion-type slug to train/evaluate on across sources; equals `finding` unless an explicit vocabulary rewrite applies."),
    ("finding_parent", _S, "finding", "Coarse pooling key (`ulcerative-colitis` for the graded UC classes, `polyps` for `polyp-like-lesion`...). Defaults to `finding_harmonized`."),
    ("finding_subtype", _S, "finding", "Histology / grade / size class of the finding (`adenomatous`, `grade-2-3`, `la-a`, `3-10mm`, `gt-10mm`). Nullable."),
    ("finding_harmonization", _S, "finding", "`native` (label already canonical), `identity` (slug used as is), `mapped` (rewritten by an explicit rule), `derived` (label synthesised by the adapter, e.g. `no-polyp-annotated` for a frame without box)."),
    ("finding_in_image_vocab", _B, "finding", "`video_frame` rows only (null elsewhere): True if (region, category, finding_harmonized) of the clip also occurs among the `image` rows of the table, i.e. a still-image class with this meaning exists."),
    ("findings_all", _S, "finding", "`|`-separated sorted distinct `finding_harmonized` of ALL labels of the row (multi-label images, 2nd video label). Equals `finding_harmonized` for single-label rows."),
    ("class_counts_json", _S, "finding", "Detection datasets: compact JSON `{finding_harmonized: n_boxes}` for the row, else null."),
    ("finding_2", _S, "finding", "Slug of the second label slot (second video label / second folder of a double-labelled frame). Nullable."),
    ("finding_2_harmonized", _S, "finding", "`finding_2` after the explicit vocabulary map."),
    ("finding_2_raw", _S, "finding", "Original second finding text, stripped."),
    ("category_2", _S, "finding", "Slug of the second classification."),
    ("category_2_raw", _S, "finding", "Original second classification text, stripped."),
    ("n_labels", _I, "finding", "Number of label slots filled: 1; 2 when a second label slot (`finding_2` and/or `category_2`) is filled. For multi-class detection rows: the number of distinct classes (`len(findings_all)`). Never counts boxes or instances."),
    ("description", _S, "finding", "Free-text description of the finding (Hyper-Kvasir videos). Commas occur inside values - never split."),
    ("bbps_score", _I, "finding", "Boston Bowel Preparation Scale score 0-3 parsed from the description (Hyper-Kvasir BBPS video frames only)."),
    ("bbps_range", _S, "finding", "`0-1` or `2-3` for BBPS rows."),
    ("label_confidence", _S, "finding", "high | medium | low: confidence of the native class -> unified label mapping (from the vocabulary CSV)."),
    ("is_negative", _B, "finding", "Pathology polarity: True for `normal` / `background` (no pathology annotated), False for `pathological-findings`, null for classes that are not about pathology (landmarks, mucosal-view quality, therapeutic interventions, artefacts)."),
    # ---------------- folder provenance
    ("dir_region", _S, "folder", "Region folder the source file really sits in (Hyper-Kvasir)."),
    ("dir_category", _S, "folder", "Category folder as on disk (Hyper-Kvasir)."),
    ("dir_finding", _S, "folder", "Finding / class folder as on disk (Hyper-Kvasir, Kvasir-Capsule)."),
    ("label_category_mismatch", _B, "folder", "CSV category differs from the on-disk category folder."),
    ("label_finding_mismatch", _B, "folder", "`finding_harmonized` differs from the lower-cased on-disk finding folder."),
    ("label_folder_mismatch", _B, "folder", "Any of region/category/finding disagrees between CSV label and folder."),
    # ---------------- files & links
    ("file_path", _S, "files", "POSIX path relative to `data_to_merge/` of the asset the row is about (image, mask, or the .avi of a frame row). Never null."),
    ("file_ext", _S, "files", "Lower-case extension without dot (`jpg`, `png`, `avi`, `tif`)."),
    ("file_exists", _B, "files", "`file_path` verified as an existing file. Never null."),
    ("file_size_bytes", _I, "files", "Size of `file_path` in bytes."),
    ("image_path", _S, "files", "Path of the image (image + mask rows). For image rows equals `file_path`."),
    ("segmented_image_path", _S, "files", "Hyper-Kvasir: path of the renamed byte-identical copy in `segmented-images/images/`."),
    ("mask_path", _S, "files", "Path of the mask file (images with a standalone mask file + mask rows)."),
    ("annotation_path", _S, "files", "Per-item annotation file (xml / json / txt) when the labels are not in a table or folder name."),
    ("image_md5", _S, "files", "MD5 of the image bytes (all image rows; cached). Basis for `dup_group_id` and the Hyper-Kvasir segmentation link."),
    ("video_id", _S, "files", "Id of the source video / sequence / case when the dataset gives one (Hyper-Kvasir clips; frame images of Kvasir-Capsule, PolypsSet cases, EAD sequences)."),
    ("frame_index", _I, "files", "Video frame rows: 0-based frame number inside the .avi (frames are addressed, not extracted). Extracted-frame images: the source-defined frame number where the dataset gives one."),
    ("timestamp_s", _F, "files", "frame_index / fps_effective in seconds (video_frame rows only)."),
    ("seg_stem", _S, "files", "Name stem of the segmentation entry (Hyper-Kvasir `cju...`; other datasets: the mask stem)."),
    ("parent_image_sample_id", _S, "files", "Mask rows: sample_id of the linked image row."),
    ("mask_sample_id", _S, "files", "Image rows with a standalone mask file: sample_id of the linked mask row."),
    # ---------------- split safety & QA
    ("centre", _S, "split", "Acquisition centre / hospital code if the dataset records it (PolypGen `C1`..`C6`), else null. Enables leave-one-centre-out."),
    ("group_id", _S, "split", "Leakage-safe grouping key `<dataset>:<group>`; split by it, never by row. Videos known to be duplicated are merged into one group. Null if no grouping exists."),
    ("group_kind", _S, "split", "video | sequence | case | centre | block-proxy | dataset (the whole dataset is one group, e.g. ETIS) | none."),
    ("group_quality", _S, "split", "exact (all frames of one video / sequence / case share the id) | proxy (heuristic blocks, may still leak) | coarse (group = whole dataset: safe but cannot be split further) | none (no id: rows cannot be split leak-safely - hold out whole datasets or accept leakage). Never patient-level unless stated in docs/datasets/<dataset>.md."),
    ("split_official", _S, "split", "Split shipped with the dataset (`train`, `val`, `test`, `fold-1`..`fold-5`), else null."),
    ("dup_group_id", _S, "split", "`dup:<md5 prefix>` for image rows sharing identical bytes (whole table); null if unique."),
    ("qa_flags", _S, "split", "`|`-separated flags: annotation-missing, dup-label-conflict, split-leak-known, burned-in-text, non-gi-possible, label-folder-mismatch, frames-suspect, ..."),
    ("extra_json", _S, "split", "Compact JSON with dataset-specific extras (documented per dataset in docs/datasets/<dataset>.md)."),
    # ---------------- pixel size / video
    ("width", _I, "pixel", "Pixel width of the addressed asset (image, mask or video frame). Never null."),
    ("height", _I, "pixel", "Pixel height of the addressed asset. Never null."),
    ("n_frames_total", _I, "pixel", "Frames in the video (video_frame rows)."),
    ("fps", _F, "pixel", "Frame rate as stored in the video metadata."),
    ("fps_effective", _F, "pixel", "Frame rate used for `timestamp_s`."),
    ("duration_s", _F, "pixel", "Clip duration in seconds from the video metadata."),
    ("codec", _S, "pixel", "Video codec."),
    ("frames_suspect", _B, "pixel", "True for videos whose frame count disagrees with duration*fps by more than 2 frames."),
    ("timestamp_note", _S, "pixel", "Why a suspect clip's frame count / duration / timestamps need care."),
    ("frame_rank", _I, "pixel", "0-based rank of the frame among the sampled frames of its video."),
    ("frames_sampled_in_video", _I, "pixel", "How many frames of this video are present as rows."),
    ("frame_selection", _S, "pixel", "Sampling rule, e.g. `even-segment-midpoints k=20`."),
    # ---------------- boxes & masks
    ("has_mask", _B, "mask", "A segmentation mask exists for this row's image (standalone file or embedded). Never null."),
    ("has_bbox", _B, "mask", "At least one bounding box exists (annotated or derived). Never null."),
    ("n_boxes", _I, "mask", "Number of boxes (0 for annotated negatives, null when the dataset has no box/mask annotation)."),
    ("bboxes_json", _S, "mask", "Compact JSON list `[{\"label\",\"finding\",\"xmin\",\"ymin\",\"xmax\",\"ymax\"},...]`: pixels, top-left origin, corner format, xmax/ymax INCLUSIVE."),
    ("bbox_label", _S, "mask", "Distinct box labels, `|`-separated (Hyper-Kvasir/CVC/ETIS: `polyp`)."),
    ("bbox_xmin", _I, "mask", "Union of all boxes (a convenience; for multi-class rows use `bboxes_json`): min xmin."),
    ("bbox_ymin", _I, "mask", "Union of all boxes: min ymin."),
    ("bbox_xmax", _I, "mask", "Union of all boxes: max xmax (inclusive)."),
    ("bbox_ymax", _I, "mask", "Union of all boxes: max ymax (inclusive)."),
    ("bbox_source", _S, "mask", "annotator (drawn by the dataset authors; the source encoding is in `annotation_format`) | mask-derived (computed from the mask: 8-connected components)."),
    ("mask_format", _S, "mask", "File / storage format of the mask (`jpeg-rgb`, `png-gray`, `png-rgb`, `tif-multipage-class-pages`, `supervisely-bitmap-in-json`)."),
    ("mask_encoding", _S, "mask", "How to binarise the mask, e.g. `gray>127 white=polyp`, `value==1`, `tif-page>127 (last row ignored)`."),
    ("mask_foreground_pixels", _I, "mask", "Foreground pixels after binarisation (and noise removal)."),
    ("mask_foreground_fraction", _F, "mask", "mask_foreground_pixels / (width*height), 6 decimals."),
    ("mask_tight_xmin", _I, "mask", "Tight bounding box of the mask foreground, min column."),
    ("mask_tight_ymin", _I, "mask", "Tight bounding box of the mask foreground, min row."),
    ("mask_tight_xmax", _I, "mask", "Tight bounding box, max column (inclusive)."),
    ("mask_tight_ymax", _I, "mask", "Tight bounding box, max row (inclusive)."),
    ("mask_in_bbox_fraction", _F, "mask", "QA: share of mask foreground lying inside the annotated boxes (xmax/ymax inclusive). EAD2020: each mask page is paired with the boxes of its own class."),
    ("mask_json_bbox_max_diff_px", _I, "mask", "QA: largest coordinate difference between the tight mask box and the union of the annotated boxes."),
    ("mask_noise_pixels_removed", _I, "mask", "Foreground pixels dropped as noise before the mask statistics (Hyper-Kvasir: the isolated JPEG pixel at (0,0) = 1; CVC-ClinicDB: components < 10 px; EAD2020: the sentinel last row of 255s; clean masks: 0)."),
    ("annotation_source", _S, "mask", "Where the mask / box annotations come from (file or rule)."),
]

COLUMNS: list[str] = [c[0] for c in SCHEMA_SPEC]
DTYPES: dict[str, str] = {c[0]: c[1] for c in SCHEMA_SPEC}
GROUPS: dict[str, str] = {c[0]: c[2] for c in SCHEMA_SPEC}
DESCRIPTIONS: dict[str, str] = {c[0]: c[3] for c in SCHEMA_SPEC}

assert len(COLUMNS) == len(set(COLUMNS)), "duplicate column in SCHEMA_SPEC"

# columns that must be non-null on EVERY row (checked in validate.py)
REQUIRED_NON_NULL = [
    "group_kind", "group_quality",
    "sample_id", "source_type", "dataset", "item_id", "label_source", "label_level", "row_description", "license",
    "annotation_types", "annotation_format", "region", "site", "location_source", "procedure", "imaging",
    "category", "finding", "finding_raw", "finding_harmonized", "finding_parent", "finding_harmonization",
    "findings_all", "n_labels", "label_confidence",
    "file_path", "file_ext", "file_exists", "file_size_bytes", "width", "height", "has_mask", "has_bbox",
]

# columns that must be null outside video_frame rows (Kvasir-Capsule image rows may carry video_id/frame_index)
VIDEO_ONLY = ["timestamp_s", "n_frames_total", "fps", "fps_effective", "duration_s", "codec", "frames_suspect",
              "timestamp_note", "frame_rank", "frames_sampled_in_video", "frame_selection"]

GROUP_TITLES = {
    "identity": "identity", "what": "WHAT is annotated", "where": "WHERE (anatomy / procedure)",
    "finding": "WHAT finding", "folder": "folder provenance", "files": "files and links",
    "split": "split safety and QA", "pixel": "pixel size / video", "mask": "boxes and masks",
}


def empty_frame(n: int = 0) -> pd.DataFrame:
    """Frame with all schema columns, nullable dtypes, `n` empty rows."""
    return pd.DataFrame({c: pd.array([pd.NA] * n, dtype=DTYPES[c]) for c in COLUMNS})


def coerce(df: pd.DataFrame) -> pd.DataFrame:
    """Add missing columns, drop nothing unknown silently (raises), order columns, cast to the schema dtypes."""
    unknown = [c for c in df.columns if c not in DTYPES]
    if unknown:
        raise ValueError(f"adapter produced columns that are not in SCHEMA_SPEC: {unknown}")
    out = {}
    for c in COLUMNS:
        if c in df.columns:
            s = df[c]
            if DTYPES[c] == "boolean":
                out[c] = s.astype("boolean")
            elif DTYPES[c] in ("Int64",):
                out[c] = pd.to_numeric(s, errors="raise").astype("Int64")
            elif DTYPES[c] == "Float64":
                out[c] = pd.to_numeric(s, errors="raise").astype("Float64")
            else:
                out[c] = s.astype("string")
        else:
            out[c] = pd.array([pd.NA] * len(df), dtype=DTYPES[c])
    res = pd.DataFrame(out, index=df.index)
    return res[COLUMNS]


def schema_markdown() -> str:
    """Markdown column dictionary (used for docs/SCHEMA.md)."""
    lines = []
    n = 0
    for g, title in GROUP_TITLES.items():
        rows = [c for c in SCHEMA_SPEC if c[2] == g]
        lines.append(f"#### {title}\n")
        lines.append("| # | column | dtype | description |")
        lines.append("|--:|---|---|---|")
        for name, dtype, _, desc in rows:
            n += 1
            lines.append(f"| {n} | `{name}` | {dtype} | {desc} |")
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    print(schema_markdown())
