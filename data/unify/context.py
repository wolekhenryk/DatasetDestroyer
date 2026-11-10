"""What an adapter gets to work with: paths, dataset META defaults, the label vocabulary of the dataset, md5 cache, logging.

An adapter only has to answer: "which files exist, which native class does each one have, where are its boxes / masks / groups".
Everything generic (sizes, md5, duplicates, sample_id, findings_all, is_negative, schema order, validation) is done by build.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import pandas as pd

from . import common as c

VOCAB_DIR = Path(__file__).parent / "vocab"
# columns a vocabulary CSV may set (everything but native_key / note); must be schema columns
VOCAB_FIELDS = ["region", "site", "category", "finding", "finding_harmonized", "finding_parent", "finding_subtype",
                "finding_harmonization", "label_confidence", "imaging", "procedure", "location_source"]


class UnmappedClass(KeyError):
    """A native class has no row in the dataset's vocabulary CSV - add one (the message contains a template row)."""


class Vocab:
    """Native class -> unified label fields, read from unify/vocab/<dataset>.csv (editable in any spreadsheet).

    CSV columns: native_key (required, unique), category + finding (required), the optional columns in VOCAB_FIELDS, note.
    `native_key` is whatever string the adapter uses to look a class up (a folder name, a class id, 'region|category|finding').
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        df = c.read_csv_safe(self.path)
        missing = {"native_key", "category", "finding"} - set(df.columns)
        if missing:
            raise ValueError(f"{self.path.name}: missing required column(s) {sorted(missing)}")
        unknown = set(df.columns) - set(VOCAB_FIELDS) - {"native_key", "note"}
        if unknown:
            raise ValueError(f"{self.path.name}: unknown column(s) {sorted(unknown)}; allowed: native_key, note, {VOCAB_FIELDS}")
        if df["native_key"].duplicated().any():
            raise ValueError(f"{self.path.name}: duplicate native_key {df['native_key'][df['native_key'].duplicated()].tolist()}")
        self.table = df
        self.map = {r["native_key"]: {k: v for k, v in r.items() if k in VOCAB_FIELDS and v != ""} for r in df.to_dict("records")}
        self.used: set[str] = set()

    def get(self, key: str) -> dict:
        if key not in self.map:
            raise UnmappedClass(
                f"native class {key!r} has no row in {self.path.name}. Add a row, e.g.\n"
                f"  {key},<region>,<site>,<category>,<finding>,<finding_harmonized>,... (columns: {list(self.table.columns)})")
        self.used.add(key)
        return dict(self.map[key])

    def unused(self) -> list[str]:
        """Keys in the CSV that no row used in this run (typos / classes that vanished)."""
        return sorted(set(self.map) - self.used)


@dataclass
class Ctx:
    data_root: Path
    meta: dict
    params: dict
    vocab: Vocab | None
    md5_cache: c.Md5Cache
    log: Callable[[str], None] = print
    warnings: list[str] = field(default_factory=list)

    # ---- paths
    @property
    def root(self) -> Path:
        """Folder of this dataset: data_root / META['folder']."""
        return self.data_root / self.meta["folder"]

    def rel(self, path: Path | str) -> str:
        """POSIX path relative to data_root - the form stored in the table."""
        return c.rel_posix(Path(path), self.data_root)

    def md5(self, relpaths) -> dict[str, str]:
        """md5 of files given relative to data_root (shared persistent cache)."""
        return self.md5_cache.get(list(relpaths))

    # ---- reporting
    def warn(self, msg: str):
        """Record a non-fatal data problem (orphans, skipped files...). Shown in the build report and the notebook."""
        self.warnings.append(f"[{self.meta['dataset']}] {msg}")
        self.log(f"  WARNING {msg}")

    # ---- labels
    def label(self, native_key: str) -> dict:
        """Vocabulary fields for a native class (raises UnmappedClass for an unknown one)."""
        if self.vocab is None:
            raise RuntimeError(f"{self.meta['dataset']}: no vocabulary CSV (unify/vocab/{self.meta['dataset']}.csv)")
        return self.vocab.get(native_key)

    def multi_label_fields(self, counts: dict[str, int], raw: dict[str, str] | None = None, areas: dict[str, float] | None = None) -> dict:
        """Label columns for a row carrying several native classes (detection datasets).

        counts: {native_key: n_boxes} IN CLASS-ID ORDER; the primary class is the one with the most boxes, then the largest total box area
        (`areas`, optional), then the lowest class id (first in `counts`).
        raw: {native_key: original class name} for `finding_raw`.
        Returns finding*/category*/findings_all/class_counts_json/n_labels for the row; the primary class fills the single-label columns.
        """
        if not counts:
            raise ValueError("multi_label_fields needs at least one class")
        primary = max(counts, key=lambda k: (counts[k], (areas or {}).get(k, 0)))  # max() keeps the first of equal maxima
        out = dict(self.label(primary))
        harmonised: dict[str, int] = {}
        for k, n in counts.items():
            h = self.label(k).get("finding_harmonized") or self.label(k)["finding"]
            harmonised[h] = harmonised.get(h, 0) + n
        out["finding_raw"] = (raw or {}).get(primary, primary)
        out["findings_all"] = c.pipe_join(harmonised)
        out["class_counts_json"] = c.compact_json(dict(sorted(harmonised.items())))
        out["n_labels"] = len(harmonised)
        return out

    # ---- rows
    def row(self, source_type: str, **fields) -> dict:
        """A row dict with the dataset name and source_type; meta defaults (licence, procedure...) are filled later."""
        return {"source_type": source_type, "dataset": self.meta["dataset"], **fields}

    def frame(self, rows: list[dict]) -> pd.DataFrame:
        return pd.DataFrame(rows)
