# datacrohnipi (`dataset = datacrohnipi`) - CrohnIPI, small-bowel capsule images of Crohn's disease, one image-level label

Adapter `unify/adapters/datacrohnipi.py`, vocabulary `unify/vocab/datacrohnipi.csv`, analysis `docs/reports/DataCrohnIPI.md`.
`META["expected"] = {"image": 3484}` (verified). Validation: all checks PASS; output byte-identical across runs.

## 1. What it is
* CROHN-IPI dataset, Univ. of Nantes / CHU de Nantes / LS2N / IMAD (https://crohnipi.ls2n.fr/): 3,484 labelled frames from endoscopic video capsules (README); papers: Vallee et al., Proc. SPIE 11317 (2020); de Maissin et al., Endoscopy Int. Open (accepted).
* **Licence**: README = research use only, CC BY-NC-ND (link to the 2.0 text) -> `license = CC BY-NC-ND 2.0 (research use only)`. *NoDerivatives* may restrict cropping / resizing / redistribution of modified images - check before publishing a merged corpus.
* Capsule device not stated (`device` empty); `imaging = white-light` is an inference (capsule LED illumination; the README is silent).

## 2. Layout used / ignored
| path | use |
|---|---|
| `imgs/NNNNN.jpg` | 3,498 files (320x320 RGB, circular field of view), numbered `00001..03498` in capsule-video order |
| `CrohnIPI_description.csv` | `Frame name,Label,Fold`; UTF-8, CRLF, 3,484 rows -> the 3,484 `image` rows |
| `Readme.md` | read by humans only (label legend, licence) |
**14 orphan images** exist on disk without a CSV row (`00042, 00093, 00190, 00191, 00192, 00201, 00222, 00313, 00620, 00707, 00708, 00709, 00710, 01022`): not ingested, build warning (they are unlabeled, not normal). 0 CSV rows without a file.

## 3. Label semantics
**Image-level single label** (`annotation_types = class`, `annotation_format = csv`); no boxes, masks or patient ids. Native code (README legend, French abbreviations) -> unified label; `finding_raw` keeps the code, `finding` is the expanded vocabulary slug (never `slugify("U>10")`):
| code | meaning | images | category | `finding` / `finding_harmonized` | `finding_parent` | `finding_subtype` |
|---|---|--:|---|---|---|---|
| N | normal | 2,124 | `normal` | `normal-mucosa` | `normal-mucosa` | |
| E | erythema | 125 | pathological-findings | `erythema` | | |
| O | (o)edema | 149 | pathological-findings | `edema` | | |
| AU | aphthoid ulceration | 251 | pathological-findings | `aphthoid-ulceration` | `ulcer` | |
| U3-10 | ulceration 3-10 mm | 408 | pathological-findings | `ulcer` | `ulcer` | `3-10mm` |
| U>10 | ulceration over 10 mm | 297 | pathological-findings | `ulcer` | `ulcer` | `gt-10mm` |
| S | stenosis | 130 | pathological-findings | `stenosis` | | |
All mappings are `finding_harmonization = mapped` (the native value is a code), confidence high. `aphthoid-ulceration` is deliberately **not** merged into `erosion` (clinically close small aphthae) - pool through `finding_parent = ulcer` if wanted. `is_negative` is True only for `N`.
`N` = normal mucosa **of a Crohn's disease exam**: the README does not say whether healthy controls are included, so a model trained to separate "normal" in general inherits the Crohn-patient domain.

## 4. Location
`region = small-bowel`, `site = small-bowel` (segment - jejunum / ileum / terminal ileum - **not recorded**), `location_source = readme` ("endoscopic video capsules" + the paper title on the small bowel). `procedure = capsule-small-bowel`.

## 5. Shipped split and leaks
* `split_official = fold-<n>` from `Fold` (1-5; 697 / 697 / 697 / 697 / 696 rows). The README defines it as the **CV test-set number** of a frame (5-fold cross validation, 80 % train / 20 % test): frame `fold-3` is in the held-out part of round 3.
* **The folds leak.** They were drawn at random *per frame*, but the frames are consecutive capsule-video frames (neighbouring file numbers share the label in 85 % of pairs vs 40 % by chance; the agreement reaches chance at ~100 files apart). Near-identical frame pairs (24x24 grey thumbnail cosine >= 0.985: 47 pairs among the labelled frames) are mostly split across folds: 67 frames have such a partner in a different fold and carry `qa_flags = split-leak-known`. The test is conservative (a threshold of 0.98 finds ~144 pairs), so many more near-duplicates exist than are flagged.
* `group_id = datacrohnipi:b200-NNN`, `group_kind = block-proxy`, `group_quality = proxy`: blocks of **200 consecutive file numbers** (orphans keep their numbers), blocks containing a flagged near-duplicate pair merged (union-find; 18 blocks -> 14 groups). It is a proxy for the capsule exam / video segment, **not** patient-level: no patient id exists. Use it instead of `split_official` for leakage-safe splits.

## 6. Technical facts
* 320x320 RGB JPEG for all 3,498 files (14-45 KB), no unreadable file, no byte-identical duplicates (inside the dataset and against all other datasets in `data_to_merge/` and `out/`), no visible text overlay (24 images inspected). The frame looks like a zoomed crop of the capsule image (the field of view fills the square).
* Class imbalance: 61 % normal; lesion classes 125-408 images each.

## 7. `extra_json` keys
`disease_context = "crohns-disease"` (all rows). (`fold` is in `split_official`, the label code in `finding_raw`.)

## 8. Pitfalls
* Leaky official folds, no patient id (see 5).
* 14 unlabeled files in `imgs/` must not be treated as normal.
* Licence CC BY-NC-ND.
* A lesion can occupy a small part of the frame; there is no localisation.
* Near-duplicate detection uses a thumbnail heuristic (threshold `NEARDUP_COS = 0.985` in the adapter); the group merge and the `split-leak-known` flags depend on it.

## 9. Row counts
`image` 3,484; no `segmentation_mask`, no `video_frame` rows.
