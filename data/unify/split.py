"""Group-level split of the merged table into the six benchmark roles (documentation: docs/SPLIT.md).

    cd data
    ../.venv/bin/python -m unify.split                          # merged-labels.csv -> split-manifest.csv, split-groups.csv, near-dup-pairs.csv
    ../.venv/bin/python -m unify.split --previous split-manifest.csv   # keep earlier group assignments, place only new groups
    ../.venv/bin/python -m unify.split --hash-only              # just (re)compute the near-duplicate hash cache

What it does (in this order):
  1. one row per ORIGINAL frame (image rows + Hyper-Kvasir clip frames; mask rows are folded into their image row),
  2. the split unit: `study_id` = the adapter's `group_id` (video / sequence / block; Hyper-Kvasir stills have none -> own id);
     studies are linked into `group_id`s through exact duplicates (`dup_group_id`) and near-duplicates (16x16 dHash),
  3. a group is ANNOTATED when one of its frames has a usable polyp mask / confirmed-empty mask / stomach-colon anatomy label,
  4. groups are assigned to the roles per domain and pool with iterative stratification (Sechidis et al. 2011),
  5. normalised 0/255 mask PNGs are written for the annotated frames (sources are JPEG / RGB PNG / bitmaps inside JSON),
  6. hard validation, then manifest + group table + report.
Deterministic: a fixed seed and sorted traversal give byte-identical outputs.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

from . import common as c
from . import schema

DATA_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = Path(__file__).resolve().parent / "cache"
DHASH_CACHE = CACHE_DIR / "dhash-cache.csv"
MASK_DIR = "derived/masks"                       # normalised masks (relative to DATA_ROOT, gitignored with the rest of data/)

# ======================================================================================
# configuration - everything a reviewer may want to change is here
# ======================================================================================
SEED = 20261115
SPLITS = ["translator_train", "translator_posttrain", "translator_val", "expert_train", "expert_val", "test"]
RATIOS = {                                       # per domain; the guide's orientative shares of GROUPS in each pool
    "unannotated": {"translator_train": 0.95, "translator_val": 0.05},
    "annotated": {"translator_posttrain": 0.10, "translator_val": 0.05, "expert_train": 0.55, "expert_val": 0.10, "test": 0.20},
}
DOMAIN = {                                       # dataset -> imaging domain
    "kvasir-capsule": "capsule", "see-ai": "capsule", "datacrohnipi": "capsule",
    "hyper-kvasir": "classic", "cvc-clinicdb": "classic", "etis-laribpolypdb": "classic", "polypgen-ninja": "classic", "polypsset": "classic",
}
EXCLUDED = {                                     # dataset -> reason; rows stay in the manifest with split = "excluded"
    "ead2020-train": "artefact labels only: no GI region, includes non-GI frames, masks are not polyp masks",
}
# anatomy labels (guide, variant 1: stomach / colon). Key = (region, site) of a row whose location comes from a per-image / per-clip label.
# Capsule: only Kvasir-Capsule landmark frames carry a location -> pylorus = stomach, ileocecal valve = colon (a PROXY, see docs/SPLIT.md).
ANATOMY_MAP = {
    ("upper-gi-tract", "stomach"): "stomach", ("upper-gi-tract", "pylorus"): "stomach",
    ("lower-gi-tract", "colon"): "colon", ("lower-gi-tract", "cecum"): "colon", ("lower-gi-tract", "rectum"): "colon",
    ("lower-gi-tract", "anorectum"): "colon", ("lower-gi-tract", "ileocecal-valve"): "colon",
}
ANATOMY_LOCATION_SOURCES = {"class-name", "label-column"}     # NOT dataset-constant (polyp sets), NOT the heuristic region_derived
SEG_NEGATIVE_DATASETS = {"polypgen-ninja"}       # frames shipped as polyp-free with an (empty) annotation -> confirmed no-polyp

# near-duplicate linking = two stages (calibrated on contact sheets of candidate pairs, see docs/SPLIT.md):
#   1. candidates: 16x16 dHash (256 bits) of the whole picture differs by <= DHASH_CANDIDATE_DIST bits (cheap, exact, all pairs);
#   2. verification: the dHash alone is fooled by smooth frames, vignettes and shared overlays (capsule, PolypsSet: visually different frames
#      at 3-4 bits), so a pair is only linked when the high-passed 16x16 thumbnails of the central half of both pictures correlate enough.
#      Measured: all capsule / PolypsSet / cross-dataset candidates stay <= 0.6 except genuine duplicates; consecutive Hyper-Kvasir frames of one
#      examination reach 0.7-1.0 (checked on contact sheets), while PolypsSet / PolypGen pairs at 0.70-0.80 are mostly look-alike smooth frames of
#      different videos and genuine copies there are >= 0.85 (PolypGen C2 singles vs seq12/seq15 >= 0.95, SEE-AI duplicates 0.9998).
#      Hence two thresholds: loose when BOTH studies are ungrouped Hyper-Kvasir stills (similarity is the only grouping evidence there),
#      stricter as soon as one side already has a real group (video / sequence / block).
DHASH_SIZE = 16
DHASH_CANDIDATE_DIST = 24
LINK_MIN_CORR_UNGROUPED = 0.70
LINK_MIN_CORR_GROUPED = 0.85
REVIEW_MIN_CORR = 0.50                           # pairs from this correlation up are written to near-dup-pairs.csv (linked ones are marked)
DHASH_MIN_STD = 6                                # pictures flatter than this (black / blank frames) say nothing -> never linked
REFINE_MIN_ROWS = 15                             # swap refinement balances labelled FRAMES per stratum; only groups with at least this many frames move
REFINE_ITERATIONS = 40000
GROUP_SHARE_WARN = 0.05                          # warn when one linked group holds more than this share of its (domain, pool)

QUALITY_ORDER = ["none", "coarse", "proxy", "exact"]          # weakest first

READ_COLS = [
    "sample_id", "source_type", "dataset", "item_id", "region", "site", "location_source", "centre", "group_id", "group_kind", "group_quality",
    "split_official", "dup_group_id", "qa_flags", "has_mask", "is_negative", "file_path", "image_path", "mask_path", "parent_image_sample_id",
    "mask_encoding", "video_id", "frame_index", "width", "height", "category", "finding_harmonized",
]


def log(*a):
    print(*a, flush=True)


# ======================================================================================
# 1. rows
# ======================================================================================
def read_table(path: Path) -> pd.DataFrame:
    dtypes = {col: schema.DTYPES[col] for col in READ_COLS if col in schema.DTYPES}
    return pd.read_csv(path, usecols=READ_COLS, dtype=dtypes, keep_default_na=False, na_values=[""], encoding="utf-8")


def build_rows(df: pd.DataFrame) -> pd.DataFrame:
    """One row per original frame: image rows and video frames, with the mask-row facts folded in."""
    masks = df[df.source_type == "segmentation_mask"]
    assert masks.parent_image_sample_id.is_unique, "an image has two mask rows"
    mask_enc = masks.set_index("parent_image_sample_id")["mask_encoding"]
    rows = df[df.source_type != "segmentation_mask"].copy().reset_index(drop=True)
    rows["mask_source"] = rows["mask_path"]
    rows["mask_encoding"] = rows["sample_id"].map(mask_enc)
    rows["has_mask"] = rows["has_mask"].fillna(False).astype(bool)
    rows["is_negative"] = rows["is_negative"].fillna(False).astype(bool)
    assert (rows.has_mask == rows.mask_source.notna()).all(), "has_mask and mask_path disagree"
    missing = set(masks.parent_image_sample_id) - set(rows.sample_id)
    assert not missing, f"mask rows without image row: {sorted(missing)[:3]}"
    # image rows: file_path IS the picture (image_path is only set when a separate annotation file exists); clip frames: the video + frame_index
    rows["image"] = rows["image_path"].fillna(rows["file_path"])
    assert rows.image.notna().all()
    rows["frame_index"] = rows["frame_index"].astype("Int64")
    rows["domain"] = rows["dataset"].map(DOMAIN)
    rows.loc[rows.dataset.isin(EXCLUDED), "domain"] = "excluded"
    unknown = sorted(set(rows.dataset) - set(DOMAIN) - set(EXCLUDED))
    if unknown:
        raise SystemExit(f"dataset(s) {unknown} have no domain: add them to DOMAIN or EXCLUDED in unify/split.py")
    rows["study_id"] = rows["group_id"].fillna(rows["sample_id"])          # no group id (Hyper-Kvasir stills): the picture itself
    rows["study_quality"] = rows["group_quality"].fillna("none")
    return rows


# ======================================================================================
# 2. near-duplicate hash
# ======================================================================================
def _dhash(args):
    """(relative path) -> (hex hash, std). 16x16 dHash of the grey picture; JPEGs are decoded at reduced scale (draft) for speed."""
    from PIL import Image  # noqa: PLC0415
    rel, root = args
    try:
        with Image.open(Path(root) / rel) as im:
            im.draft("L", (4 * DHASH_SIZE, 4 * DHASH_SIZE))
            g = np.asarray(im.convert("L").resize((DHASH_SIZE + 1, DHASH_SIZE), Image.Resampling.BILINEAR), dtype=np.int16)
    except Exception as e:  # noqa: BLE001 - unreadable picture: no hash, reported by the caller
        return rel, "", -1, repr(e)
    bits = (g[:, 1:] > g[:, :-1]).astype(np.uint8)
    return rel, np.packbits(bits).tobytes().hex(), int(round(float(g.std()))), ""


def load_dhash_cache() -> dict[str, tuple[int, int, str, int]]:
    out = {}
    if DHASH_CACHE.exists():
        try:
            for line in DHASH_CACHE.read_text(encoding="utf-8").splitlines()[1:]:
                p, size, mtime, std, h = line.rsplit(",", 4)
                out[p] = (int(size), int(mtime), h, int(std))
        except (ValueError, OSError):
            return {}
    return out


def compute_dhash(relpaths: list[str], root: Path = DATA_ROOT, workers: int = 10) -> dict[str, tuple[str, int]]:
    """{relative path: (hex hash, std)}; cached on (path, size, mtime_ns) like the md5 cache."""
    cache = load_dhash_cache()
    todo, out = [], {}
    for rp in dict.fromkeys(relpaths):
        st = (root / rp).stat()
        e = cache.get(rp)
        if e and e[0] == st.st_size and e[1] == st.st_mtime_ns:
            out[rp] = (e[2], e[3])
        else:
            todo.append((rp, st.st_size, st.st_mtime_ns))
    if todo:
        log(f"   dHash of {len(todo):,} pictures ({len(out):,} cached)")
        t0 = time.time()
        with ProcessPoolExecutor(workers) as ex:
            res = list(ex.map(_dhash, [(t[0], str(root)) for t in todo], chunksize=64))
        bad = [r for r in res if r[1] == ""]
        if bad:
            raise SystemExit(f"{len(bad)} picture(s) could not be read for hashing, e.g. {bad[0][0]}: {bad[0][3]}")
        for (rp, size, mtime), r in zip(todo, res):
            cache[rp] = (size, mtime, r[1], r[2])
            out[rp] = (r[1], r[2])
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        lines = ["path,size,mtime_ns,std,hash"] + [f"{p},{s},{m},{sd},{h}" for p, (s, m, h, sd) in sorted(cache.items())]
        tmp = DHASH_CACHE.with_name(f"{DHASH_CACHE.name}.{os.getpid()}.tmp")
        tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.replace(tmp, DHASH_CACHE)
        log(f"   done in {time.time() - t0:.0f} s")
    return out


def hamming_pairs(H: np.ndarray, study: np.ndarray, t_max: int, block: int = 256) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """All pairs i<j with Hamming distance <= t_max and different study. H = (n, 4) uint64. Exact, blockwise, numpy only."""
    n = len(H)
    ii_all, jj_all, dd_all = [], [], []
    for s in range(0, n, block):
        e = min(n, s + block)
        d = np.zeros((e - s, n - s), dtype=np.uint16)
        for w in range(H.shape[1]):
            d += np.bitwise_count(H[s:e, w][:, None] ^ H[s:, w][None, :])
        d[np.arange(e - s)[:, None] >= np.arange(n - s)[None, :]] = 65535        # keep j > i only
        ii, jj = np.nonzero(d <= t_max)
        keep = study[s + ii] != study[s + jj]
        ii, jj = ii[keep], jj[keep]
        ii_all.append(s + ii)
        jj_all.append(s + jj)
        dd_all.append(d[ii, jj].astype(np.uint16))
    cat = lambda xs, dt: np.concatenate(xs) if xs else np.zeros(0, dtype=dt)  # noqa: E731
    return cat(ii_all, np.int64), cat(jj_all, np.int64), cat(dd_all, np.uint16)


def _thumb(args) -> bytes:
    """16x16 grey thumbnail of the central half of a picture (no borders, overlays or corner boxes)."""
    from PIL import Image  # noqa: PLC0415
    rel, root = args
    with Image.open(Path(root) / rel) as im:
        im.draft("L", (256, 256))
        g = im.convert("L")
        w, h = g.size
        g = g.crop((int(0.25 * w), int(0.25 * h), int(0.75 * w), int(0.75 * h))).resize((16, 16), Image.Resampling.BOX)
        return np.asarray(g, dtype=np.uint8).tobytes()


def _feature(t: bytes) -> np.ndarray:
    """High-pass (thumbnail minus its 5x5 box blur), zero mean, unit norm: structure without illumination / vignette."""
    a = np.frombuffer(t, dtype=np.uint8).reshape(16, 16).astype(np.float32)
    p = np.pad(a, 2, mode="edge")
    blur = sum(p[i:i + 16, j:j + 16] for i in range(5) for j in range(5)) / 25
    v = (a - blur).ravel()
    v -= v.mean()
    n = float(np.linalg.norm(v))
    return v / n if n > 1e-6 else np.zeros_like(v)


def near_duplicate_pairs(rows: pd.DataFrame, workers: int = 10) -> pd.DataFrame:
    """Candidate pairs of pictures of DIFFERENT studies within one domain (dHash <= DHASH_CANDIDATE_DIST) with their verification
    correlation `corr`; rows with corr < REVIEW_MIN_CORR are dropped (they are shared-border / smooth-frame coincidences)."""
    img = rows[(rows.source_type == "image") & (rows.domain != "excluded")]
    hashes = compute_dhash(img.image.tolist(), workers=workers)
    res = []
    for dom, d in img.groupby("domain", sort=True):
        d = d.reset_index(drop=True)
        ungrouped = (d.study_quality == "none").to_numpy()
        hx = [hashes[p][0] for p in d.image]
        sd = np.array([hashes[p][1] for p in d.image])
        ok = sd >= DHASH_MIN_STD
        d, hx, ungrouped = d[ok].reset_index(drop=True), [h for h, k in zip(hx, ok) if k], ungrouped[ok]
        H = np.frombuffer(b"".join(bytes.fromhex(h) for h in hx), dtype=np.uint64).reshape(len(hx), -1)
        i, j, dist = hamming_pairs(H, d.study_id.to_numpy(), DHASH_CANDIDATE_DIST)
        used = np.unique(np.concatenate([i, j]))
        with ProcessPoolExecutor(workers) as ex:
            th = list(ex.map(_thumb, [(d.image[k], str(DATA_ROOT)) for k in used], chunksize=64))
        feat = {k: _feature(t) for k, t in zip(used.tolist(), th)}
        corr = np.array([float(feat[a] @ feat[b]) for a, b in zip(i.tolist(), j.tolist())], dtype=np.float32)
        thr = np.where(ungrouped[i] & ungrouped[j], LINK_MIN_CORR_UNGROUPED, LINK_MIN_CORR_GROUPED).astype(np.float32)
        keep = corr >= REVIEW_MIN_CORR
        log(f"   {dom}: {len(d):,} hashed pictures, {len(i):,} candidate pairs <= {DHASH_CANDIDATE_DIST} bits, {int(keep.sum()):,} with correlation >= {REVIEW_MIN_CORR},"
            f" {int((corr >= thr).sum()):,} linked")
        i, j, dist, corr, thr = i[keep], j[keep], dist[keep], corr[keep], thr[keep]
        res.append(pd.DataFrame({"sample_a": d.sample_id.to_numpy()[i], "sample_b": d.sample_id.to_numpy()[j],
                                 "study_a": d.study_id.to_numpy()[i], "study_b": d.study_id.to_numpy()[j],
                                 "dataset_a": d.dataset.to_numpy()[i], "dataset_b": d.dataset.to_numpy()[j],
                                 "dist": dist, "corr": corr.round(4), "threshold": thr, "domain": dom}))
    out = pd.concat(res, ignore_index=True) if res else pd.DataFrame()
    out["linked"] = out["corr"] >= out["threshold"]
    return out.sort_values(["corr", "sample_a", "sample_b"], ascending=[False, True, True], kind="stable").reset_index(drop=True)


# ======================================================================================
# 3. group linking
# ======================================================================================
class DSU:
    def __init__(self, items):
        self.p = {i: i for i in items}

    def find(self, a):
        p = self.p
        while p[a] != a:
            p[a] = p[p[a]]
            a = p[a]
        return a

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[max(ra, rb)] = min(ra, rb)          # the smallest study id stays the root -> deterministic, stable group ids


def link_groups(rows: pd.DataFrame, pairs: pd.DataFrame) -> pd.DataFrame:
    """Adds `group_id` (the smallest member study_id of a linked cluster) and `group_quality`. Excluded rows keep their own study as group."""
    keep = rows.domain != "excluded"
    dsu = DSU(sorted(rows.study_id.unique()))
    n_exact = 0
    dups = rows[keep & rows.dup_group_id.notna()].groupby("dup_group_id")["study_id"].agg(lambda s: sorted(set(s)))
    for ids in dups:
        for other in ids[1:]:
            n_exact += dsu.find(ids[0]) != dsu.find(other)
            dsu.union(ids[0], other)
    n_near = 0
    if len(pairs):
        for a, b in pairs.loc[pairs.linked, ["study_a", "study_b"]].itertuples(index=False):
            n_near += dsu.find(a) != dsu.find(b)
            dsu.union(a, b)
    log(f"   linked: {n_exact} study merges through exact duplicates, {n_near} through near-duplicates (dHash <= {DHASH_CANDIDATE_DIST} bits and correlation >= {LINK_MIN_CORR_UNGROUPED} for ungrouped stills / {LINK_MIN_CORR_GROUPED} otherwise)")
    rows["group_id"] = rows["study_id"].map(dsu.find)
    # quality of a group = weakest member; a Hyper-Kvasir still ("none") has been clustered by the hash -> "proxy" (it may still share a patient)
    qrank = {q: i for i, q in enumerate(QUALITY_ORDER)}
    q = rows["study_quality"].replace({"none": "proxy"})
    rows["_q"] = q.map(qrank)
    gq = rows.groupby("group_id")["_q"].min().map(lambda i: QUALITY_ORDER[i])
    rows["group_quality"] = rows["group_id"].map(gq)
    return rows.drop(columns="_q")


# ======================================================================================
# 4. labels, pools
# ======================================================================================
def label_rows(rows: pd.DataFrame) -> pd.DataFrame:
    usable = rows.location_source.isin(ANATOMY_LOCATION_SOURCES) & (rows.domain != "excluded")
    anat = pd.Series([ANATOMY_MAP.get(k) for k in zip(rows.region, rows.site)], index=rows.index, dtype="object")
    rows["anatomy"] = anat.where(usable)
    rows["anatomy_source"] = pd.Series(np.where(rows.domain == "capsule", "landmark-proxy", "label"), index=rows.index, dtype="object").where(rows.anatomy.notna())
    is_img = rows.source_type == "image"
    pos = is_img & rows.has_mask & (rows.domain != "excluded") & (rows.dataset != "ead2020-train")
    neg = is_img & rows.dataset.isin(SEG_NEGATIVE_DATASETS) & rows.is_negative & ~rows.has_mask
    rows["seg_label"] = pd.Series(np.select([pos, neg], ["polyp", "no_polyp"], default=""), index=rows.index, dtype="object").replace("", None)
    rows["labelled"] = rows.anatomy.notna() | rows.seg_label.notna()
    return rows


def group_table(rows: pd.DataFrame) -> pd.DataFrame:
    """One row per group: domain, pool, strata labels (what stratification balances), sizes."""
    def labels(g: pd.DataFrame) -> str:
        s = {f"ds:{d}" for d in g.dataset.unique()}
        s |= {f"centre:{c_}" for c_ in g.centre.dropna().unique()}
        s |= {f"seg:{x}" for x in g.seg_label.dropna().unique()}
        s |= {f"anat:{x}" for x in g.anatomy.dropna().unique()}
        return "|".join(sorted(s))
    out = []
    for gid, g in rows.groupby("group_id", sort=True):
        dom = g.domain.unique()
        assert len(dom) == 1, f"group {gid} spans domains {list(dom)}"
        pool = "excluded" if dom[0] == "excluded" else "annotated" if g.labelled.any() else "unannotated"
        out.append({"group_id": gid, "domain": dom[0], "pool": pool, "n_studies": g.study_id.nunique(), "n_rows": len(g),
                    "n_labelled_rows": int(g.labelled.sum()), "datasets": "|".join(sorted(g.dataset.unique())),
                    "group_quality": g.group_quality.iloc[0], "strata": labels(g)})
    return pd.DataFrame(out)


# ======================================================================================
# 5. assignment: iterative stratification on groups
# ======================================================================================
def iterative_stratification(strata: dict[str, set[str]], ratios: dict[str, float], rng: np.random.Generator,
                             fixed: dict[str, str] | None = None) -> dict[str, str]:
    """Sechidis et al. 2011 on groups: always place the groups of the rarest stratum next, each into the split that still needs the most
    groups of that stratum (ties: the split that still needs the most groups overall, then the seeded RNG). `fixed` = earlier assignments."""
    fixed = fixed or {}
    splits = sorted(ratios)
    n = len(strata)
    all_labels = sorted({lab for s in strata.values() for lab in s})
    cnt = {lab: sum(lab in s for s in strata.values()) for lab in all_labels}
    need_l = {s: {lab: cnt[lab] * ratios[s] for lab in all_labels} for s in splits}
    need_n = {s: n * ratios[s] for s in splits}
    out = {}
    for g, s in fixed.items():
        if g in strata and s in need_n:
            out[g] = s
            need_n[s] -= 1
            for lab in strata[g]:
                need_l[s][lab] -= 1
    remaining = [g for g in sorted(strata) if g not in out]
    order = {g: r for g, r in zip(remaining, rng.permutation(len(remaining)))}
    by_label = {lab: {g for g in remaining if lab in strata[g]} for lab in all_labels}
    left = set(remaining)
    while left:
        lab = min((lb for lb in all_labels if by_label[lb]), key=lambda lb: (len(by_label[lb]), lb))
        for g in sorted(by_label[lab], key=order.get):
            best = max(splits, key=lambda s: (need_l[s][lab], need_n[s], rng.random()))
            out[g] = best
            need_n[best] -= 1
            for lb in strata[g]:
                need_l[best][lb] -= 1
                by_label[lb].discard(g)
            left.discard(g)
    return out


def label_frames(rows: pd.DataFrame, group_ids: set[str]) -> dict[str, dict[str, int]]:
    """{group: {stratum label: frames}} - all frames for ds:/centre:, labelled frames for seg:/anat:; plus '__all__' = all frames."""
    r = rows[rows.group_id.isin(group_ids)]
    parts = [r.groupby(["group_id", "dataset"]).size().rename("n").reset_index().assign(label=lambda d: "ds:" + d.dataset)[["group_id", "label", "n"]],
             r.dropna(subset=["centre"]).groupby(["group_id", "centre"]).size().rename("n").reset_index().assign(label=lambda d: "centre:" + d.centre)[["group_id", "label", "n"]],
             r.dropna(subset=["seg_label"]).groupby(["group_id", "seg_label"]).size().rename("n").reset_index().assign(label=lambda d: "seg:" + d.seg_label)[["group_id", "label", "n"]],
             r.dropna(subset=["anatomy"]).groupby(["group_id", "anatomy"]).size().rename("n").reset_index().assign(label=lambda d: "anat:" + d.anatomy)[["group_id", "label", "n"]],
             r.groupby("group_id").size().rename("n").reset_index().assign(label="__all__")[["group_id", "label", "n"]]]
    out: dict[str, dict[str, int]] = {}
    for g, lab, n in pd.concat(parts).itertuples(index=False):
        out.setdefault(g, {})[lab] = int(n)
    return out


def refine(assign: dict[str, str], lf: dict[str, dict[str, int]], ratios: dict[str, float], rng: np.random.Generator,
           frozen: set[str], iterations: int = REFINE_ITERATIONS) -> dict[str, str]:
    """Hill-climb on moves / swaps of single groups. Loss = chi-square of the GROUP counts and of the FRAME shares per stratum against the
    targets (+ a penalty for a stratum that misses a role it should have). Keeps the group-count targets because they are part of the loss."""
    splits = sorted(ratios)
    r = np.array([ratios[s] for s in splits])
    groups = sorted(assign)
    labels = sorted({lab for g in groups for lab in lf[g]})
    li = {lab: k for k, lab in enumerate(labels)}
    G = np.zeros((len(groups), len(labels)))                      # groups per label (indicator)
    F = np.zeros((len(groups), len(labels)))                      # frames per label
    for a, g in enumerate(groups):
        for lab, n in lf[g].items():
            G[a, li[lab]] = 1
            F[a, li[lab]] = n
    NL, FL = G.sum(0), F.sum(0)
    req = np.minimum(2, np.floor(np.outer(NL, r) + 0.5))           # (L, S): groups a stratum should have in a role
    core = np.array([s in ("expert_train", "expert_val", "test", "translator_train") for s in splits])
    sid = {s: k for k, s in enumerate(splits)}
    cur = np.array([sid[assign[g]] for g in groups])

    def stats(cur_):
        n = np.zeros((len(labels), len(splits)))
        f = np.zeros_like(n)
        for k in range(len(splits)):
            m = cur_ == k
            n[:, k] = G[m].sum(0)
            f[:, k] = F[m].sum(0)
        return n, f

    def loss(n, f):
        exp_n = np.outer(NL, r)
        a = ((n - exp_n) ** 2 / (exp_n + 1)).sum()
        b = (((f / np.maximum(FL[:, None], 1)) - r[None, :]) ** 2 / r[None, :]).sum()
        pen = (np.maximum(req - n, 0)[:, core] ** 2).sum()
        return a + 20 * b + 3 * pen

    n, f = stats(cur)
    best = loss(n, f)
    movable = [a for a, g in enumerate(groups) if g not in frozen]
    if len(movable) < 2:
        return assign
    for _ in range(iterations):
        a = movable[rng.integers(len(movable))]
        if rng.random() < 0.5:                                    # move
            k = int(rng.integers(len(splits)))
            if k == cur[a]:
                continue
            n2, f2 = n.copy(), f.copy()
            for x, new in ((a, k),):
                n2[:, cur[x]] -= G[x]; f2[:, cur[x]] -= F[x]; n2[:, new] += G[x]; f2[:, new] += F[x]
            ch = [(a, k)]
        else:                                                     # swap
            b = movable[rng.integers(len(movable))]
            if cur[a] == cur[b]:
                continue
            n2, f2 = n.copy(), f.copy()
            for x, new in ((a, cur[b]), (b, cur[a])):
                n2[:, cur[x]] -= G[x]; f2[:, cur[x]] -= F[x]; n2[:, new] += G[x]; f2[:, new] += F[x]
            ch = [(a, int(cur[b])), (b, int(cur[a]))]
        l2 = loss(n2, f2)
        if l2 < best - 1e-12:
            best, n, f = l2, n2, f2
            for x, new in ch:
                cur[x] = new
    return {g: splits[cur[a]] for a, g in enumerate(groups)}


def assign_splits(groups: pd.DataFrame, rows: pd.DataFrame, fixed: dict[str, str], seed: int) -> pd.Series:
    """split per group_id. Per (domain, pool) independently; excluded groups get 'excluded'."""
    res = pd.Series("excluded", index=groups.group_id, dtype="object")
    for (dom, pool), g in groups.groupby(["domain", "pool"], sort=True):
        if pool == "excluded":
            continue
        base = [seed, int(hashlib.md5(f"{dom}/{pool}".encode()).hexdigest()[:8], 16)]
        strata = {r.group_id: set(r.strata.split("|")) for r in g.itertuples()}
        fx = {k: v for k, v in fixed.items() if k in strata}
        a = iterative_stratification(strata, RATIOS[pool], np.random.default_rng(base), fx)
        light = set(g.loc[g.n_rows < REFINE_MIN_ROWS, "group_id"])           # singletons stay where stratification put them
        a = refine(a, label_frames(rows, set(strata)), RATIOS[pool], np.random.default_rng(base + [1]), frozen=set(fx) | light)
        res.loc[list(a)] = list(a.values())
    return res


# ======================================================================================
# 6. normalised masks
# ======================================================================================
MASK_CLEAN = {                                   # same noise handling as the adapters (unify/adapters/*.py), so masks equal the table's statistics
    "cvc-clinicdb": dict(min_component_px=10),                 # grey specks of 1-6 px
    "hyper-kvasir": dict(drop_corner_pixel=True),              # isolated JPEG pixel at (0, 0)
}


def _safe(name: str) -> str:
    import re  # noqa: PLC0415
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)


def mask_relpath(dataset: str, item_id: str) -> str:
    return f"{MASK_DIR}/{dataset}/{_safe(item_id)}.png"


def _make_mask(args) -> tuple[str, str]:
    """(row facts) -> writes the normalised mask (L, 0/255, original geometry); returns (relpath, error or '')."""
    import json  # noqa: PLC0415
    from PIL import Image  # noqa: PLC0415
    dataset, item_id, seg_label, src, W, H, root, force = args
    rel = mask_relpath(dataset, item_id)
    out = Path(root) / rel
    if out.exists() and not force:
        return rel, ""
    try:
        if seg_label == "no_polyp":
            m = np.zeros((H, W), dtype=bool)                     # confirmed-empty mask
        elif dataset == "polypgen-ninja":                        # Supervisely bitmaps inside the annotation JSON, OR over instances
            from .adapters.polypgen_ninja import _decode_bitmap  # noqa: PLC0415
            j = json.loads((Path(root) / src).read_text(encoding="utf-8"))
            m = np.zeros((H, W), dtype=bool)
            for o in j["objects"]:
                crop = _decode_bitmap(o["bitmap"])
                ox, oy = o["bitmap"]["origin"]
                h, w = crop.shape
                if not crop.any() or ox < 0 or oy < 0 or ox + w > W or oy + h > H:
                    continue                                       # the adapter skips these instances as well
                m[oy:oy + h, ox:ox + w] |= crop
        else:
            m, _ = c.clean_mask(c.load_mask(Path(root) / src), **MASK_CLEAN.get(dataset, {}))
        if m.shape != (H, W):
            return rel, f"mask geometry {m.shape[::-1]} != image {(W, H)}"
        if seg_label == "polyp" and not m.any():
            return rel, "empty mask for a polyp frame"
        out.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(m.astype(np.uint8) * 255, mode="L").save(out)
    except Exception as e:  # noqa: BLE001
        return rel, repr(e)
    return rel, ""


def write_masks(rows: pd.DataFrame, force: bool = False, workers: int = 8) -> pd.Series:
    """Normalised mask path for every labelled-for-segmentation row (index-aligned Series, NA elsewhere)."""
    from concurrent.futures import ThreadPoolExecutor  # noqa: PLC0415
    sel = rows[rows.seg_label.notna()]
    args = [(r.dataset, r.item_id, r.seg_label, r.mask_source if r.seg_label == "polyp" else None, int(r.width), int(r.height), str(DATA_ROOT), force)
            for r in sel.itertuples()]
    t0 = time.time()
    with ThreadPoolExecutor(workers) as ex:
        res = list(ex.map(_make_mask, args))
    errs = [(a[0], a[1], e) for a, (_, e) in zip(args, res) if e]
    if errs:
        raise SystemExit(f"{len(errs)} mask(s) failed, e.g. {errs[:3]}")
    log(f"   {len(res):,} normalised masks in {MASK_DIR}/ ({time.time() - t0:.0f} s)")
    return pd.Series([r for r, _ in res], index=sel.index, dtype="object")


# ======================================================================================
# 7. validation and report
# ======================================================================================
def validate(rows: pd.DataFrame, groups: pd.DataFrame, check_files: bool = True) -> list[str]:
    """Hard asserts (raise) + soft findings (returned as warnings)."""
    warns = []
    def ok(cond, msg):
        if not cond:
            raise AssertionError(msg)
    ok(rows.sample_id.is_unique, "sample_id not unique")
    ok(rows.split.notna().all(), "rows without split")
    ok(set(rows.split) <= set(SPLITS) | {"excluded"}, f"unknown split values {set(rows.split) - set(SPLITS)}")
    ok((rows.groupby("group_id").split.nunique() == 1).all(), "a group spans two splits")
    ok((rows.groupby("study_id").group_id.nunique() == 1).all(), "a study is in two groups")
    ok((rows.groupby("group_id").domain.nunique() == 1).all(), "a group spans two domains")
    dd = rows[rows.dup_group_id.notna() & (rows.domain != "excluded")]
    ok((dd.groupby("dup_group_id").split.nunique() == 1).all(), "an exact-duplicate cluster spans two splits")
    un = rows[rows.pool == "unannotated"]
    ok(un.split.isin(["translator_train", "translator_val"]).all(), "unannotated frame outside translator_train/translator_val")
    an = rows[rows.pool == "annotated"]
    ok(an.split.isin(RATIOS["annotated"]).all(), "annotated frame in a role it does not have")
    ok((groups[groups.pool == "annotated"].n_labelled_rows > 0).all(), "annotated group without a labelled frame")
    ok(((rows.seg_label.notna()) == rows["mask"].notna()).all(), "mask present iff seg_label present")
    ok(rows[rows.split == "excluded"].domain.eq("excluded").all(), "excluded rows must be the excluded datasets")
    if check_files:
        miss = [p for p in rows.image.unique() if not (DATA_ROOT / p).is_file()]
        ok(not miss, f"{len(miss)} image/video path(s) missing, e.g. {miss[:2]}")
        miss = [p for p in rows["mask"].dropna().unique() if not (DATA_ROOT / p).is_file()]
        ok(not miss, f"{len(miss)} mask path(s) missing, e.g. {miss[:2]}")
    # soft findings
    for (dom, pool), g in groups[groups.pool != "excluded"].groupby(["domain", "pool"]):
        roles = list(RATIOS[pool])
        got = set(g.split)
        if len(g) >= len(roles) and not set(roles) <= got:
            warns.append(f"{dom}/{pool}: no group in {sorted(set(roles) - got)}")
        big = g[g.n_rows > GROUP_SHARE_WARN * g.n_rows.sum()]
        for r in big.itertuples():
            warns.append(f"{dom}/{pool}: group {r.group_id} holds {r.n_rows / g.n_rows.sum():.0%} of the frames ({r.n_rows:,}) -> {r.split}")
    ann = rows[rows.pool == "annotated"]
    for kind, col in (("seg", "seg_label"), ("anatomy", "anatomy")):
        t = ann.dropna(subset=[col]).groupby(["domain", col, "split"]).group_id.nunique().unstack("split", fill_value=0).reindex(columns=SPLITS, fill_value=0)
        for (dom, cls), r in t.iterrows():
            few = [s for s in ("expert_train", "expert_val", "test") if r[s] < 3]
            if few:
                warns.append(f"{dom}/{kind}/{cls}: fewer than 3 groups in {few} ({', '.join(f'{s}={int(r[s])}' for s in few)})")
    return warns


def _tbl(df: pd.DataFrame) -> str:
    return "```\n" + df.to_string() + "\n```\n"


def coverage_report(rows: pd.DataFrame, groups: pd.DataFrame, warns: list[str], pairs: pd.DataFrame, info: dict) -> str:
    out = [f"# Split coverage (generated by `python -m unify.split`; seed {info['seed']}, manifest md5 `{info['md5']}`)\n",
           "Counts are **groups** unless the heading says frames. Roles per pool: unannotated = translator_train / translator_val; "
           "annotated = translator_posttrain / translator_val / expert_train / expert_val / test.\n"]
    gs = groups[groups.pool != "excluded"]
    cols = SPLITS
    out.append("## Groups per domain, pool and role (actual | target share)\n")
    n = gs.groupby(["domain", "pool", "split"]).size().unstack("split", fill_value=0).reindex(columns=cols, fill_value=0)
    n["total"] = n.sum(axis=1)
    pct = (n[cols].div(n["total"], axis=0) * 100).round(1)
    tgt = pd.DataFrame({k: {s: RATIOS[k].get(s, 0) * 100 for s in cols} for k in RATIOS}).T
    out.append(_tbl(n))
    out.append("actual share of groups, %:\n" + _tbl(pct))
    out.append("target share, %:\n" + _tbl(tgt))
    out.append("## Frames per domain, pool and role\n")
    fr = gs.groupby(["domain", "pool", "split"]).n_rows.sum().unstack("split", fill_value=0).reindex(columns=cols, fill_value=0)
    out.append(_tbl(fr))
    out.append("## Dataset x role (groups | frames)\n")
    r = rows[rows.domain != "excluded"]
    a = r.groupby(["domain", "dataset", "pool", "split"]).group_id.nunique().unstack("split", fill_value=0).reindex(columns=cols, fill_value=0)
    b = r.groupby(["domain", "dataset", "pool", "split"]).size().unstack("split", fill_value=0).reindex(columns=cols, fill_value=0)
    out.append("groups containing frames of the dataset:\n" + _tbl(a) + "frames:\n" + _tbl(b))
    out.append("## Task coverage: groups | labelled frames per role (annotated pool)\n")
    ann = rows[rows.pool == "annotated"]
    for title, col in (("Polyp segmentation (seg_label)", "seg_label"), ("Anatomy (stomach / colon)", "anatomy")):
        sub = ann.dropna(subset=[col])
        if sub.empty:
            continue
        gtab = sub.groupby(["domain", col, "split"]).group_id.nunique().unstack("split", fill_value=0).reindex(columns=SPLITS, fill_value=0)
        ftab = sub.groupby(["domain", col, "split"]).size().unstack("split", fill_value=0).reindex(columns=SPLITS, fill_value=0)
        out.append(f"### {title}\ngroups:\n" + _tbl(gtab) + "labelled frames:\n" + _tbl(ftab))
    present = set(map(tuple, ann.dropna(subset=["seg_label"])[["domain", "seg_label"]].drop_duplicates().to_numpy().tolist()))
    for dom in ("capsule", "classic"):
        for cls in ("polyp", "no_polyp"):
            if (dom, cls) not in present:
                out.append(f"**No `{cls}` segmentation frames exist in the `{dom}` domain** (no annotated group).\n")
    cen = rows[rows.centre.notna() & (rows.domain != "excluded")]
    if len(cen):
        out.append("## Centre (PolypGen C1-C6; the only dataset that names one) x role, groups\n" +
                   _tbl(cen.groupby(["centre", "split"]).group_id.nunique().unstack("split", fill_value=0).reindex(columns=SPLITS, fill_value=0)))
    out.append("## Group quality x role (groups)\n" +
               _tbl(gs.groupby(["domain", "group_quality", "split"]).size().unstack("split", fill_value=0).reindex(columns=cols, fill_value=0)))
    out.append("## Near-duplicate linking\n")
    if len(pairs):
        lk = pairs[pairs.linked]
        out.append(f"{len(pairs):,} candidate pairs reviewed (corr >= {REVIEW_MIN_CORR}), {len(lk):,} linked (corr >= {LINK_MIN_CORR_UNGROUPED} between two ungrouped stills, >= {LINK_MIN_CORR_GROUPED} otherwise). "
                   "Linked pairs by dataset combination:\n" + _tbl(lk.assign(combo=lk.dataset_a + " ~ " + lk.dataset_b).groupby("combo").size().to_frame("pairs")))
    multi = groups[(groups.n_studies > 1) & (groups.pool != "excluded")]
    out.append(f"Groups formed from more than one study: {len(multi):,} (largest {int(multi.n_studies.max()) if len(multi) else 0} studies, "
               f"{int(multi.n_rows.max()) if len(multi) else 0:,} frames).\n")
    out.append("## Warnings\n" + ("\n".join(f"* {w}" for w in warns) if warns else "none") + "\n")
    return "\n".join(out)


# ======================================================================================
# main
# ======================================================================================
MANIFEST_COLS = ["sample_id", "group_id", "study_id", "dataset", "domain", "image", "mask", "anatomy", "split",
                 "source_type", "frame_index", "pool", "seg_label", "anatomy_source", "mask_source", "centre", "group_quality", "split_official"]
GROUP_COLS = ["group_id", "domain", "pool", "split", "n_studies", "n_rows", "n_labelled_rows", "datasets", "group_quality", "strata"]


def write_csv(df: pd.DataFrame, path: Path) -> None:
    df.to_csv(path, index=False, lineterminator="\n", encoding="utf-8", na_rep="")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m unify.split", description=__doc__.split("\n")[0])
    ap.add_argument("--csv", type=Path, default=DATA_ROOT / "merged-labels.csv")
    ap.add_argument("--out-dir", type=Path, default=DATA_ROOT)
    ap.add_argument("--previous", type=Path, help="an earlier split-manifest.csv: keep its study -> split assignments, place only new groups")
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--no-masks", action="store_true", help="skip writing normalised masks (the `mask` column is then not validated on disk)")
    ap.add_argument("--force-masks", action="store_true", help="rewrite masks that already exist")
    ap.add_argument("--hash-only", action="store_true", help="only (re)compute the near-duplicate hash cache")
    ap.add_argument("--workers", type=int, default=10)
    a = ap.parse_args(argv)

    t0 = time.time()
    log(f"== read {a.csv}")
    rows = build_rows(read_table(a.csv))
    log(f"   {len(rows):,} frames ({rows.source_type.value_counts().to_dict()}), {rows.study_id.nunique():,} studies")
    if a.hash_only:
        compute_dhash(rows[(rows.source_type == "image") & (rows.domain != "excluded")].image.tolist(), workers=a.workers)
        return
    log("== near-duplicates")
    pairs = near_duplicate_pairs(rows, workers=a.workers)
    log("== groups")
    rows = link_groups(rows, pairs)
    rows = label_rows(rows)
    groups = group_table(rows)
    fixed = {}
    if a.previous:
        prev = pd.read_csv(a.previous, usecols=["study_id", "split"], keep_default_na=False, na_values=[""])
        pm = dict(zip(prev.study_id, prev.split))
        sp = rows.assign(_p=rows.study_id.map(pm)).dropna(subset=["_p"]).groupby("group_id")["_p"].agg(lambda s: sorted(set(s)))
        bad = sp[sp.map(len) > 1]
        if len(bad):
            raise SystemExit(f"new links merge groups that were assigned to different splits earlier: {bad.head(5).to_dict()}")
        fixed = {g: v[0] for g, v in sp.items() if v[0] != "excluded"}
        log(f"   --previous: {len(fixed):,} groups keep their earlier split")
    by_pool = {f"{d}/{p}": n for (d, p), n in groups.groupby(["domain", "pool"]).size().items()}
    log(f"   {len(groups):,} groups: " + ", ".join(f"{k}={v:,}" for k, v in by_pool.items()))
    groups["split"] = groups.group_id.map(assign_splits(groups, rows, fixed, a.seed))
    rows["split"] = rows.group_id.map(groups.set_index("group_id").split)
    rows["pool"] = rows.group_id.map(groups.set_index("group_id").pool)
    log("== masks")
    rows["mask"] = None
    if not a.no_masks:
        rows.loc[rows.seg_label.notna(), "mask"] = write_masks(rows, force=a.force_masks, workers=a.workers)
    else:
        rows.loc[rows.seg_label.notna(), "mask"] = [mask_relpath(d, i) for d, i in zip(rows.dataset[rows.seg_label.notna()], rows.item_id[rows.seg_label.notna()])]
    log("== validate")
    warns = validate(rows, groups, check_files=not a.no_masks)
    for w in warns:
        log("   WARNING", w)

    a.out_dir.mkdir(parents=True, exist_ok=True)
    manifest = rows[MANIFEST_COLS]
    mf = a.out_dir / "split-manifest.csv"
    write_csv(manifest, mf)
    write_csv(groups[GROUP_COLS], a.out_dir / "split-groups.csv")
    if len(pairs):
        write_csv(pairs.drop(columns=["domain"]), a.out_dir / "near-dup-pairs.csv")
    md5 = hashlib.md5(mf.read_bytes()).hexdigest()
    rep = coverage_report(rows, groups, warns, pairs, {"seed": a.seed, "md5": md5})
    docs = a.out_dir / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "split-coverage.md").write_text(rep, encoding="utf-8")
    log(rep)
    log(f"== wrote {mf} ({len(manifest):,} rows, md5 {md5}), split-groups.csv, near-dup-pairs.csv, docs/split-coverage.md in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
