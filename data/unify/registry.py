"""Adapter discovery. An adapter is any `unify/adapters/<name>.py` (not starting with '_') that defines META and build(ctx).

Adding a dataset = adding one adapter file + one vocabulary CSV (see docs/ADD_A_DATASET.md). Nothing else is registered by hand.
"""
from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path
from types import ModuleType

from . import schema
from .context import VOCAB_DIR, Vocab

REQUIRED_META = ["dataset", "folder", "license", "procedure", "imaging", "region", "site", "location_source", "expected"]
# top-level folders of data_to_merge/ that are tooling / docs, not datasets
NON_DATASET_DIRS = {"docs", "unify", "__pycache__", ".ipynb_checkpoints"}


def module_name(dataset: str) -> str:
    """Convention: adapter module = dataset name with '-' -> '_' (etis-laribpolypdb -> unify/adapters/etis_laribpolypdb.py)."""
    return dataset.replace("-", "_")


def discover(only: list[str] | None = None) -> dict[str, ModuleType]:
    """{dataset name: adapter module}, sorted by name. Fails loudly on a malformed adapter.
    With `only`, ONLY those adapter modules are imported (found via the naming convention), so a broken adapter under
    development never blocks a build of another dataset."""
    from . import adapters  # noqa: PLC0415

    available = sorted(m.name for m in pkgutil.iter_modules(adapters.__path__) if not m.name.startswith("_"))
    if only:
        missing = [d for d in only if module_name(d) not in available]
        if missing:
            raise SystemExit(f"no adapter module for dataset(s) {missing} (expected unify/adapters/<name with '-' -> '_'>.py); available modules: {available}")
        modules = [module_name(d) for d in only]
    else:
        modules = available
    found: dict[str, ModuleType] = {}
    for name in modules:
        mod = importlib.import_module(f"{adapters.__name__}.{name}")
        check_adapter(mod)
        ds = mod.META["dataset"]
        if module_name(ds) != name:
            raise ValueError(f"{mod.__name__}: META['dataset']={ds!r} does not match the module name (expected module {module_name(ds)}.py)")
        if ds in found:
            raise ValueError(f"two adapters declare dataset {ds!r}")
        found[ds] = mod
    return dict(sorted(found.items()))


def check_adapter(mod: ModuleType) -> None:
    where = mod.__name__
    if not hasattr(mod, "META") or not callable(getattr(mod, "build", None)):
        raise ValueError(f"{where}: must define META (dict) and build(ctx)")
    missing = [k for k in REQUIRED_META if k not in mod.META]
    if missing:
        raise ValueError(f"{where}: META lacks {missing}")
    m = mod.META
    for key, allowed in (("procedure", schema.PROCEDURES), ("imaging", schema.IMAGING), ("region", schema.REGIONS),
                         ("location_source", schema.LOCATION_SOURCES)):
        if m[key] not in allowed:
            raise ValueError(f"{where}: META[{key!r}]={m[key]!r} not in {allowed}")
    if not callable(m["expected"]):   # a dict, or a function(params) -> dict (e.g. Hyper-Kvasir frame rows depend on FRAMES_PER_VIDEO)
        bad = [k for k in m["expected"] if k not in schema.SOURCE_TYPES]
        if bad:
            raise ValueError(f"{where}: META['expected'] keys must be source types, got {bad}")


def load_vocab(meta: dict) -> Vocab | None:
    path = VOCAB_DIR / f"{meta['dataset']}.csv"
    return Vocab(path) if path.exists() else None


def unregistered_folders(data_root: Path, adapters: dict[str, ModuleType]) -> list[str]:
    """Visible top-level folders in data_to_merge/ that no adapter claims -> a dataset waiting to be plugged in."""
    claimed = {m.META["folder"] for m in adapters.values()}
    return sorted(p.name for p in Path(data_root).iterdir()
                  if p.is_dir() and not p.name.startswith(".") and p.name not in NON_DATASET_DIRS and p.name not in claimed)
