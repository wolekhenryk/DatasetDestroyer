# Splitting the merged table into the six benchmark roles

`unify/split.py` turns `merged-labels.csv` into **one manifest with six disjoint roles**, following the colleague's guide
(*Podział danych do benchmarków endoskopii*). It adds no column to the merged table: it reads it and writes new files.

```bash
cd data
../.venv/bin/python -m unify.split                              # ~30 s (first run: ~1 min for hashes and masks)
../.venv/bin/python -m unify.split --previous split-manifest.csv   # append: earlier group assignments are frozen, only new groups are placed
```

| output | what it is |
|---|---|
| `split-manifest.csv` | **the file to hand over**: one row per original frame (144,082 rows). Guide header `sample_id,group_id,study_id,dataset,domain,image,mask,anatomy,split` + `source_type, frame_index, pool, seg_label, anatomy_source, mask_source, centre, group_quality, split_official` |
| `split-groups.csv` | one row per group: domain, pool, role, studies / frames / labelled frames, stratification labels |
| `near-dup-pairs.csv` | review artefact: every near-duplicate candidate pair with its scores and whether it was linked |
| `docs/split-coverage.md` | generated tables: groups and frames per role, dataset x role, task x class x role, centre, group quality, warnings, manifest md5 |
| `derived/masks/` | normalised masks (9,204 PNGs, not tracked): see "Masks" |

Same inputs and seed give a byte-identical manifest (checked; also with `--previous` on its own output).

## How the guide maps onto the merged table

| guide | here |
|---|---|
| `domain` = capsule / classic | `capsule` = kvasir-capsule, see-ai, datacrohnipi. `classic` = hyper-kvasir, cvc-clinicdb, etis-laribpolypdb, polypgen-ninja, polypsset. `ead2020-train` is **excluded** (below). |
| `image` | `image_path` / `file_path` of the row. Hyper-Kvasir **clip frames** keep the video path plus `frame_index` (frames are addressed, not extracted). |
| `mask` | normalised 0/255 PNG for every frame with a polyp mask **or** a confirmed-empty mask (`seg_label` = `polyp` / `no_polyp`); empty = no segmentation annotation. |
| `anatomy` | `stomach` / `colon` or empty (mapping below); `anatomy_source` says `label` (classic) or `landmark-proxy` (capsule). |
| `study_id` | the adapter's `group_id` (video / sequence / block); Hyper-Kvasir stills have none and use their own `sample_id`. |
| `group_id` | the split unit: studies linked by exact and near duplicates (smallest member id names the group). |
| one row per original frame | mask rows are folded into their image row; `source_type` is `image` or `video_frame`. |

Roles and shares are those of the guide (unannotated pool 95 / 5, annotated pool 10 / 5 / 55 / 10 / 20, counted in **groups**, per domain).
The shares are orientative: the stratification and the refinement below trade them for class coverage.

## Method

