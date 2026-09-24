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
  ``atf_sha256``, so rebuilds are incremental: an existing entry is reused
  when its uncompressed bytes hash to that pin. The hash is streamed on a
  thread pool (zlib and hashlib release the GIL) and costs about 25 s for
  the full 2 GB cache on 8 threads -- far below one regeneration. An entry
  that fails (a stale pin after a family rebuild, a truncated or corrupt
  gzip) is removed and regenerated, and counted as ``invalidated``.
- Writes are atomic (``save_instance_atfs`` writes a ``*.partial`` sibling
  and renames it), so an interrupted build never leaves a truncated entry
  and a staging cache hard-linked from the live one never truncates the
  live file. Leftover ``*.partial`` files from a killed build are removed
  on the next run and never seeded into a staging cache.

Above the size cap the viewer simply has no sidecar link (a 28-82 MB
download per arc click is no favour to anyone) and schedule tables are
skipped for those pages.
"""

from __future__ import annotations

import os
import warnings
import zlib
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

from mamut_routing_lib.td import (
    TD_IGP_MODEL,
    TD_ROAD_MODEL,
    load_td_instance,
    save_instance_atfs,
)
from mamut_routing_lib.td.artifacts import atf_file_sha256

ATF_CACHE_RELATIVE = Path("dist") / "atf-cache"
DEFAULT_MAX_CUSTOMERS = 400
#: Readers for the reuse scan. Purely I/O bound, so threads (not processes):
#: pickling thousands of instance payloads back would cost more than the read.
_SCAN_READ_THREADS = 8

#: td models whose ATFs are materialized on load (no committed sidecar).
MATERIALIZED_TD_MODELS = frozenset({TD_IGP_MODEL, TD_ROAD_MODEL})
#: Suffix of the temp file an atomic sidecar write renames into place.
PARTIAL_SUFFIX = ".partial"


def resolve_atf_jobs(jobs: int | None = None, task_count: int | None = None) -> int:
    """Effective materialization workers: cores - 2 unless pinned.

    Each worker holds one full ``InstanceATFs`` at a time (hundreds of MB at
    the n=400 cap), so this is the phase's memory knob as much as its speed
    knob -- hence a caller-supplied value is honoured verbatim.

    ``task_count``, when known, clamps the result: an incremental build with a
    handful of stale entries should not fork a worker per core to run three
    tasks. Mirrors ``route_geometry._resolve_workers``.
    """
    if jobs is None:
        resolved = max(1, (os.cpu_count() or 4) - 2)
    elif jobs < 1:
        raise ValueError(f"jobs must be >= 1, got: {jobs}")
    else:
        resolved = jobs
    if task_count is not None:
        resolved = min(resolved, max(task_count, 1))
    return resolved


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
    """Worker: full load (materializes + verifies both sha256) then an atomic write."""
    loaded = load_td_instance(instance_path_str)
    save_instance_atfs(loaded.atfs, Path(cache_path_str))
    return cache_path_str


def cached_entry_problem(cache_path: Path, expected_sha256: str | None) -> str | None:
    """Why a cache entry cannot be reused (``None`` when it can).

    With a pin the uncompressed bytes must hash to it; without one (an
    unpinned instance) the gzip must at least read to the end, which still
    catches truncation.
    """
    try:
        digest = atf_file_sha256(cache_path)
    except (OSError, EOFError, zlib.error) as error:
        return f"unreadable ({error.__class__.__name__}: {error})"
    if expected_sha256 is not None and digest != expected_sha256:
        return f"sha256 {digest} does not match the instance pin {expected_sha256}"
    return None


def remove_partial_files(cache_dir: Path) -> int:
    """Delete ``*.partial`` leftovers of interrupted atomic writes; returns the count."""
    if not cache_dir.is_dir():
        return 0
    removed = 0
    for partial in cache_dir.rglob(f"*{PARTIAL_SUFFIX}"):
        if partial.is_file():
            partial.unlink(missing_ok=True)
            removed += 1
    return removed


@dataclass
class ATFCacheSummary:
    materialized: list[str] = field(default_factory=list)
    reused: list[str] = field(default_factory=list)
    #: Existing entries that failed verification (also in ``materialized``).
    invalidated: list[str] = field(default_factory=list)
    skipped_over_cap: int = 0
    removed_partials: int = 0

    def as_dict(self) -> dict:
        return {
            "materialized": len(self.materialized),
            "reused": len(self.reused),
            "invalidated": len(self.invalidated),
            "skipped_over_cap": self.skipped_over_cap,
            "removed_partials": self.removed_partials,
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
    one cache entry. Existing cache files are reused when they hash to the
    instance's ``atf_sha256`` pin, and regenerated otherwise.

    ``jobs`` pins the worker count (default: cores - 2). ``cache_dir``
    overrides the default ``<repo>/dist/atf-cache`` target for staging
    builds. ``seed_from`` hardlinks an existing cache tree into the
    target first, so a fresh staging dir reuses prior materializations
    instead of regenerating them.
    """
    import json

    from mamut_routing_lib.sidecars import COLLECTION_MARKER_FILENAME

    resolved_cache_dir = cache_dir if cache_dir is not None else output_repo_dir / ATF_CACHE_RELATIVE
    if seed_from is not None and seed_from.resolve() != resolved_cache_dir.resolve():
        from mamut_routing_publish.publish_roots import hardlink_tree

        hardlink_tree(seed_from, resolved_cache_dir)

    summary = ATFCacheSummary(removed_partials=remove_partial_files(resolved_cache_dir))
    tasks: dict[str, str] = {}  # cache path -> instance path (first variant found)
    #: Existing entries to verify: cache path -> (instance path, pin).
    candidates: dict[str, tuple[str, str | None]] = {}
    pins: dict[str, str | None] = {}
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
            pin = td_block.get("atf_sha256")
            pin = str(pin) if pin else None
            if key in pins:
                if pin != pins[key]:
                    warnings.warn(
                        f"TD twins disagree on atf_sha256 for {key} ({pins[key]} vs {pin} in {instance_path}); "
                        "the cache keeps the first, pages of the other lose their schedule table",
                        stacklevel=2,
                    )
                continue
            pins[key] = pin
            if cache_path.is_file():
                candidates[key] = (str(instance_path), pin)
                continue
            tasks[key] = str(instance_path)

    if candidates:
        # Hash every reused entry against its pin. CPU bound in zlib and
        # hashlib, which both release the GIL, so threads scale.
        with ThreadPoolExecutor(max_workers=resolve_atf_jobs(jobs, len(candidates))) as verifiers:
            problems = verifiers.map(
                lambda key: cached_entry_problem(Path(key), candidates[key][1]), list(candidates)
            )
            for key, problem in zip(list(candidates), problems):
                if problem is None:
                    summary.reused.append(key)
                    continue
                warnings.warn(f"Regenerating ATF cache entry {key}: {problem}", stacklevel=2)
                # Unlink, do not truncate: the entry may be a hard link into
                # the live cache a staging build was seeded from.
                Path(key).unlink(missing_ok=True)
                summary.invalidated.append(key)
                tasks[key] = candidates[key][0]

    if tasks:
        with ProcessPoolExecutor(max_workers=resolve_atf_jobs(jobs, len(tasks))) as pool:
            futures = {
                pool.submit(_materialize_one, instance_path, cache_path): cache_path
                for cache_path, instance_path in tasks.items()
            }
            for future in as_completed(futures):
                summary.materialized.append(future.result())
    return summary
