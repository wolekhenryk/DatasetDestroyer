"""Helpers shared by all adapters. Pure functions, no dataset knowledge, no global state (except the md5 cache file).

Conventions used everywhere:
* boxes are integer pixels, top-left origin, corner format (xmin, ymin, xmax, ymax), xmax/ymax INCLUSIVE;
* strings are stripped, empty strings become None (-> empty CSV cell);
* paths stored in the table are POSIX and relative to `data_to_merge/` (see Ctx.rel).
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import pandas as pd
from PIL import Image

# --------------------------------------------------------------------------------------
# text
# --------------------------------------------------------------------------------------
_APOSTROPHES = "'’‘`´"
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def blank_to_none(x):
    """None / NaN / whitespace-only string -> None; other strings are stripped."""
    if x is None or (isinstance(x, float) and math.isnan(x)) or x is pd.NA:
        return None
    if isinstance(x, str):
        x = x.strip()
        return x or None
    return x


def slugify(text) -> str | None:
    """strip -> lower -> delete apostrophes (barrett's -> barretts) -> runs of non-alphanumerics -> '-' -> trim '-'.
    Same rule as the Hyper-Kvasir merge. Returns None for empty / symbol-only input."""
    text = blank_to_none(text)
    if text is None:
        return None
    s = str(text).lower()
    for ch in _APOSTROPHES:
        s = s.replace(ch, "")
    s = _NON_ALNUM.sub("-", s).strip("-")
    return s or None


def pipe_join(items: Iterable[str | None], sort: bool = True) -> str | None:
    """Distinct, non-empty items joined with '|' (sorted by default). None if nothing is left."""
    seen = []
    for i in items:
        i = blank_to_none(i)
        if i is not None and i not in seen:
            seen.append(i)
    if not seen:
        return None
    return "|".join(sorted(seen) if sort else seen)


def compact_json(obj) -> str:
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def make_sample_id(source_type: str, dataset: str, item_id: str, video_id: str | None = None, frame_index: int | None = None) -> str:
    """The one place that defines sample_id: image:<dataset>:<item>, mask:<dataset>:<item>, frame:<dataset>:<video>:<frame:06d>."""
    if source_type == "image":
        return f"image:{dataset}:{item_id}"
    if source_type == "segmentation_mask":
        return f"mask:{dataset}:{item_id}"
    if source_type == "video_frame":
        return f"frame:{dataset}:{video_id}:{int(frame_index):06d}"
    raise ValueError(f"unknown source_type {source_type!r}")


# --------------------------------------------------------------------------------------
# files
# --------------------------------------------------------------------------------------
def read_csv_safe(path: Path, **kw) -> pd.DataFrame:
    """Read a label CSV without pandas surprises: everything as str, NO NA conversion ('NA', 'null', 'None' stay text),
    BOM / CRLF tolerated, header and cells stripped."""
    df = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[], encoding="utf-8-sig", **kw)
    df.columns = [c.strip() for c in df.columns]
    return df.apply(lambda col: col.str.strip())


def rel_posix(path: Path, base: Path) -> str:
    return Path(path).resolve().relative_to(Path(base).resolve()).as_posix()


def natural_key(s: str):
    """Sort key so that 2.png < 10.png."""
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", str(s))]


def image_size(path: Path) -> tuple[int, int]:
    """(width, height) from the file header only (PIL does not decode pixels here)."""
    with Image.open(path) as im:
        return im.size


def image_sizes(paths: Sequence[Path], workers: int = 8) -> list[tuple[int, int]]:
    with ThreadPoolExecutor(workers) as ex:
        return list(ex.map(image_size, paths))


# ---- md5 with a persistent cache keyed by (relative path, size, mtime_ns)
class Md5Cache:
    """Persistent md5 cache. Safe for concurrent builds: the file is re-read and merged at save time and replaced atomically."""

    def __init__(self, cache_file: Path | None, base: Path):
        self.file = Path(cache_file) if cache_file else None
        self.base = Path(base)
        self.entries: dict[str, tuple[int, int, str]] = self._load()
        self.dirty = False

    def _load(self) -> dict[str, tuple[int, int, str]]:
        entries: dict[str, tuple[int, int, str]] = {}
        if self.file and self.file.exists():
            try:
                for line in self.file.read_text(encoding="utf-8").splitlines()[1:]:
                    p, size, mtime, md5 = line.rsplit(",", 3)
                    entries[p] = (int(size), int(mtime), md5)
            except (ValueError, OSError):   # a half-written / foreign file: start clean, the cache is only an accelerator
                return {}
        return entries

    @staticmethod
    def _md5(path: Path) -> str:
        h = hashlib.md5()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()

    def get(self, relpaths: Sequence[str], workers: int = 8) -> dict[str, str]:
        """md5 for every relative path (hashes only what is missing / changed in the cache)."""
        todo, out = [], {}
        for rp in dict.fromkeys(relpaths):
            st = (self.base / rp).stat()
            e = self.entries.get(rp)
            if e and e[0] == st.st_size and e[1] == st.st_mtime_ns:
                out[rp] = e[2]
            else:
                todo.append((rp, st.st_size, st.st_mtime_ns))
        if todo:
            with ThreadPoolExecutor(workers) as ex:
                digests = list(ex.map(lambda t: self._md5(self.base / t[0]), todo))
            for (rp, size, mtime), md5 in zip(todo, digests):
                self.entries[rp] = (size, mtime, md5)
                out[rp] = md5
            self.dirty = True
        return out

    def save(self):
        if self.file and self.dirty:
            import os  # noqa: PLC0415
            self.file.parent.mkdir(parents=True, exist_ok=True)
            merged = {**self._load(), **self.entries}          # keep entries other processes added meanwhile
            lines = ["path,size,mtime_ns,md5"] + [f"{p},{s},{m},{h}" for p, (s, m, h) in sorted(merged.items())]
            tmp = self.file.with_name(f"{self.file.name}.{os.getpid()}.tmp")
            tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
            os.replace(tmp, self.file)
            self.dirty = False


# --------------------------------------------------------------------------------------
# boxes
# --------------------------------------------------------------------------------------
def _snap(v: float, dim: int) -> float:
    """YOLO files store 6 decimals, so an edge that was an integer pixel comes back as e.g. 143.9992: snap it to the integer.
    Tolerance 1e-5*dim pixels (>> the quantisation error 1e-6*dim, << any real sub-pixel annotation)."""
    r = round(v)
    return float(r) if abs(v - r) <= 1e-5 * dim + 1e-9 else v


def yolo_to_box(cx: float, cy: float, w: float, h: float, W: int, H: int, convention: str = "continuous") -> tuple[int, int, int, int]:
    """YOLO normalised (centre x/y, width, height) -> inclusive 0-based pixel corners, clipped to the image.

    convention="continuous" (default; edges are real coordinates in [0, W]): xmin = floor(x0), xmax = ceil(x1)-1 after snapping
        near-integers; a zero-size box becomes a 1-pixel box. Use when the source boxes were drawn on the image plane.
    convention="one-based-inclusive": the normalised edges are 1-based INCLUSIVE integer pixel indices (EAD2020, measured against its
        masks): xmin = round(x0)-1, xmax = round(x1)-1.
    Verify the convention of a new dataset against masks or against the count of boxes touching the border (docs/ADD_A_DATASET.md)."""
    x0, x1 = _snap((cx - w / 2) * W, W), _snap((cx + w / 2) * W, W)
    y0, y1 = _snap((cy - h / 2) * H, H), _snap((cy + h / 2) * H, H)
    if convention == "continuous":
        xmin, xmax, ymin, ymax = math.floor(x0), math.ceil(x1) - 1, math.floor(y0), math.ceil(y1) - 1
    elif convention == "one-based-inclusive":
        xmin, xmax, ymin, ymax = round(x0) - 1, round(x1) - 1, round(y0) - 1, round(y1) - 1
    else:
        raise ValueError(f"unknown convention {convention!r}")
    return clip_box(xmin, ymin, max(xmax, xmin), max(ymax, ymin), W, H)


def clip_box(xmin, ymin, xmax, ymax, W: int, H: int) -> tuple[int, int, int, int]:
    """Clip an inclusive pixel box to [0, W-1] x [0, H-1]."""
    xmin, xmax = max(0, min(int(xmin), W - 1)), max(0, min(int(xmax), W - 1))
    ymin, ymax = max(0, min(int(ymin), H - 1)), max(0, min(int(ymax), H - 1))
    return xmin, ymin, max(xmin, xmax), max(ymin, ymax)


def voc_to_box(xmin, ymin, xmax, ymax, W: int, H: int) -> tuple[int, int, int, int]:
    """Pascal-VOC XML box -> inclusive pixel corners, for datasets whose max edges are HALF-OPEN (xmax == W occurs, never > W).
    Measured for PolypsSet: xmax == W in 60 boxes vs W-1 in 5, ymax == H in 312 vs 61 -> subtract 1 from xmax / ymax.
    Check this against the data of a new dataset before reusing it (docs/ADD_A_DATASET.md)."""
    return clip_box(xmin, ymin, int(xmax) - 1, int(ymax) - 1, W, H)


def union_box(boxes: Sequence[Sequence[int]]) -> tuple[int, int, int, int]:
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


def box_columns(boxes: Sequence[dict], source: str) -> dict:
    """Schema columns for a list of box dicts `{"label", "finding", "xmin","ymin","xmax","ymax"}` (inclusive pixels).
    `source` in schema.BBOX_SOURCES. Empty list -> annotated negative (n_boxes = 0, has_bbox False, no union box)."""
    if not boxes:
        return {"has_bbox": False, "n_boxes": 0, "bbox_source": source}
    u = union_box([(b["xmin"], b["ymin"], b["xmax"], b["ymax"]) for b in boxes])
    items = [{k: b[k] for k in ("label", "finding", "xmin", "ymin", "xmax", "ymax") if k in b} for b in boxes]
    return {
        "has_bbox": True, "n_boxes": len(boxes), "bboxes_json": compact_json(items),
        "bbox_label": pipe_join(b.get("label") for b in boxes),
        "bbox_xmin": u[0], "bbox_ymin": u[1], "bbox_xmax": u[2], "bbox_ymax": u[3], "bbox_source": source,
    }


# --------------------------------------------------------------------------------------
# masks
# --------------------------------------------------------------------------------------
def load_mask(path: Path, threshold: int = 127) -> np.ndarray:
    """Binary mask (bool, True = foreground) from a grey / RGB image file: gray > threshold."""
    with Image.open(path) as im:
        return np.asarray(im.convert("L")) > threshold


def label_components(mask: np.ndarray) -> tuple[np.ndarray, list[tuple[int, int, int, int, int]]]:
    """8-connected components of a bool mask. Returns (label image int32, 0 = background, labels 1..n; list of
    (xmin, ymin, xmax, ymax, area) per label in label order, inclusive pixels, labels sorted by (ymin, xmin)).
    Pure numpy + run-length union-find (scipy is not installed in the project venv)."""
    m = np.asarray(mask, dtype=bool)
    parent: list[int] = []

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    runs: list[tuple[int, int, int]] = []  # (y, x0, x1) per run, index = run id
    prev: list[tuple[int, int, int]] = []  # (x0, x1, run id) of the previous row
    for y in range(m.shape[0]):
        d = np.diff(np.concatenate(([0], m[y].astype(np.int8), [0])))
        starts, ends = np.flatnonzero(d == 1), np.flatnonzero(d == -1) - 1
        cur = []
        j = 0
        for x0, x1 in zip(starts.tolist(), ends.tolist()):
            rid = len(runs)
            runs.append((y, x0, x1))
            parent.append(rid)
            while j < len(prev) and prev[j][1] < x0 - 1:  # previous runs ending left of x0-1 cannot touch
                j += 1
            k = j
            while k < len(prev) and prev[k][0] <= x1 + 1:
                ra, rb = find(rid), find(prev[k][2])
                if ra != rb:
                    parent[rb] = ra
                k += 1
            cur.append((x0, x1, rid))
        prev = cur
    comps: dict[int, list[int]] = {}
    for rid, (y, x0, x1) in enumerate(runs):
        c = comps.setdefault(find(rid), [x0, y, x1, y, 0])
        c[0], c[1], c[2], c[3] = min(c[0], x0), min(c[1], y), max(c[2], x1), max(c[3], y)
        c[4] += x1 - x0 + 1
    order = sorted(comps, key=lambda r: (comps[r][1], comps[r][0]))
    label_of = {root: i + 1 for i, root in enumerate(order)}
    labels = np.zeros(m.shape, dtype=np.int32)
    for rid, (y, x0, x1) in enumerate(runs):
        labels[y, x0:x1 + 1] = label_of[find(rid)]
    return labels, [tuple(comps[r]) for r in order]


def connected_components_boxes(mask: np.ndarray, min_area: int = 1) -> list[tuple[int, int, int, int, int]]:
    """Boxes (xmin, ymin, xmax, ymax, area) of the 8-connected components with at least `min_area` pixels, sorted by (ymin, xmin)."""
    return [c_ for c_ in label_components(mask)[1] if c_[4] >= min_area]


def clean_mask(mask: np.ndarray, min_component_px: int = 0, drop_corner_pixel: bool = False) -> tuple[np.ndarray, int]:
    """Remove noise from a binarised mask; returns (mask, number of foreground pixels removed).
    * drop_corner_pixel: the Hyper-Kvasir JPEG artefact 'single set pixel at (0,0) with all three neighbours unset';
    * min_component_px: drop 8-connected components smaller than this (CVC-ClinicDB: 10; its specks are 1-6 px, the smallest real polyp 190 px)."""
    removed = 0
    if drop_corner_pixel and mask.shape[0] > 1 and mask.shape[1] > 1 and mask[0, 0] and not (mask[0, 1] or mask[1, 0] or mask[1, 1]):
        mask = mask.copy()
        mask[0, 0] = False
        removed += 1
    if min_component_px > 1 and mask.any():
        labels, comps = label_components(mask)
        small = [i + 1 for i, c_ in enumerate(comps) if c_[4] < min_component_px]
        if small:
            kill = np.isin(labels, small)
            removed += int(kill.sum())
            mask = mask & ~kill
    return mask, removed


def mask_columns(mask: np.ndarray, boxes: Sequence[Sequence[int]] | None = None, noise_removed: int | None = None) -> dict:
    """Mask statistics columns for a binary (already cleaned) mask. `boxes` = annotated boxes (inclusive pixels) for the QA columns."""
    H, W = mask.shape
    fg = int(mask.sum())
    out: dict = {"mask_foreground_pixels": fg, "mask_foreground_fraction": round(fg / (W * H), 6)}
    if noise_removed is not None:
        out["mask_noise_pixels_removed"] = int(noise_removed)
    if fg == 0:
        return out
    ys, xs = np.nonzero(mask)
    tight = (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))
    out.update(mask_tight_xmin=tight[0], mask_tight_ymin=tight[1], mask_tight_xmax=tight[2], mask_tight_ymax=tight[3])
    if boxes:
        inside = np.zeros_like(mask)
        for x0, y0, x1, y1 in boxes:
            inside[y0:y1 + 1, x0:x1 + 1] = True
        out["mask_in_bbox_fraction"] = round(int((mask & inside).sum()) / fg, 6)
        u = union_box(boxes)
        out["mask_json_bbox_max_diff_px"] = max(abs(a - b) for a, b in zip(tight, u))
    return out


def mask_derived_boxes(mask: np.ndarray, label: str, finding: str, min_area: int = 10) -> list[dict]:
    """Box dicts (for box_columns(..., 'mask-derived')) = tight boxes of the 8-connected components of at least `min_area` px."""
    return [{"label": label, "finding": finding, "xmin": x0, "ymin": y0, "xmax": x1, "ymax": y1}
            for x0, y0, x1, y1, _ in connected_components_boxes(mask, min_area)]