1. **Frames and labels.** *Annotated* = the group has at least one frame with a usable label for a benchmark task:
   * **polyp segmentation**: a polyp mask (CVC-ClinicDB, ETIS, PolypGen, Hyper-Kvasir) or a *confirmed* polyp-free frame (PolypGen's 4,275 negatives, which ship with an empty annotation).
     PolypGen's 641 positive frames **without** a mask are not negatives and carry no `seg_label`; they inherit their group's role.
   * **anatomy**: `stomach` (upper GI, site stomach / pylorus) or `colon` (lower GI, site colon / cecum / rectum / anorectum / ileocecal valve), only where the location is a per-image or per-clip *label*
     (`location_source` class-name / label-column). Dataset constants (every PolypsSet frame is colonoscopy) and the heuristic `region_derived` of Kvasir-Capsule do not count.
   Everything else is *unannotated* and goes to the translator pool. A group is annotated if **any** of its frames is labelled; the other frames inherit its role.
2. **Groups.** Start from the study (`group_id` of the merged table), then merge studies that share an exact duplicate (`dup_group_id`; the adapters had already merged duplicate videos)
   or a **near-duplicate** picture:
   * candidates: 16x16 dHash (256 bit) within 24 bits, all pairs inside a domain, exact search, flat/black frames skipped;
   * verification: the dHash alone links visually different smooth frames (capsule, PolypsSet pairs at 3-4 bits looked nothing alike), so the high-passed 16x16 thumbnails of the central half
     of both pictures must correlate: **>= 0.70 when both studies are ungrouped Hyper-Kvasir stills, >= 0.85 otherwise**. Calibrated on contact sheets
     (consecutive Hyper-Kvasir frames of one examination are 0.7-1.0; PolypsSet / PolypGen look-alikes sit at 0.7-0.8, genuine copies there at >= 0.85, SEE-AI duplicates at 0.9998);
   * result: 1,359 study merges; Hyper-Kvasir stills 10,662 -> ~9,300 groups (largest cluster 96 stills); PolypGen `centre-C2` absorbs `seq5, 12-18, 23`
     (C2 singles are resized copies of `seq12`/`seq15` frames, as `docs/datasets/polypgen-ninja.md` already warned) and becomes one 3,361-frame group; no cross-dataset pair was linked.
3. **Assignment.** Per (domain, pool): iterative stratification of groups (Sechidis et al. 2011) over the labels dataset, PolypGen centre, `seg:polyp`, `seg:no_polyp`, `anat:stomach`, `anat:colon`,
   then a seeded swap refinement over groups with >= 15 frames that balances the **labelled frames** per label as well as the group counts (Kvasir-Capsule videos have 74-2,394 frames).
   Before the refinement the capsule test role had 2,022 colon but 268 stomach frames; afterwards 834 / 342.
4. **Masks.** The sources are heterogeneous (JPEG with noise, RGB PNG, Supervisely bitmaps inside JSON). `derived/masks/<dataset>/<item>.png` holds mode-L masks with values 0 / 255 in the original
   geometry, produced with the adapters' own noise handling (`unify/common.py`: `load_mask`, `clean_mask`) and the adapter's bitmap decoder; empty masks for the confirmed negatives.
   Geometry equals the image, polyp frames are non-empty, negatives are all-zero (checked on every dataset; overlays inspected).
5. **Validation (hard asserts, run every time).** Every frame has a role; one group = one role; one study = one group; groups are domain-pure; exact-duplicate clusters are not split;
   unannotated frames only in `translator_train` / `translator_val`; annotated frames only in the five annotated roles; every annotated group has a labelled frame; `mask` iff `seg_label`;
   every image / video / mask path exists; `sample_id` unique. Warnings (not errors): empty roles, groups holding > 5 % of a pool, classes with < 3 groups in a role.

## Result (details: `docs/split-coverage.md`)

| domain / pool | translator_train | translator_posttrain | translator_val | expert_train | expert_val | test |
|---|--:|--:|--:|--:|--:|--:|
| capsule, unannotated: groups / frames | 41 / 20,897 | | 3 / 1,195 | | | |
| capsule, annotated: groups / frames | | 4 / 4,495 | 2 / 2,506 | 24 / 26,011 | 4 / 4,736 | 8 / 9,354 |
| classic, unannotated: groups / frames | 1,804 / 39,385 | | 95 / 2,108 | | | |
| classic, annotated: groups / frames | | 818 / 2,987 | 409 / 1,467 | 4,496 / 17,625 | 819 / 2,927 | 1,636 / 5,858 |

(`translator_val` therefore holds both a 5 % unannotated and a 5 % annotated part, as in the guide; `pool` tells them apart.)
Labelled groups | frames in `test`: classic polyp 246 | 755, classic no-polyp 4 | 752, classic colon 1,235 | 3,990, classic stomach 354 | 471, capsule colon 7 | 834, capsule stomach 6 | 342.

## Things the colleague should know

* **Capsule has no polyp masks.** The only capsule annotations are class labels (Kvasir-Capsule, CrohnIPI) and boxes (SEE-AI), so the capsule polyp-segmentation pool is **empty**: no annotated capsule group
  carries a `seg_label`. Anything in the benchmarks that needs capsule polyp masks (capsule `test`, the capsule->classic direction of the segmentation task) cannot be run with this data.
  Capsule can be used for **anatomy** and for translator training only.
* **Capsule anatomy is a proxy**: pylorus frames = `stomach`, ileocecal-valve frames = `colon` (the only two location labels capsule data has; both are junctions). 42 of 43 Kvasir-Capsule videos have one of them.
  The mapping is `ANATOMY_MAP` in `unify/split.py`; the heuristic `region_derived` (stomach 1,342, colon 44 frames) was deliberately not used.
* **No dataset has a patient id.** Groups are videos (exact), sequences (exact), blocks of consecutive files (SEE-AI 500, CrohnIPI 200: `proxy`) or similarity clusters (Hyper-Kvasir stills: `proxy`). A patient can still
  appear in several groups, and Hyper-Kvasir stills may share an examination with the Hyper-Kvasir clips (undetectable). `group_quality` is in the manifest; the boundary is "study, not patient".
* **Hyper-Kvasir stills dominate the classic group counts** (10,662 of ~11.4k groups before linking), so the guide's percentages of groups are really percentages of stills there; real multi-frame groups are balanced by the refinement.
  Frames per role for polyp segmentation are lumpier than the group counts (polyp frames: 346 / 116 / 3,400 / 312 / 755) because PolypGen's sequences are large and the `centre-C2` cluster (3,361 frames) is one unit.
* **ETIS-LaribPolypDB is one coarse group** (the dataset ships no sequence ids); it landed in `expert_train`. It is the natural candidate for an external test cohort; move it by hand or add it as `external_test` later.
* **PolypsSet** (151 videos, boxes only, location constant) is entirely unannotated -> the classic translator pool (36k of its 38k frames in `translator_train`). Its shipped train / val / test split is ignored (known leaks, `split_official` is kept in the manifest).
* **EAD2020** (2,531 frames) is listed with `split = excluded`: artefact labels only, no GI region, non-GI frames, artefact masks. Change `EXCLUDED` / `DOMAIN` in `unify/split.py` to include it.
* **Not in the table:** the 99,417 unlabeled Hyper-Kvasir images would enlarge the classic translator pool. Add them to the merge, then re-run with `--previous split-manifest.csv`: existing groups keep their role,
  only new groups are placed (an error is raised if new links would merge groups that sit in different roles).
* **Freeze before looking at test results.** The manifest md5 is printed by the script and written to `docs/split-coverage.md`; version the manifest together with `unify/split.py` and the seed.

## Knobs (top of `unify/split.py`)

`SEED`, `RATIOS`, `DOMAIN`, `EXCLUDED`, `ANATOMY_MAP`, `SEG_NEGATIVE_DATASETS`, `LINK_MIN_CORR_UNGROUPED` / `LINK_MIN_CORR_GROUPED`, `DHASH_CANDIDATE_DIST`, `REFINE_MIN_ROWS`, `REFINE_ITERATIONS`.
Hashes are cached in `unify/cache/dhash-cache.csv` (keyed on path, size, mtime; safe to delete); masks that already exist are kept (`--force-masks` rewrites them).
