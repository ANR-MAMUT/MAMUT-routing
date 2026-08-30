"""Build-time ATF sidecar cache for materialized-td-model families.

Covers the compact td models that ship no committed ATF sidecar:
``igp-profile`` (Lera2026) and ``road-graph`` (Poryos2026 TD). An n=1000
sidecar weighs tens of MB gzipped; the families would be tens of GB. The site
still wants real sidecars — the arc-click viewer fetches one per instance,
and BKS schedule tables need the arrival-time functions — so the publisher
materializes them at build time into ``dist/atf-cache/`` (git-ignored, kept
out of ``benchmarks/``) for instances up to a size cap.

Two structural facts keep the cache small and correct:

- The TDVRPTW/TDVRP twins of an instance share byte-identical ATF content
  (same ``atf_sha256``), so the cache stores ONE file per (benchmark,
  instance name), shared by both problem types.
- Materialization is deterministic and pinned by the instance's recorded
  ``atf_sha256``; a cached file whose recorded-name exists is trusted
  as-is (regeneration would produce the same bytes), so rebuilds are
  incremental.

Above the size cap the viewer simply has no sidecar link (a 28-82 MB
download per arc click is no favour to anyone) and schedule tables are
skipped for those pages.
"""

from __future__ import annotations

import os
import warnings
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

from mamut_routing_lib.td import TD_IGP_MODEL, TD_ROAD_MODEL, load_td_instance, save_instance_atfs

ATF_CACHE_RELATIVE = Path("dist") / "atf-cache"
DEFAULT_MAX_CUSTOMERS = 400
#: Readers for the reuse scan. Purely I/O bound, so threads (not processes):
#: pickling thousands of instance payloads back would cost more than the read.
_SCAN_READ_THREADS = 8

#: td models whose ATFs are materialized on load (no committed sidecar).
MATERIALIZED_TD_MODELS = frozenset({TD_IGP_MODEL, TD_ROAD_MODEL})


def atf_cache_file(cache_dir: Path, benchmark_name: str, instance_name: str) -> Path:
    return cache_dir / benchmark_name / f"{instance_name}.atf.json.gz"


def atf_cache_path(output_repo_dir: Path, benchmark_name: str, instance_name: str) -> Path:
    return atf_cache_file(output_repo_dir / ATF_CACHE_RELATIVE, benchmark_name, instance_name)


def _is_materialized_instance_payload(td_block) -> bool:
    model = td_block.get("model") if isinstance(td_block, dict) else getattr(td_block, "model", None)
    return model in MATERIALIZED_TD_MODELS


def _read_bytes_or_none(path: Path) -> bytes | None:
    """Scan reader: unreadable files are reported, not raised (as before)."""
    try:
        return path.read_bytes()
    except OSError as error:
        warnings.warn(f"Skipping unreadable TD instance {path}: {error}", stacklevel=2)
        return None


def _materialize_one(instance_path_str: str, cache_path_str: str) -> str:
    """Worker: full load (materializes + verifies both sha256) then write."""
    loaded = load_td_instance(instance_path_str)
    save_instance_atfs(loaded.atfs, Path(cache_path_str))
    return cache_path_str


@dataclass
class ATFCacheSummary:
    materialized: list[str] = field(default_factory=list)
    reused: list[str] = field(default_factory=list)
    skipped_over_cap: int = 0

    def as_dict(self) -> dict:
        return {
            "materialized": len(self.materialized),
            "reused": len(self.reused),
            "skipped_over_cap": self.skipped_over_cap,
        }


