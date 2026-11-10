"""Independent spot-check + overlay montage for the three polyp adapters (polypsset, polypgen-ninja, cvc-clinicdb).

    cd data_to_merge
    ../.venv/bin/python unify/tools/polyp_adapters_check.py <table.csv> <montage-dir> [--n 8] [--seed 0]

For N random rows of every row type of every one of the three datasets present in the table the script re-derives the facts from the RAW files
with code that does NOT use unify.common / the adapters (regex on the XML text, own base64/zlib/PNG decoding, own thresholding) and compares:
size, md5 (image rows), boxes, class, mask pixel counts, group. It also writes one overlay montage per dataset (boxes in red, masks in green)
to <montage-dir>/<dataset>-overlay.png for a visual check. Exit code 1 on any mismatch. Read-only for the dataset folders.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import random
import re
import sys
import zlib
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]          # data_to_merge/


def _md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def _bad(msgs: list[str], cond: bool, text: str):
    if not cond:
        msgs.append(text)


# ---------------------------------------------------------------- PolypsSet
def check_polypsset(r: pd.Series, msgs: list[str]):
    xml = (ROOT / r.annotation_path).read_text(encoding="utf-8")
    objs = re.findall(r"<object>(.*?)</object>", xml, re.S)
    W, H = (int(re.search(rf"<{t}>\s*(\d+)\s*</{t}>", xml).group(1)) for t in ("width", "height"))
    with Image.open(ROOT / r.file_path) as im:
        _bad(msgs, im.size == (W, H) == (int(r.width), int(r.height)), f"{r.sample_id}: size")
    _bad(msgs, _md5(ROOT / r.file_path) == r.image_md5, f"{r.sample_id}: md5")
    _bad(msgs, len(objs) == int(r.n_boxes), f"{r.sample_id}: n_boxes {r.n_boxes} vs {len(objs)} objects")
    path = re.search(r"<path>(.*?)</path>", xml, re.S).group(1)
    fn = re.search(r"<filename>(.*?)</filename>", xml).group(1)
    pre = re.search(r"80_Videos_Frames/(pretest|posttest)/(\d+)/(\d+)\.jpg", path)
    cv = re.search(r"CVC-300/(\d+)/(\d+)\.bmp", path)
    nb = re.search(r"NBI-Frames/adenoma_(\d+)$", path)
    if pre:
        exp = (f"videos80-{pre[1]}-{int(pre[2])}", int(pre[3]), "videos80")
    elif cv:
        exp = (f"cvc300-{int(cv[1])}", int(cv[2]), "cvc300")
    elif nb:
        exp = (f"nbi_adenoma-{int(nb[1])}", int(re.match(r"adenoma_(\d+)", fn)[1]), "nbi_adenoma")
    else:
        exp = (r.video_id, int(r.frame_index), r.source_subset)       # other sub-sets: only internal consistency is checked
    _bad(msgs, (r.video_id, int(r.frame_index), r.source_subset) == exp, f"{r.sample_id}: origin {(r.video_id, r.frame_index, r.source_subset)} vs {exp}")
    _bad(msgs, r.video_id in r.group_id.split(":", 1)[1].split("+"), f"{r.sample_id}: group {r.group_id} does not contain video {r.video_id}")
    _bad(msgs, "krushipatel" not in json.dumps(r.to_dict(), default=str) and "mfathan" not in json.dumps(r.to_dict(), default=str), f"{r.sample_id}: user name leaked")
    boxes = json.loads(r.bboxes_json) if isinstance(r.bboxes_json, str) else []
    for (o, b) in zip(objs, boxes):
        name = re.search(r"<name>(.*?)</name>", o).group(1).strip()
        x0, y0, x1, y1 = (int(re.search(rf"<{t}>\s*(\d+)\s*</{t}>", o).group(1)) for t in ("xmin", "ymin", "xmax", "ymax"))
        _bad(msgs, (b["xmin"], b["ymin"], b["xmax"], b["ymax"]) == (x0, y0, min(x1 - 1, W - 1), min(y1 - 1, H - 1)), f"{r.sample_id}: box {b} vs xml {(x0, y0, x1, y1)}")
        _bad(msgs, name == r.finding_subtype and r.finding_harmonized == "polyps", f"{r.sample_id}: class {name} vs {r.finding_subtype}")
    if not objs:
        _bad(msgs, r.category == "background" and r.finding_harmonization == "derived", f"{r.sample_id}: negative labelling")


# ---------------------------------------------------------------- PolypGen
def _decode(b: dict) -> np.ndarray:
    return np.asarray(Image.open(io.BytesIO(zlib.decompress(base64.b64decode(b["data"]))))) != 0


def check_polypgen(r: pd.Series, msgs: list[str]):
    j = json.loads((ROOT / r.annotation_path).read_text(encoding="utf-8"))
    tags = {t["name"]: t["value"] for t in j["tags"]}
    with Image.open(ROOT / r.image_path) as im:
        _bad(msgs, im.size == (int(r.width), int(r.height)) == (j["size"]["width"], j["size"]["height"]), f"{r.sample_id}: size")
    if r.source_type == "image":
        _bad(msgs, _md5(ROOT / r.file_path) == r.image_md5, f"{r.sample_id}: md5")
    _bad(msgs, r.centre == tags.get("institute", "") or (pd.isna(r.centre) and "institute" not in tags), f"{r.sample_id}: centre")
    objs = j["objects"]
    if "negative" in tags:
        _bad(msgs, r.category == "background" and int(r.n_boxes) == 0 and not objs, f"{r.sample_id}: negative row")
        return
    if not objs:
        _bad(msgs, pd.isna(r.n_boxes) and r.qa_flags == "annotation-missing" and not r.has_mask, f"{r.sample_id}: positive without object")
        return
    areas, exp_boxes = [], []
    for o in objs:
        ox, oy = o["bitmap"]["origin"]
        png = Image.open(io.BytesIO(zlib.decompress(base64.b64decode(o["bitmap"]["data"]))))
        exp_boxes.append((ox, oy, ox + png.size[0] - 1, oy + png.size[1] - 1))          # tight crop: PNG size, not foreground extent
        areas.append(int(_decode(o["bitmap"]).sum()))
    got = [(b["xmin"], b["ymin"], b["xmax"], b["ymax"]) for b in json.loads(r.bboxes_json)]
    _bad(msgs, got == exp_boxes, f"{r.sample_id}: boxes {got} vs bitmap extents {exp_boxes}")
    _bad(msgs, int(r.mask_foreground_pixels) == sum(areas), f"{r.sample_id}: mask px {r.mask_foreground_pixels} vs {sum(areas)}")
    _bad(msgs, int(r.n_boxes) == len(objs) and bool(r.has_mask), f"{r.sample_id}: n_boxes / has_mask")
    seq = tags.get("sequence")
    _bad(msgs, (r.group_id == f"polypgen-ninja:{seq}") if seq else r.group_id.startswith("polypgen-ninja:"), f"{r.sample_id}: group {r.group_id}")
    if r.source_type == "segmentation_mask":
        _bad(msgs, r.file_path == r.annotation_path and r.mask_format == "supervisely-bitmap-in-json", f"{r.sample_id}: mask row paths")


# ---------------------------------------------------------------- CVC-ClinicDB
def check_cvc(r: pd.Series, msgs: list[str]):
    fid = int(r.item_id)
    gray = np.asarray(Image.open(ROOT / "CVC-ClinicDB/PNG/Ground Truth" / f"{fid}.png").convert("L"))
    raw_fg = int((gray > 127).sum())
    _bad(msgs, int(r.mask_foreground_pixels) + int(r.mask_noise_pixels_removed) == raw_fg, f"{r.sample_id}: fg {r.mask_foreground_pixels}+{r.mask_noise_pixels_removed} vs raw {raw_fg}")
    ys, xs = np.nonzero(gray > 127)
    if int(r.mask_noise_pixels_removed) == 0:
        _bad(msgs, (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())) == tuple(int(v) for v in (r.mask_tight_xmin, r.mask_tight_ymin, r.mask_tight_xmax, r.mask_tight_ymax)), f"{r.sample_id}: tight box")
    _bad(msgs, (int(r.width), int(r.height)) == (384, 288) == Image.open(ROOT / r.image_path).size, f"{r.sample_id}: size")
    grey = int(((gray > 0) & (gray < 255)).sum())
    _bad(msgs, json.loads(r.extra_json)["mask_grey_pixels"] == grey, f"{r.sample_id}: grey px")
    meta = pd.read_csv(ROOT / "CVC-ClinicDB/metadata.csv", dtype=str)
    seq = int(meta.loc[meta.frame_id.astype(int) == fid, "sequence_id"].iloc[0])
    _bad(msgs, r.group_id == f"cvc-clinicdb:seq-{seq:02d}", f"{r.sample_id}: group")
    if r.source_type == "image":
        _bad(msgs, _md5(ROOT / r.file_path) == r.image_md5, f"{r.sample_id}: md5")


CHECKS = {"polypsset": check_polypsset, "polypgen-ninja": check_polypgen, "cvc-clinicdb": check_cvc}


# ---------------------------------------------------------------- overlay
def overlay_tile(r: pd.Series) -> Image.Image:
    img = Image.open(ROOT / r.image_path).convert("RGB")
    arr = np.asarray(img).astype(float)
    if r.has_mask:
        if r.mask_format == "supervisely-bitmap-in-json":
            j = json.loads((ROOT / r.mask_path).read_text(encoding="utf-8"))
            for o in j["objects"]:
                m = _decode(o["bitmap"]); ox, oy = o["bitmap"]["origin"]
                sub = arr[oy:oy + m.shape[0], ox:ox + m.shape[1]]
                sub[m] = 0.5 * sub[m] + 0.5 * np.array([0, 255, 0])
        else:
            m = np.asarray(Image.open(ROOT / r.mask_path).convert("L")) > 127
            arr[m] = 0.5 * arr[m] + 0.5 * np.array([0, 255, 0])
    img = Image.fromarray(arr.astype(np.uint8))
    d = ImageDraw.Draw(img)
    if isinstance(r.bboxes_json, str):
        for b in json.loads(r.bboxes_json):
            d.rectangle([b["xmin"], b["ymin"], b["xmax"], b["ymax"]], outline=(255, 0, 0), width=max(2, img.size[0] // 300))
    d.text((6, 6), f"{r.sample_id[-40:]} {r.category}", fill=(255, 255, 0))
    s = 340 / max(img.size)
    return img.resize((int(img.size[0] * s), int(img.size[1] * s)))


def montage(rows: pd.DataFrame, out: Path):
    tiles = [overlay_tile(r) for _, r in rows.iterrows()]
    cols = 4
    W = Image.new("RGB", (350 * cols, 280 * ((len(tiles) + cols - 1) // cols)))
    for i, t in enumerate(tiles):
        W.paste(t, ((i % cols) * 350, (i // cols) * 280))
    W.save(out)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("table", type=Path)
    ap.add_argument("outdir", type=Path)
    ap.add_argument("--n", type=int, default=8)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args(argv)
    df = pd.read_csv(a.table, dtype=str, keep_default_na=False, na_values=[""])
    for col in ("has_mask", "has_bbox"):
        df[col] = df[col] == "True"
    a.outdir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(a.seed)
    msgs: list[str] = []
    for ds, fn in CHECKS.items():
        sub = df[df.dataset == ds]
        if sub.empty:
            continue
        picked = []
        for st, g in sub.groupby("source_type", sort=True):
            idx = sorted(rng.sample(range(len(g)), min(a.n, len(g))))
            picked.append(g.iloc[idx])
            for _, r in g.iloc[idx].iterrows():
                fn(r, msgs)
        # overlay: prefer rows that have geometry plus two negatives / missing-geometry rows
        geo = sub[(sub.source_type == "image") & sub.has_bbox]
        oth = sub[(sub.source_type == "image") & ~sub.has_bbox]
        tiles = pd.concat([geo.iloc[sorted(rng.sample(range(len(geo)), min(10, len(geo))))], oth.iloc[sorted(rng.sample(range(len(oth)), min(2, len(oth))))]]) if len(geo) else oth.head(4)
        montage(tiles, a.outdir / f"{ds}-overlay.png")
        print(f"{ds}: checked {sum(len(p) for p in picked)} rows ({', '.join(f'{st}={len(p)}' for st, p in zip(sorted(sub.source_type.unique()), picked))}); overlay -> {a.outdir / (ds + '-overlay.png')}")
    print("ALL CHECKS PASSED" if not msgs else f"{len(msgs)} MISMATCH(ES):\n  " + "\n  ".join(msgs[:40]))
    return 1 if msgs else 0


if __name__ == "__main__":
    sys.exit(main())
