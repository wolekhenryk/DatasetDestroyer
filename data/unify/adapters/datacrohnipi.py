"""DataCrohnIPI (CrohnIPI, Univ. Nantes / LS2N): 3,484 small-bowel capsule frames of Crohn's disease, ONE image-level label each.

Layout used:   imgs/NNNNN.jpg (3,498 files, 320x320)  +  CrohnIPI_description.csv (`Frame name,Label,Fold`, 3,484 rows).
Ignored:       the 14 images on disk that have no CSV row (orphans -> ctx.warn, no rows); README.md is only read by humans.
Row unit:      `image` only (no boxes, no masks).
Location:      small bowel, from the README ("images from endoscopic video capsules") and the paper title; segment unknown.
Groups:        no patient / video id exists -> blocks of 200 consecutive file numbers (frames are numbered in capsule-video order:
               neighbouring files share the label in 85 % of pairs, and the agreement falls to chance at ~100 files apart), then blocks that
               contain a near-duplicate pair (24x24 grey thumbnail cosine >= NEARDUP_COS) are merged. group_kind block-proxy / proxy.
Shipped split: `Fold` (1-5) is the CV test-fold of a frame, assigned at random PER FRAME -> neighbouring near-identical frames sit in
               different folds (leak). Rows whose near-duplicate partner is in another fold carry the qa flag split-leak-known.
Facts and decisions: docs/datasets/datacrohnipi.md.
"""
from __future__ import annotations

import re

import numpy as np
from PIL import Image

from .. import common as c

META = dict(
    dataset="datacrohnipi",
    folder="DataCrohnIPI",
    license="CC BY-NC-ND 2.0 (research use only)",
    procedure="capsule-small-bowel",
    imaging="white-light",              # README silent; capsule endoscopy = white LED illumination (inferred, see docs)
    region="small-bowel",
    site="small-bowel",
    location_source="readme",
    citation="Vallee R. et al., CrohnIPI: An endoscopic image database for the evaluation of automatic Crohn's disease lesions recognition algorithms, "
             "Proc. SPIE 11317 (2020); de Maissin A. et al., Endoscopy Int. Open (accepted)",
    expected={"image": 3484},
)

BLOCK = 200            # consecutive file numbers per proxy group
NEARDUP_COS = 0.985    # cosine of 24x24 grey thumbnails: 0.98 would chain 8 of the 18 blocks into one group, 0.985 only a few
THUMB = 24
LEGEND = {"N": "normal", "E": "erythema", "O": "oedema", "AU": "aphthoid ulceration", "U3-10": "ulceration 3-10 mm",
          "U>10": "ulceration over 10 mm", "S": "stenosis"}


def _thumb(path):
    with Image.open(path) as im:
        size = im.size
        return size, np.asarray(im.convert("L").resize((THUMB, THUMB), Image.BILINEAR), dtype=np.float32).ravel()


def build(ctx):
    csv_path = ctx.root / "CrohnIPI_description.csv"
    df = c.read_csv_safe(csv_path)
    assert list(df.columns) == ["Frame name", "Label", "Fold"], list(df.columns)
    imgdir = ctx.root / "imgs"
    on_disk = {p.name for p in imgdir.glob("*.jpg")}
    in_csv = set(df["Frame name"])
    if orphans := sorted(on_disk - in_csv):
        ctx.warn(f"{len(orphans)} images in imgs/ have no row in CrohnIPI_description.csv and are NOT ingested: {', '.join(orphans)}")
    if missing := sorted(in_csv - on_disk):
        ctx.warn(f"{len(missing)} CSV rows without an image file (skipped): {missing[:5]}")
    if df["Frame name"].duplicated().any():
        raise ValueError("duplicate Frame name in CrohnIPI_description.csv")

    recs = []
    for r in sorted(df.to_dict("records"), key=lambda r: c.natural_key(r["Frame name"])):
        name = r["Frame name"]
        if name not in on_disk:
            continue
        m = re.fullmatch(r"(\d{5})\.jpg", name)
        if not m or r["Fold"] not in {"1", "2", "3", "4", "5"}:
            raise ValueError(f"unexpected frame name / fold: {r}")
        recs.append({"name": name, "num": int(m.group(1)), "code": r["Label"], "fold": int(r["Fold"])})

    # ---- near-duplicate frames (cheap thumbnail comparison) -> merged groups + cross-fold leak flag
    thumbs, sizes = [], []
    for rec in recs:
        size, t = _thumb(imgdir / rec["name"])
        sizes.append(size)
        thumbs.append(t)
    T = np.stack(thumbs)
    T = T - T.mean(axis=1, keepdims=True)
    T = T / (np.linalg.norm(T, axis=1, keepdims=True) + 1e-6)
    sim = T @ T.T
    pairs = np.argwhere(np.triu(sim >= NEARDUP_COS, 1))
    n_blocks = (max(r["num"] for r in recs) - 1) // BLOCK + 1
    parent = list(range(n_blocks + 1))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    leak = set()
    for i, j in pairs.tolist():
        a, b = recs[i], recs[j]
        ra, rb = find((a["num"] - 1) // BLOCK + 1), find((b["num"] - 1) // BLOCK + 1)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)            # root = lowest block number
        if a["fold"] != b["fold"]:
            leak.update((a["name"], b["name"]))
    ctx.log(f"   {len(pairs)} near-duplicate pairs (cos >= {NEARDUP_COS}), {len(leak)} frames with a partner in another fold")

    rows = []
    for rec, (w, h) in zip(recs, sizes):
        lab = ctx.label(rec["code"])
        stem = rec["name"][:-4]
        block = find((rec["num"] - 1) // BLOCK + 1)
        rows.append(ctx.row(
            "image",
            item_id=stem,
            source_subset="imgs",
            file_path=ctx.rel(imgdir / rec["name"]),
            label_source=ctx.rel(csv_path),
            label_level="image",
            row_description=(f"CrohnIPI small-bowel capsule frame {stem} ({w}x{h}) of a Crohn's disease exam, expert label {rec['code']} "
                             f"({LEGEND[rec['code']]}), official CV test fold {rec['fold']}"),
            annotation_types="class",
            annotation_format="csv",
            finding_raw=rec["code"],                       # the native code (E, O, AU, U3-10, U>10, S, N); `finding` is the expanded vocabulary slug
            width=w, height=h,
            group_id=f"{META['dataset']}:b{BLOCK}-{block:03d}", group_kind="block-proxy", group_quality="proxy",
            split_official=f"fold-{rec['fold']}",
            qa_flags="split-leak-known" if rec["name"] in leak else None,
            extra_json=c.compact_json({"disease_context": "crohns-disease"}),
            **lab,
        ))
    return rows
