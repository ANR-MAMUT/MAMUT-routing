"""Hash-addressed, publication-only BKS road geometry for Mamut2026."""

from __future__ import annotations

from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
import gzip
import hashlib
import json
import os
from pathlib import Path
from typing import Any


ROUTE_GEOMETRY_FORMAT = "mamut-bks-geometry"
ROUTE_GEOMETRY_FORMAT_VERSION = 1
ROUTE_GEOMETRY_CACHE_DIR = Path("dist/route-geometry-cache")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def route_geometry_cache_path(
    output_repo_dir: str | Path,
    bks_path: str | Path,
    *,
    cache_dir: str | Path | None = None,
) -> Path:
    repo = Path(output_repo_dir)
    bks = Path(bks_path)
    digest = _file_sha256(bks)
    base = Path(cache_dir) if cache_dir is not None else repo / ROUTE_GEOMETRY_CACHE_DIR
    return base / digest[:2] / f"{digest}.route-geometry.json.gz"


def load_route_geometry(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    with gzip.open(target, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    if payload.get("format") != ROUTE_GEOMETRY_FORMAT:
        raise ValueError(f"Unsupported route-geometry format in {target}")
    if payload.get("format_version") != ROUTE_GEOMETRY_FORMAT_VERSION:
        raise ValueError(f"Unsupported route-geometry format version in {target}")
    return payload


def route_geometry_for_bks(
    output_repo_dir: str | Path,
    bks_path: str | Path,
    *,
    file_hash_cache: dict[Path, str] | None = None,
    cache_dir: str | Path | None = None,
) -> tuple[Path, dict[str, Any]] | None:
    repo = Path(output_repo_dir)
    bks = Path(bks_path)
    target = route_geometry_cache_path(repo, bks, cache_dir=cache_dir)
    if not target.is_file():
        return None
    payload = load_route_geometry(target)
    bks_bytes = bks.read_bytes()
    digest = _sha256_bytes(bks_bytes)
    if payload.get("bks_sha256") != digest:
        return None
    if payload.get("bks_path") != bks.relative_to(repo).as_posix():
        return None
    instance_path = repo / str(payload.get("instance_path") or "")
    if not instance_path.is_file():
        return None
    instance_digest = file_hash_cache.get(instance_path) if file_hash_cache is not None else None
    if instance_digest is None:
        instance_digest = _file_sha256(instance_path)
        if file_hash_cache is not None:
            file_hash_cache[instance_path] = instance_digest
    if payload.get("instance_sha256") != instance_digest:
        return None
    geo_file_sha256 = payload.get("source_geo_file_sha256")
    if geo_file_sha256:
        geo_path = repo / str(payload.get("source_geo_path") or "")
        if not geo_path.is_file():
            return None
        geo_digest = file_hash_cache.get(geo_path) if file_hash_cache is not None else None
        if geo_digest is None:
            geo_digest = _file_sha256(geo_path)
            if file_hash_cache is not None:
                file_hash_cache[geo_path] = geo_digest
        if geo_file_sha256 != geo_digest:
            return None
    bks_payload = json.loads(bks_bytes)
    expected_paths: set[str] = set()
    for route in bks_payload.get("routes") or []:
        sequence = [0, *[int(stop) for stop in route], 0]
        expected_paths.update(f"{sequence[index]}-{sequence[index + 1]}" for index in range(len(sequence) - 1))
    if expected_paths != set(payload.get("paths") or {}):
        return None
    return target, payload


@dataclass(frozen=True)
class _PendingBks:
    instance_path: Path
    instance_sha256: str
    bks_path: Path
    bks_sha256: str
    geo_path: Path
    geo_sha256: str
    geo_file_sha256: str
    metric: str
    objective_function: str
    routes: list[list[int]]


def _metric_for_instance(instance_path: Path, collection_root: Path) -> str | None:
    parts = instance_path.relative_to(collection_root).parts
    problem_type = parts[0]
    if problem_type in {"CVRP", "VRPTW"}:
        metric = parts[1]
        return None if metric == "euclidean" else metric
    if problem_type in {"TDVRP", "TDVRPTW"}:
        return "fastest"
    return None


def _discover_pending(
    output_repo_dir: Path,
    *,
    min_customers: int,
    cache_dir: Path | None = None,
) -> tuple[list[_PendingBks], int]:
    collection_root = output_repo_dir / "benchmarks" / "Mamut2026"
    pending: list[_PendingBks] = []
    reused = 0
    geo_file_hashes: dict[Path, str] = {}
    validation_hashes: dict[Path, str] = {}
    for instance_path in sorted(collection_root.rglob("*.vrp.json")):
        instance_bytes = instance_path.read_bytes()
        instance = json.loads(instance_bytes)
        if int(instance.get("num_customers", 0)) < min_customers:
            continue
        metric = _metric_for_instance(instance_path, collection_root)
        if metric is None:
            continue
        metadata = instance.get("metadata")
        sidecars = metadata.get("sidecars") if isinstance(metadata, dict) else None
        geo_ref = sidecars.get("geo") if isinstance(sidecars, dict) else None
        geo_relpath = geo_ref.get("path") if isinstance(geo_ref, dict) else None
        if not geo_relpath:
            continue
        geo_path = collection_root / str(geo_relpath)
        if not geo_path.is_file():
            continue
        if geo_path not in geo_file_hashes:
            geo_file_hashes[geo_path] = _file_sha256(geo_path)
        geo_file_sha256 = geo_file_hashes[geo_path]
        for bks_path in sorted(instance_path.parent.glob(f"{instance_path.name.removesuffix('.vrp.json')}.bks.*.json")):
            cached = route_geometry_for_bks(output_repo_dir, bks_path, file_hash_cache=validation_hashes, cache_dir=cache_dir)
            if cached is not None:
                reused += 1
                continue
            bks_bytes = bks_path.read_bytes()
            bks = json.loads(bks_bytes)
            routes = bks.get("routes")
            if not isinstance(routes, list) or not routes:
                continue
            pending.append(
                _PendingBks(
                    instance_path=instance_path,
                    instance_sha256=_sha256_bytes(instance_bytes),
                    bks_path=bks_path,
                    bks_sha256=_sha256_bytes(bks_bytes),
                    geo_path=geo_path,
                    geo_sha256=str(geo_ref.get("sha256") or ""),
                    geo_file_sha256=geo_file_sha256,
                    metric=metric,
                    objective_function=str(bks.get("objective_function") or bks_path.name.split(".bks.", 1)[1].removesuffix(".json")),
                    routes=[[int(stop) for stop in route] for route in routes],
                )
            )
    return pending, reused


def _group_plan(output_repo_dir: Path, pending: list[_PendingBks]) -> tuple[list[dict[str, Any]], dict[str, _PendingBks]]:
    """Build slim (meta-free) groups; the batch worker loads each geo meta
    itself, so multi-megabyte sidecars are never pickled across processes."""
    grouped: dict[tuple[Path, str], list[_PendingBks]] = defaultdict(list)
    pending_by_relpath: dict[str, _PendingBks] = {}
    for entry in pending:
        grouped[(entry.geo_path, entry.metric)].append(entry)
        pending_by_relpath[entry.bks_path.relative_to(output_repo_dir).as_posix()] = entry

    groups: list[dict[str, Any]] = []
    for group_index, ((geo_path, metric), entries) in enumerate(sorted(grouped.items(), key=lambda item: (str(item[0][0]), item[0][1]))):
        groups.append(
            {
                "result_file": f"group-{group_index:03d}.json",
                "geo_path": geo_path.relative_to(output_repo_dir).as_posix(),
                "metric": metric,
                "entries": [
                    {
                        "bks_path": entry.bks_path.relative_to(output_repo_dir).as_posix(),
                        "routes": entry.routes,
                    }
                    for entry in entries
                ],
            }
        )
    return groups, pending_by_relpath


def _load_group_meta(output_repo_dir: Path, geo_relpath: str) -> dict[str, Any]:
    with gzip.open(output_repo_dir / geo_relpath, "rt", encoding="utf-8") as handle:
        meta = json.load(handle)
    meta["depot_instance_node_id"] = 0
    return meta


def _city_key(geo_relpath: str) -> str:
    """Batch key so every group of one city lands in the same worker: the
    road graph is built once per (osm, options) and reused across the batch."""
    parts = Path(geo_relpath).parts
    if "sidecars" in parts:
        index = parts.index("sidecars")
        if index + 1 < len(parts):
            return parts[index + 1]
    return str(Path(geo_relpath).parent)


def _materialize_batch(output_repo_dir: str, groups: list[dict[str, Any]]) -> list[tuple[str, str, Any]]:
    from mamut_routing_tools.geometry.materialize import materialize_group
    from mamut_routing_tools.roadgraph import build as roadgraph_build

    repo = Path(output_repo_dir)
    results: list[tuple[str, str, Any]] = []
    try:
        for group in groups:
            try:
                full_group = {**group, "meta": _load_group_meta(repo, str(group["geo_path"]))}
                results.append((str(group["result_file"]), "ok", materialize_group(repo, full_group)))
            except Exception as error:  # noqa: BLE001 - reported per group by the caller
                results.append((str(group["result_file"]), "error", f"{group['geo_path']} [{group['metric']}]: {error}"))
    finally:
        # Pooled workers survive across batches; without this a worker would
        # accumulate one multi-gigabyte road graph per city it processed.
        roadgraph_build.clear_caches()
    return results


def _resolve_workers(workers: int | str | None, batch_count: int) -> int:
    if isinstance(workers, str):
        if workers != "auto":
            raise ValueError(f"workers must be 'auto' or a positive integer, got: {workers!r}")
        workers = None
    if workers is None:
        workers = max(1, (os.cpu_count() or 2) - 1)
    workers = int(workers)
    if workers < 1:
        raise ValueError(f"workers must be >= 1, got: {workers}")
    return min(workers, max(batch_count, 1))


def _indexed_paths(edge_cache: dict[str, list[list[float]]], edge_keys: list[str]) -> tuple[list[list[float]], dict[str, list[int]]]:
    selected = {key: edge_cache[key] for key in edge_keys}
    vertices = sorted({(float(point[0]), float(point[1])) for path in selected.values() for point in path})
    index_of = {point: index for index, point in enumerate(vertices)}
    paths = {
        key.removeprefix("node:").replace("_", "-"): [index_of[(float(point[0]), float(point[1]))] for point in path]
        for key, path in sorted(selected.items())
    }
    return [[lon, lat] for lon, lat in vertices], paths


def _save_artifact(
    output_repo_dir: Path,
    entry: _PendingBks,
    edge_cache: dict[str, list[list[float]]],
    edge_keys: list[str],
    straight_fallback_edges: list[str] | None = None,
    cache_dir: Path | None = None,
) -> Path | None:
    if (
        _file_sha256(entry.bks_path) != entry.bks_sha256
        or _file_sha256(entry.instance_path) != entry.instance_sha256
        or _file_sha256(entry.geo_path) != entry.geo_file_sha256
    ):
        return None
    vertex_lonlat, paths = _indexed_paths(edge_cache, edge_keys)
    payload = {
        "format": ROUTE_GEOMETRY_FORMAT,
        "format_version": ROUTE_GEOMETRY_FORMAT_VERSION,
        "instance_path": entry.instance_path.relative_to(output_repo_dir).as_posix(),
        "instance_sha256": entry.instance_sha256,
        "bks_path": entry.bks_path.relative_to(output_repo_dir).as_posix(),
        "bks_sha256": entry.bks_sha256,
        "objective_function": entry.objective_function,
        "metric": entry.metric,
        "source_geo_path": entry.geo_path.relative_to(output_repo_dir).as_posix(),
        "source_geo_sha256": entry.geo_sha256,
        "source_geo_file_sha256": entry.geo_file_sha256,
        "vertex_lonlat": vertex_lonlat,
        "paths": paths,
        "straight_fallback_paths": sorted(
            key.removeprefix("node:").replace("_", "-")
            for key in (straight_fallback_edges or [])
            if key in edge_keys
        ),
    }
    canonical = (json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8")
    target = route_geometry_cache_path(output_repo_dir, entry.bks_path, cache_dir=cache_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            compressed.write(canonical)
    return target


def _canonical_cache_relpath(target: Path) -> str:
    return (ROUTE_GEOMETRY_CACHE_DIR / target.parent.name / target.name).as_posix()


def materialize_route_geometry(
    output_repo_dir: str | Path,
    *,
    min_customers: int = 1,
    cache_dir: str | Path | None = None,
    workers: int | str | None = None,
) -> dict[str, Any]:
    output_repo = Path(output_repo_dir).resolve()
    resolved_cache_dir = Path(cache_dir).resolve() if cache_dir is not None else None
    pending, reused = _discover_pending(output_repo, min_customers=min_customers, cache_dir=resolved_cache_dir)
    if not pending:
        return {"generated": 0, "reused": reused, "changed_during_run": 0, "groups": 0, "workers": 0, "paths": []}
    groups, pending_by_relpath = _group_plan(output_repo, pending)

    batches: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for group in groups:
        batches[_city_key(str(group["geo_path"]))].append(group)
    batch_list = [batches[key] for key in sorted(batches)]
    effective_workers = _resolve_workers(workers, len(batch_list))

    written: list[str] = []
    changed_during_run = 0
    failures: list[str] = []

    def _publish_batch(batch_result: list[tuple[str, str, Any]]) -> None:
        # Per-group publication: completed groups publish immediately, so
        # earlier results survive a later failure or an interrupted run.
        nonlocal changed_during_run
        for _result_file, status, payload in batch_result:
            if status != "ok":
                failures.append(str(payload))
                continue
            edge_cache = payload["edge_cache"]
            straight_fallback_edges = payload.get("straight_fallback_edges", [])
            for result_entry in payload["entries"]:
                entry = pending_by_relpath[result_entry["bks_path"]]
                target = _save_artifact(
                    output_repo,
                    entry,
                    edge_cache,
                    result_entry["edge_keys"],
                    straight_fallback_edges,
                    cache_dir=resolved_cache_dir,
                )
                if target is None:
                    changed_during_run += 1
                    continue
                written.append(_canonical_cache_relpath(target))

    if effective_workers == 1:
        for batch in batch_list:
            _publish_batch(_materialize_batch(str(output_repo), batch))
    else:
        with ProcessPoolExecutor(max_workers=effective_workers) as executor:
            futures = [executor.submit(_materialize_batch, str(output_repo), batch) for batch in batch_list]
            for future in as_completed(futures):
                _publish_batch(future.result())
    if failures:
        details = "; ".join(failures)
        raise RuntimeError(
            f"Route-geometry materialization failed for {len(failures)} group(s) after publishing {len(written)} completed BKS artifacts: {details}"
        )
    return {
        "generated": len(written),
        "reused": reused,
        "changed_during_run": changed_during_run,
        "groups": len(groups),
        "workers": effective_workers,
        "paths": sorted(written),
    }
