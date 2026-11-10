"""Kvasir-Capsule adapter (video capsule endoscopy, 47,238 labelled frames in 14 class folders).

Layout: `kvasir-capsule/<class folder>/<video id 16 hex>_<frame number>.jpg`; the class is the folder name, nothing else ships
(no CSV / JSON / README / boxes / splits). 9 frames are stored byte-identical in two class folders (multi-label frames: 8x Erosion+Pylorus,
1x Ampulla of vater+Pylorus) -> ONE row each (47,229 rows) with `finding` = primary label and `finding_2` = the other.

Rules decided for this dataset (details: docs/datasets/kvasir-capsule.md):
* primary label of a double-labelled frame = pathological > quality > normal > landmark, then alphabetical folder name;
* region / site / location_source of such a row come from the first label that has an authoritative region (the landmark label);
* `region` of the 11 non-landmark classes is `unknown`; the heuristic zone is `region_derived`, from the order of Pylorus / Ileocecal-valve
  frames inside the same video (6 values, see schema.REGION_DERIVED);
* group = the source video (exact at video level; patients across videos are unknown).
"""
from __future__ import annotations

import re
from collections import defaultdict

from .. import common as c

META = dict(
    dataset="kvasir-capsule",
    folder="kvasir-capsule",
    license="unknown",                    # no licence file in the folder (published as CC BY 4.0 per memory - unverified)
    procedure="capsule-whole-gi",         # swallowed capsule: oesophagus -> stomach -> small bowel -> colon
    imaging="white-light",
    region="unknown",                     # default; the vocabulary sets region / site for the 3 landmark classes
    site="unknown",
    location_source="unknown",
    citation="Smedsrud et al., Kvasir-Capsule, a video capsule endoscopy dataset, Scientific Data 8, 142 (2021)",
    expected={"image": 47229},
)

FILE_RE = re.compile(r"^([0-9a-f]{16})_(\d+)\.jpg$")
LANDMARKS = {"Pylorus", "Ileocecal valve", "Ampulla of vater"}
CATEGORY_RANK = {"pathological-findings": 0, "quality-of-mucosal-views": 1, "therapeutic-interventions": 2, "normal": 3, "artefact": 4,
                 "background": 5, "anatomical-landmarks": 6}


def _zone(frame: int, py: tuple | None, ic: tuple | None) -> str:
    """Heuristic zone of a NON-landmark frame from the first / last Pylorus and Ileocecal-valve frame of its video."""
    if py and ic:
        if frame < py[0]:
            return "stomach"
        if py[1] < frame < ic[0]:
            return "small-bowel"
        if frame > ic[1]:
            return "colon"
        return "unknown"                      # inside a landmark window (never happens for single-label frames; kept for safety)
    if py:
        return "stomach" if frame < py[0] else "small-bowel-or-colon" if frame > py[1] else "unknown"
    if ic:
        return "stomach-or-small-bowel" if frame < ic[0] else "colon" if frame > ic[1] else "unknown"
    return "unknown"


def build(ctx):
    root = ctx.root
    classes = sorted(p.name for p in root.iterdir() if p.is_dir())
    # ---- 1. collect every file: stem -> [(class folder, path)]
    by_stem: dict[str, list] = defaultdict(list)
    for cls in classes:
        for p in sorted((root / cls).iterdir(), key=lambda q: c.natural_key(q.name)):
            if p.name.startswith("."):
                continue
            if not FILE_RE.match(p.name):
                ctx.warn(f"file {ctx.rel(p)} does not match <16 hex>_<frame>.jpg - skipped")
                continue
            by_stem[p.stem].append((cls, p))
    # ---- 2. landmark windows per video (first / last frame of Pylorus and Ileocecal valve, all copies counted)
    window: dict[str, dict[str, list]] = defaultdict(dict)
    for stem, items in by_stem.items():
        vid, frame = stem.split("_")
        for cls, _ in items:
            if cls in ("Pylorus", "Ileocecal valve"):
                w = window[vid].setdefault(cls, [int(frame), int(frame)])
                w[0], w[1] = min(w[0], int(frame)), max(w[1], int(frame))

    rows = []
    n_double = 0
    order = sorted(by_stem.items(), key=lambda kv: (min(cls for cls, _ in kv[1]), c.natural_key(kv[0])))
    for stem, items in order:
        vid, frame_s = stem.split("_")
        frame = int(frame_s)
        labs = [(cls, p, ctx.label(cls)) for cls, p in items]
        labs.sort(key=lambda t: (CATEGORY_RANK.get(t[2]["category"], 9), t[0]))
        (cls1, path1, lab1) = labs[0]
        fields = dict(lab1)
        fields.update(
            item_id=stem, video_id=vid, frame_index=frame,
            file_path=ctx.rel(path1), image_path=ctx.rel(path1),
            label_source="folder-name", label_level="image", annotation_types="class", annotation_format="folder-name",
            finding_raw=cls1, category_raw=None, dir_finding=cls1,
            group_id=f"{META['dataset']}:{vid}", group_kind="video", group_quality="exact",
        )
        qa, extra = [], {}
        desc_2 = ""
        if len(labs) > 1:
            n_double += 1
            (cls2, path2, lab2) = labs[1]
            fields.update(finding_2=lab2["finding"], finding_2_harmonized=lab2["finding_harmonized"], finding_2_raw=cls2,
                          category_2=lab2["category"], n_labels=2)
            # region / site from the first label that has an authoritative region (normally the landmark label)
            for lab in (lab1, lab2):
                if lab["region"] != "unknown":
                    fields.update(region=lab["region"], site=lab["site"], location_source=lab["location_source"])
                    break
            qa.append("multi-label-duplicate-file")
            extra = {"alt_paths": [ctx.rel(p) for _, p, _ in labs[1:]], "alt_dir_finding": [cls for cls, _, _ in labs[1:]]}
            if lab1["category"] == lab2["category"] == "anatomical-landmarks":
                extra["alt_site"] = lab2["site"]
            desc_2 = f"; second label (same bytes in folder {cls2!r}): {lab2['finding']}"
        else:
            fields["n_labels"] = 1
        if len(labs) > 2:
            raise AssertionError(f"{stem}: stored in {len(labs)} class folders")
        # heuristic zone: only rows without any landmark label
        if not any(cls in LANDMARKS for cls, _, _ in labs):
            w = window.get(vid, {})
            py, ic = w.get("Pylorus"), w.get("Ileocecal valve")
            fields["region_derived"] = _zone(frame, tuple(py) if py else None, tuple(ic) if ic else None)
        # folder provenance: labels ARE the folders -> never a mismatch (native slug vs folder slug)
        fields.update(label_finding_mismatch=c.slugify(cls1) != lab1["finding"], label_category_mismatch=None)
        fields["label_folder_mismatch"] = fields["label_finding_mismatch"]
        if qa:
            fields["qa_flags"] = c.pipe_join(qa)
        if extra:
            fields["extra_json"] = c.compact_json(extra)
        fields["row_description"] = (f"Capsule endoscopy frame {frame} of source video {vid} (kvasir-capsule) — class folder {cls1!r}: "
                                     f"{fields['category']} / {lab1['finding_harmonized']}{desc_2}")
        rows.append(ctx.row("image", **fields))
    ctx.log(f"   {len(rows):,} distinct frames from {len(classes)} class folders ({n_double} double-labelled), {len(window)} videos with landmarks")
    return rows