def materialize_atf_cache(
    output_repo_dir: Path,
    *,
    max_customers: int = DEFAULT_MAX_CUSTOMERS,
    jobs: int | None = None,
    cache_dir: Path | None = None,
    seed_from: Path | None = None,
) -> ATFCacheSummary:
    """Materialize sidecars for every materialized-model instance with n <= max_customers.

    Scans ``benchmarks/TDVRPTW`` and ``benchmarks/TDVRP``; twins collapse onto
    one cache entry. Existing cache files are reused (deterministic content).

    ``cache_dir`` overrides the default ``<repo>/dist/atf-cache`` target for
    staging builds. ``seed_from`` hardlinks an existing cache tree into the
    target first, so a fresh staging dir reuses prior materializations
    instead of regenerating them.
    """
    import json

    from mamut_routing_lib.sidecars import COLLECTION_MARKER_FILENAME

    resolved_cache_dir = cache_dir if cache_dir is not None else output_repo_dir / ATF_CACHE_RELATIVE
    if seed_from is not None and seed_from.resolve() != resolved_cache_dir.resolve():
        from mamut_routing_publish.publish_roots import hardlink_tree

        hardlink_tree(seed_from, resolved_cache_dir)

    summary = ATFCacheSummary()
    tasks: dict[str, str] = {}  # cache path -> instance path (first variant found)
    over_cap: set[str] = set()
    benchmarks_root = output_repo_dir / "benchmarks"
    # Problem-type-first satellites plus the TD trees of family-first
    # collections (marker-rooted, e.g. benchmarks/Poryos2026/TDVRPTW).
    scan_roots = [benchmarks_root / problem_type for problem_type in ("TDVRPTW", "TDVRP")]
    if benchmarks_root.is_dir():
        for candidate in sorted(benchmarks_root.iterdir()):
            if candidate.is_dir() and (candidate / COLLECTION_MARKER_FILENAME).is_file():
                scan_roots.extend(candidate / problem_type for problem_type in ("TDVRPTW", "TDVRP"))
    scan_paths: list[Path] = []
    for root in scan_roots:
        if not root.is_dir():
            continue
        scan_paths.extend(sorted(root.rglob("*.vrp.json")))

    # The scan reads every TD instance file to decide what is already cached.
    # Reading is I/O bound (and slow on a cold checkout), so it runs on a small
    # thread pool; ``map`` preserves order, so the reduction below still walks
    # the files in exactly the scan order and picks exactly the same variants.
    reused_keys: set[str] = set()
    with ThreadPoolExecutor(max_workers=_SCAN_READ_THREADS) as readers:
        for instance_path, raw in zip(scan_paths, readers.map(_read_bytes_or_none, scan_paths, chunksize=32)):
            if raw is None:
                continue
            try:
                # Bytes, not ``read_text()``: json handles the UTF-8 decode itself.
                # ``read_text()`` without an encoding decodes as the locale codepage
                # (cp1252 on Windows), and the resulting UnicodeDecodeError -- a
                # ValueError -- was swallowed below, silently dropping the instance
                # and its schedule table from the site.
                payload = json.loads(raw)
            except ValueError as error:
                warnings.warn(f"Skipping unparseable TD instance {instance_path}: {error}", stacklevel=2)
                continue
            td_block = payload.get("td")
            if not isinstance(td_block, dict) or not _is_materialized_instance_payload(td_block):
                continue
            if int(payload.get("num_customers", 0)) > max_customers:
                over_cap.add(str(payload["instance_name"]))
                summary.skipped_over_cap = len(over_cap)
                continue
            cache_path = atf_cache_file(
                resolved_cache_dir, str(payload["benchmark_name"]), str(payload["instance_name"])
            )
            key = str(cache_path)
            if key in tasks or key in reused_keys:
                continue
            if cache_path.is_file():
                reused_keys.add(key)
                summary.reused.append(key)
                continue
            tasks[key] = str(instance_path)

    if tasks:
        with ProcessPoolExecutor(max_workers=jobs or max(1, (os.cpu_count() or 4) - 2)) as pool:
            futures = {
                pool.submit(_materialize_one, instance_path, cache_path): cache_path
                for cache_path, instance_path in tasks.items()
            }
            for future in as_completed(futures):
                summary.materialized.append(future.result())
    return summary
