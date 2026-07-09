"""Naming and on-disk layout of the Mamut2026 collection (v2, Stream 12').

One base instance = one customer set = one name across every problem type:
``mamut-<city>-n<N>-<method>`` (method in {poi, hyb}). TD subinstances append
``-<model>-<intensity>`` (6 per base). Extra static-only VRPTW TW sets append
``-tw-<set>`` (the ``tw-`` prefix cannot collide with the TD tags); the
TD-paired VRPTW instance keeps the bare base name, mirroring the TDVRPTW
twins that embed the same windows. The family lives in a single family-first
collection repo mounted at ``benchmarks/Mamut2026/``:

    sidecars/<city>/n=<N>/<base>/            shared sidecars of the base
    CVRP/<metric>/<city>/n=<N>/<base>/
    VRPTW/fastest/<city>/n=<N>/<base>/       one file per TW set
    TDVRP/<city>/n=<N>/<base>/<sub>/
    TDVRPTW/<city>/n=<N>/<base>/<sub>/
"""

from __future__ import annotations

from pathlib import Path

FAMILY = "Mamut2026"
METHOD_TAGS = {"poi_categories": "poi", "parametric_attach": "par", "hybrid": "hyb"}

TW_SET_TD_SHARED = "td-shared"
TW_SET_TIGHT = "tight"
TW_SET_SPREAD = "spread"
EXTRA_TW_SETS = (TW_SET_TIGHT, TW_SET_SPREAD)
ALL_TW_SETS = (TW_SET_TD_SHARED, *EXTRA_TW_SETS)


def base_instance_name(city: str, n: int, method_tag: str) -> str:
    return f"mamut-{city}-n{n}-{method_tag}".lower()


def subinstance_name(model: str, intensity: str) -> str:
    return f"{model}-{intensity}".lower()


def td_instance_name(base: str, model: str, intensity: str) -> str:
    return f"{base}-{subinstance_name(model, intensity)}"


def vrptw_instance_name(base: str, tw_set: str) -> str:
    """TD-paired set: the bare base name; static-only sets: ``<base>-tw-<set>``."""
    if tw_set == TW_SET_TD_SHARED:
        return base
    if tw_set not in EXTRA_TW_SETS:
        raise ValueError(f"unknown TW set {tw_set!r} (expected one of {ALL_TW_SETS})")
    return f"{base}-tw-{tw_set}"


def sidecar_dir(collection_root: str | Path, city: str, n: int, base: str) -> Path:
    return Path(collection_root) / "sidecars" / city / f"n={n}" / base


def sidecar_relpath(city: str, n: int, base: str, filename: str) -> str:
    """Collection-root-relative sidecar path (the form stored in instance refs)."""
    return f"sidecars/{city}/n={n}/{base}/{filename}"


def cvrp_dir(collection_root: str | Path, metric: str, city: str, n: int, base: str) -> Path:
    return Path(collection_root) / "CVRP" / metric / city / f"n={n}" / base


def vrptw_dir(collection_root: str | Path, city: str, n: int, base: str) -> Path:
    return Path(collection_root) / "VRPTW" / "fastest" / city / f"n={n}" / base


def td_instance_dir(
    collection_root: str | Path, problem_type: str, city: str, n: int, base: str, sub: str
) -> Path:
    if problem_type not in ("TDVRP", "TDVRPTW"):
        raise ValueError(f"problem_type must be TDVRP or TDVRPTW, got {problem_type!r}")
    return Path(collection_root) / problem_type / city / f"n={n}" / base / sub
