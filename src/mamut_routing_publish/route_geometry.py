"""Hash-addressed, publication-only BKS road geometry for Poryos2026."""

from __future__ import annotations

from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool
from dataclasses import dataclass
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Callable

from mamut_routing_lib.sidecars import COLLECTION_MARKER_FILENAME


ROUTE_GEOMETRY_FORMAT = "mamut-bks-geometry"
ROUTE_GEOMETRY_FORMAT_VERSION = 1
ROUTE_GEOMETRY_CACHE_DIR = Path("dist/route-geometry-cache")
ROUTE_GEOMETRY_SUFFIX = ".route-geometry.json.gz"
#: Companion metadata written next to every cache entry: the scalars and arc
#: keys the validator consults, so a cache hit costs a hash instead of a parse
#: of the whole polyline payload. Named ``.gz`` so ``precompress`` skips it.
ROUTE_GEOMETRY_META_SUFFIX = ".route-geometry.meta.json.gz"
OSM_BOUNDS_TOLERANCE_DEGREES = 1e-5
#: A road-geometry worker holds one parsed OSM extract and multiple graph
#: representations. Large cities can peak above 15 GiB per process, so even
#: two concurrent workers can exhaust a 32 GiB workstation. Callers can still
#: request a larger pool explicitly on hosts with enough memory.
AUTO_MAX_WORKERS = 1


@dataclass(frozen=True)
class RouteGeometryRef:
    """A validated cache hit: where it is, and what callers read off it."""

    path: Path
    bks_sha256: str
    metric: str
    payload_sha256: str


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def route_geometry_cache_path(
    output_repo_dir: str | Path,
    bks_path: str | Path,
    *,
    cache_dir: str | Path | None = None,
    bks_sha256: str | None = None,
) -> Path:
    """Content-addressed cache path of a BKS's route geometry.

    ``bks_sha256`` lets a caller that has already hashed the BKS skip a second
    read of the same file; it must be the sha256 of the file's bytes.
    """
    repo = Path(output_repo_dir)
    bks = Path(bks_path)
    digest = bks_sha256 if bks_sha256 is not None else _file_sha256(bks)
    base = Path(cache_dir) if cache_dir is not None else repo / ROUTE_GEOMETRY_CACHE_DIR
    return base / digest[:2] / f"{digest}{ROUTE_GEOMETRY_SUFFIX}"


def route_geometry_meta_path(payload_path: str | Path) -> Path:
    """Companion metadata path of a route-geometry cache entry."""
    target = Path(payload_path)
    return target.with_name(target.name.removesuffix(ROUTE_GEOMETRY_SUFFIX) + ROUTE_GEOMETRY_META_SUFFIX)


def load_route_geometry(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    with gzip.open(target, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    if payload.get("format") != ROUTE_GEOMETRY_FORMAT:
        raise ValueError(f"Unsupported route-geometry format in {target}")
    if payload.get("format_version") != ROUTE_GEOMETRY_FORMAT_VERSION:
        raise ValueError(f"Unsupported route-geometry format version in {target}")
    return payload


def _expected_path_keys(bks_bytes: bytes) -> set[str]:
    """The arc keys a cached geometry must cover for this BKS's routes."""
    bks_payload = json.loads(bks_bytes)
    expected_paths: set[str] = set()
    for route in bks_payload.get("routes") or []:
        sequence = [0, *[int(stop) for stop in route], 0]
        expected_paths.update(f"{sequence[index]}-{sequence[index + 1]}" for index in range(len(sequence) - 1))
    return expected_paths


def _geometry_check_view(payload: dict[str, Any]) -> dict[str, Any]:
    """The subset of a geometry payload that validation and callers consult.

    Everything outside this view -- ``vertex_lonlat`` and the polylines, 99.86 %
    of the payload bytes -- is parsed today only to be discarded, which is what
    the companion metadata file exists to avoid.
    """
    return {
        "format": payload.get("format"),
        "format_version": payload.get("format_version"),
        "bks_path": payload.get("bks_path"),
        "bks_sha256": payload.get("bks_sha256"),
        "instance_path": payload.get("instance_path"),
        "instance_sha256": payload.get("instance_sha256"),
        "source_geo_path": payload.get("source_geo_path"),
        "source_geo_file_sha256": payload.get("source_geo_file_sha256"),
        "metric": payload.get("metric"),
        "objective_function": payload.get("objective_function"),
        "path_keys": sorted(payload.get("paths") or {}),
    }


def _view_accepts_bks(
    repo: Path,
    bks: Path,
    bks_bytes: bytes,
    digest: str,
    view: dict[str, Any],
    *,
    file_hash_cache: dict[Path, str] | None,
) -> bool:
    """The cache-hit predicate, over the check view of a cached geometry."""
    if view.get("bks_sha256") != digest:
        return False
    if view.get("bks_path") != bks.relative_to(repo).as_posix():
        return False
    instance_path = repo / str(view.get("instance_path") or "")
    if not instance_path.is_file():
        return False
    instance_digest = file_hash_cache.get(instance_path) if file_hash_cache is not None else None
    if instance_digest is None:
        instance_digest = _file_sha256(instance_path)
        if file_hash_cache is not None:
            file_hash_cache[instance_path] = instance_digest
    if view.get("instance_sha256") != instance_digest:
        return False
    geo_file_sha256 = view.get("source_geo_file_sha256")
    if geo_file_sha256:
        geo_path = repo / str(view.get("source_geo_path") or "")
        if not geo_path.is_file():
            return False
        geo_digest = file_hash_cache.get(geo_path) if file_hash_cache is not None else None
        if geo_digest is None:
            geo_digest = _file_sha256(geo_path)
            if file_hash_cache is not None:
                file_hash_cache[geo_path] = geo_digest
        if geo_file_sha256 != geo_digest:
            return False
    return _expected_path_keys(bks_bytes) == set(view.get("path_keys") or ())


def route_geometry_for_bks(
    output_repo_dir: str | Path,
    bks_path: str | Path,
    *,
    file_hash_cache: dict[Path, str] | None = None,
    cache_dir: str | Path | None = None,
    bks_bytes: bytes | None = None,
) -> tuple[Path, dict[str, Any]] | None:
    """The cached route geometry of a BKS, or None when nothing valid is cached.

    Returns the full payload. Callers that only need the reference should use
    ``route_geometry_ref_for_bks``, which reads the companion metadata instead
    of parsing every polyline.

    ``bks_bytes`` lets a caller that has already read the BKS file hand the
    bytes over: the file is otherwise read (and hashed) once here and again by
    ``route_geometry_cache_path``.
    """
    repo = Path(output_repo_dir)
    bks = Path(bks_path)
    if bks_bytes is None:
        bks_bytes = bks.read_bytes()
    digest = _sha256_bytes(bks_bytes)
    target = route_geometry_cache_path(repo, bks, cache_dir=cache_dir, bks_sha256=digest)
    if not target.is_file():
        return None
    payload = load_route_geometry(target)
    view = _geometry_check_view(payload)
    if not _view_accepts_bks(repo, bks, bks_bytes, digest, view, file_hash_cache=file_hash_cache):
        return None
    return target, payload


def route_geometry_ref_for_bks(
    output_repo_dir: str | Path,
    bks_path: str | Path,
    *,
    file_hash_cache: dict[Path, str] | None = None,
    cache_dir: str | Path | None = None,
    bks_bytes: bytes | None = None,
    backfill_meta: bool = False,
) -> RouteGeometryRef | None:
    """Validated reference to a BKS's cached geometry, without parsing it.

    Same accept/reject decision as ``route_geometry_for_bks``, reached through
    the companion metadata when it is present and provably describes the
    payload on disk; otherwise it falls back to the full parse, so caches
    written before the companion existed keep working.

    ``backfill_meta`` writes the companion for an entry that had none, so a
    cache built before this existed upgrades itself on the next run. Only the
    materialization phase passes it: that phase already owns the cache
    directory, and it runs before payload generation in ``site build``, so the
    same build already reads the companions it just backfilled.
    """
    repo = Path(output_repo_dir)
    bks = Path(bks_path)
    if bks_bytes is None:
        bks_bytes = bks.read_bytes()
    digest = _sha256_bytes(bks_bytes)
    target = route_geometry_cache_path(repo, bks, cache_dir=cache_dir, bks_sha256=digest)
    if not target.is_file():
        return None
    view, payload_sha256 = _load_check_view(target, backfill=backfill_meta)
    if not _view_accepts_bks(repo, bks, bks_bytes, digest, view, file_hash_cache=file_hash_cache):
        return None
    return RouteGeometryRef(
        path=target,
        bks_sha256=digest,
        metric=str(view.get("metric") or ""),
        payload_sha256=payload_sha256,
    )


def _load_check_view(target: Path, *, backfill: bool = False) -> tuple[dict[str, Any], str]:
    """Check view of a cached payload, plus the sha256 of the payload file.

    The companion is trusted only when it names the exact payload bytes on
    disk, so a companion left behind by an earlier write of the same BKS (a
    partial materialization later completed, say) can never be mistaken for a
    description of the current payload. Hashing the gzip is ~30x cheaper than
    parsing it, and ``_build_bks_entries`` publishes that same digest anyway.
    """
    payload_bytes = target.read_bytes()
    payload_sha256 = _sha256_bytes(payload_bytes)
    meta_path = route_geometry_meta_path(target)
    if meta_path.is_file():
        try:
            meta = json.loads(gzip.decompress(meta_path.read_bytes()))
        except (OSError, ValueError):
            meta = None
        if (
            isinstance(meta, dict)
            and meta.get("payload_sha256") == payload_sha256
            and meta.get("format") == ROUTE_GEOMETRY_FORMAT
            and meta.get("format_version") == ROUTE_GEOMETRY_FORMAT_VERSION
        ):
            return meta, payload_sha256
    # No usable companion: parse the payload, which also raises on a bad format
    # marker exactly as before.
    payload = json.loads(gzip.decompress(payload_bytes))
    if payload.get("format") != ROUTE_GEOMETRY_FORMAT:
        raise ValueError(f"Unsupported route-geometry format in {target}")
    if payload.get("format_version") != ROUTE_GEOMETRY_FORMAT_VERSION:
        raise ValueError(f"Unsupported route-geometry format version in {target}")
    view = _geometry_check_view(payload)
    if backfill:
        _write_meta_artifact(target, view, payload_sha256)
    return view, payload_sha256


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
    # Every collection, not just the first one that needed this. A collection is
    # marked by its ``mamut-collection.json``; hardcoding one family's directory
    # here silently left the others rendering straight lines between customers no
    # matter how many validated solutions they carried.
    collection_roots = sorted(
        marker.parent
        for marker in (output_repo_dir / "benchmarks").glob("*/" + COLLECTION_MARKER_FILENAME)
    )
    pending: list[_PendingBks] = []
    reused = 0
    geo_file_hashes: dict[Path, str] = {}
    validation_hashes: dict[Path, str] = {}
    for collection_root, instance_path in (
        (root, path) for root in collection_roots for path in sorted(root.rglob("*.vrp.json"))
    ):
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
            # Read once for both the reuse check and the pending entry below.
            bks_bytes = bks_path.read_bytes()
            cached = route_geometry_ref_for_bks(
                output_repo_dir,
                bks_path,
                file_hash_cache=validation_hashes,
                cache_dir=cache_dir,
                bks_bytes=bks_bytes,
                backfill_meta=True,
            )
            if cached is not None:
                reused += 1
                continue
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
    # Generated sidecars can carry the Windows spelling ``osmdata\City.osm``.
    # Treat benchmark paths as portable POSIX paths so Linux/macOS builds read
    # and download them under ``osmdata/`` instead of creating a repository-root
    # filename containing a literal backslash.
    source_osm_file = meta.get("source_osm_file")
    if isinstance(source_osm_file, str):
        meta["source_osm_file"] = source_osm_file.replace("\\", "/")
    meta["depot_instance_node_id"] = 0
    return meta


def _partition_groups_by_source_osm(
    output_repo_dir: Path,
    groups: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    """Separate groups whose referenced raw OSM file is absent or invalid.

    Raw extracts live under the gitignored ``osmdata/`` directory, so a
    normal checkout can publish the site without having every city extract.
    Malformed metadata (including a missing ``source_osm_file`` field) stays
    in the runnable set and is allowed to fail loudly in the materializer.
    """
    from mamut_routing_tools.osm import validate_osm_extract
    from mamut_routing_tools.osm.fetch import FetchError

    available: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    missing_sources: set[str] = set()
    source_by_geo: dict[str, str | None] = {}
    availability_by_source: dict[str, bool] = {}
    for group in groups:
        geo_relpath = str(group["geo_path"])
        if geo_relpath not in source_by_geo:
            meta = _load_group_meta(output_repo_dir, geo_relpath)
            raw_source = meta.get("source_osm_file")
            source_by_geo[geo_relpath] = str(raw_source) if raw_source else None
        source_name = source_by_geo[geo_relpath]
        if source_name is None:
            source_available = True
        else:
            cached_availability = availability_by_source.get(source_name)
            if cached_availability is None:
                source = Path(source_name)
                candidates = (
                    (source,) if source.is_absolute() else (
                        (output_repo_dir / geo_relpath).parent / source,
                        output_repo_dir / source,
                    )
                )
                source_available = False
                for candidate in candidates:
                    try:
                        validate_osm_extract(candidate)
                    except FetchError:
                        continue
                    source_available = True
                    break
                availability_by_source[source_name] = source_available
            else:
                source_available = cached_availability
        if source_available:
            available.append(group)
        else:
            skipped.append(group)
            if source_name is not None:
                missing_sources.add(source_name)
    return available, skipped, sorted(missing_sources)


def _empty_osm_summary() -> dict[str, Any]:
    return {
        "required_files": 0,
        "valid_existing": 0,
        "fetched": 0,
        "invalid_existing": 0,
        "paths": [],
        "downloads": [],
    }


def _requirement_points(output_repo_dir: Path, geo_relpath: str, meta: dict[str, Any]) -> list[tuple[float, float]]:
    geo_path = output_repo_dir / geo_relpath
    road_name = geo_path.name.removesuffix(".geo.json.gz") + ".road.json.gz"
    road_path = geo_path.with_name(road_name)
    if road_path.is_file():
        with gzip.open(road_path, "rt", encoding="utf-8") as handle:
            road = json.load(handle)
        points = road.get("vertex_lonlat")
        if isinstance(points, list) and points:
            return [(float(point[0]), float(point[1])) for point in points]
    nodes = meta.get("nodes")
    if isinstance(nodes, list):
        return [
            (float(node["poi_lon"]), float(node["poi_lat"]))
            for node in nodes
            if isinstance(node, dict) and node.get("poi_lon") is not None and node.get("poi_lat") is not None
        ]
    return []


def _required_osm_files(
    output_repo_dir: Path,
    groups: list[dict[str, Any]],
    *,
    padding_km: float,
) -> list[dict[str, Any]]:
    by_source: dict[str, dict[str, Any]] = {}
    seen_geo: set[str] = set()
    for group in groups:
        geo_relpath = str(group["geo_path"])
        if geo_relpath in seen_geo:
            continue
        seen_geo.add(geo_relpath)
        meta = _load_group_meta(output_repo_dir, geo_relpath)
        raw_source = meta.get("source_osm_file")
        if not raw_source:
            raise ValueError(f"Sidecar '{geo_relpath}' is missing 'source_osm_file'")
        source = Path(str(raw_source))
        if source.is_absolute():
            if not source.is_file():
                raise ValueError(
                    f"Cannot automatically fetch missing absolute source OSM path '{source}' "
                    f"referenced by '{geo_relpath}'"
                )
            target = source
        else:
            target = (output_repo_dir / source).resolve()
            if not target.is_relative_to(output_repo_dir):
                raise ValueError(f"Source OSM path escapes the repository: {raw_source!r}")
        points = _requirement_points(output_repo_dir, geo_relpath, meta)
        if not points:
            raise ValueError(f"Cannot derive an OSM download bbox from '{geo_relpath}'")
        requirement = by_source.setdefault(
            str(raw_source),
            {
                "source_osm_file": str(raw_source),
                "target": target,
                "cities": set(),
                "minlon": float("inf"),
                "minlat": float("inf"),
                "maxlon": float("-inf"),
                "maxlat": float("-inf"),
            },
        )
        requirement["cities"].add(str(meta.get("city") or _city_key(geo_relpath)))
        requirement["minlon"] = min(requirement["minlon"], min(point[0] for point in points))
        requirement["minlat"] = min(requirement["minlat"], min(point[1] for point in points))
        requirement["maxlon"] = max(requirement["maxlon"], max(point[0] for point in points))
        requirement["maxlat"] = max(requirement["maxlat"], max(point[1] for point in points))

    requirements = []
    for requirement in by_source.values():
        requirement["required_bbox"] = {
            "minlat": requirement["minlat"],
            "minlon": requirement["minlon"],
            "maxlat": requirement["maxlat"],
            "maxlon": requirement["maxlon"],
        }
        mean_lat = (requirement["minlat"] + requirement["maxlat"]) / 2.0
        dlat = padding_km / 111.0
        dlon = padding_km / max(1e-6, 111.0 * math.cos(math.radians(mean_lat)))
        requirement["minlat"] -= dlat
        requirement["maxlat"] += dlat
        requirement["minlon"] -= dlon
        requirement["maxlon"] += dlon
        requirement["cities"] = sorted(requirement["cities"])
        requirements.append(requirement)
    return sorted(requirements, key=lambda item: item["source_osm_file"])


def _bounds_cover_required(validation: dict[str, Any], requirement: dict[str, Any]) -> bool:
    bounds = validation["bounds"]
    required = requirement["required_bbox"]
    tolerance = OSM_BOUNDS_TOLERANCE_DEGREES
    return (
        float(bounds["minlat"]) <= required["minlat"] + tolerance
        and float(bounds["minlon"]) <= required["minlon"] + tolerance
        and float(bounds["maxlat"]) >= required["maxlat"] - tolerance
        and float(bounds["maxlon"]) >= required["maxlon"] - tolerance
    )


def ensure_route_geometry_osm(
    output_repo_dir: str | Path,
    groups: list[dict[str, Any]],
    *,
    padding_km: float = 2.0,
    progress: Callable[[str, dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Validate or fetch every raw road extract required by pending groups."""
    from mamut_routing_tools.osm import fetch_and_store_bbox_osm, validate_osm_extract
    from mamut_routing_tools.osm.fetch import FetchError

    output_repo = Path(output_repo_dir).resolve()
    requirements = _required_osm_files(output_repo, groups, padding_km=padding_km)
    summary = _empty_osm_summary()
    summary["required_files"] = len(requirements)
    for index, requirement in enumerate(requirements, start=1):
        target = Path(requirement["target"])
        existing_validation = None
        if target.is_file():
            try:
                existing_validation = validate_osm_extract(target)
            except FetchError:
                summary["invalid_existing"] += 1
        if existing_validation is not None and _bounds_cover_required(existing_validation, requirement):
            summary["valid_existing"] += 1
            summary["paths"].append(str(target))
            continue
        if progress is not None:
            progress(
                "fetching",
                {
                    "source": requirement["source_osm_file"],
                    "city": ",".join(requirement["cities"]),
                    "current": index,
                    "total": len(requirements),
                },
            )
        download = fetch_and_store_bbox_osm(
            requirement["minlat"],
            requirement["minlon"],
            requirement["maxlat"],
            requirement["maxlon"],
            target,
            profile="road_cache",
            progress=(
                None
                if progress is None
                else lambda event: progress(
                    "fetching",
                    {
                        "source": requirement["source_osm_file"],
                        "phase": event["phase"],
                        "current": event["current"],
                        "total": event["total"],
                        "tiles_ok": event["tiles_ok"],
                    },
                )
            ),
        )
        summary["fetched"] += 1
        summary["paths"].append(str(target))
        summary["downloads"].append(
            {
                "source_osm_file": requirement["source_osm_file"],
                "cities": requirement["cities"],
                "bbox": download["bbox"],
                "dataset_mode": download["dataset_mode"],
                "nodes": download["validation"]["nodes"],
                "ways": download["validation"]["ways"],
                "road_tiles": download["road_tiling"]["tiles_total"],
            }
        )
        if progress is not None:
            progress(
                "fetched",
                {
                    "source": requirement["source_osm_file"],
                    "nodes": download["validation"]["nodes"],
                    "ways": download["validation"]["ways"],
                    "current": index,
                    "total": len(requirements),
                },
            )
    summary["paths"].sort()
    return summary


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
        workers = min(AUTO_MAX_WORKERS, max(1, (os.cpu_count() or 2) - 1))
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
    # Written aside and renamed into place: an interrupted build used to leave a
    # truncated .gz behind, and `load_route_geometry` raises on a corrupt entry
    # rather than treating it as a miss -- so one killed run poisoned the cache
    # for every run after it. os.replace is atomic within a filesystem.
    staging = target.with_name(f"{target.name}.{os.getpid()}.partial")
    try:
        with staging.open("wb") as raw:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
                compressed.write(canonical)
        os.replace(staging, target)
    except BaseException:
        staging.unlink(missing_ok=True)
        raise
    # Companion second: interrupted between the two, the entry simply has no
    # companion and validation falls back to parsing the payload. The reverse
    # order could leave metadata describing bytes that were never written.
    _write_meta_artifact(target, _geometry_check_view(payload), _file_sha256(target))
    return target


def _write_meta_artifact(target: Path, view: dict[str, Any], payload_sha256: str) -> Path | None:
    """Write the companion metadata describing one cache entry.

    ``view`` is the check view of the payload and ``payload_sha256`` the digest
    of the payload file it describes, so the two can never disagree. Best
    effort: the companion is an accelerator, and a failure to write one must
    not fail a build whose payload is already published.
    """
    meta = dict(view)
    meta["payload_sha256"] = payload_sha256
    canonical = (json.dumps(meta, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8")
    meta_target = route_geometry_meta_path(target)
    staging = meta_target.with_name(f"{meta_target.name}.{os.getpid()}.partial")
    try:
        with staging.open("wb") as raw:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
                compressed.write(canonical)
        os.replace(staging, meta_target)
    except OSError:
        staging.unlink(missing_ok=True)
        meta_target.unlink(missing_ok=True)
        return None
    return meta_target


def _canonical_cache_relpath(target: Path) -> str:
    return (ROUTE_GEOMETRY_CACHE_DIR / target.parent.name / target.name).as_posix()


def materialize_route_geometry(
    output_repo_dir: str | Path,
    *,
    min_customers: int = 1,
    cache_dir: str | Path | None = None,
    workers: int | str | None = None,
    skip_missing_osm: bool = False,
    fetch_missing_osm: bool = False,
    osm_padding_km: float = 2.0,
    osm_progress: Callable[[str, dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    output_repo = Path(output_repo_dir).resolve()
    resolved_cache_dir = Path(cache_dir).resolve() if cache_dir is not None else None
    pending, reused = _discover_pending(output_repo, min_customers=min_customers, cache_dir=resolved_cache_dir)
    if not pending:
        return {
            "generated": 0,
            "reused": reused,
            "changed_during_run": 0,
            "groups": 0,
            "processed_groups": 0,
            "skipped_missing_osm_groups": 0,
            "skipped_missing_osm_bks": 0,
            "missing_osm_files": [],
            "osm": _empty_osm_summary(),
            "workers": 0,
            "paths": [],
        }
    planned_groups, pending_by_relpath = _group_plan(output_repo, pending)
    osm_summary = _empty_osm_summary()
    if fetch_missing_osm:
        osm_summary = ensure_route_geometry_osm(
            output_repo,
            planned_groups,
            padding_km=osm_padding_km,
            progress=osm_progress,
        )
    groups = planned_groups
    skipped_groups: list[dict[str, Any]] = []
    missing_osm_files: list[str] = []
    if skip_missing_osm:
        groups, skipped_groups, missing_osm_files = _partition_groups_by_source_osm(output_repo, planned_groups)

    batches: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for group in groups:
        batches[_city_key(str(group["geo_path"]))].append(group)
    batch_list = [batches[key] for key in sorted(batches)]
    effective_workers = _resolve_workers(workers, len(batch_list)) if batch_list else 0

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

    if batch_list:
        if effective_workers == 1:
            for batch in batch_list:
                _publish_batch(_materialize_batch(str(output_repo), batch))
        else:
            try:
                with ProcessPoolExecutor(max_workers=effective_workers) as executor:
                    futures = [executor.submit(_materialize_batch, str(output_repo), batch) for batch in batch_list]
                    for future in as_completed(futures):
                        _publish_batch(future.result())
            except BrokenProcessPool as error:
                raise RuntimeError(
                    "A route-geometry worker exited abruptly. This is commonly caused by memory exhaustion because "
                    "each worker holds a multi-gigabyte city road graph. Retry `site build` with "
                    "`--route-geometry-jobs 1`, or the standalone command with `--jobs 1`."
                ) from error
    if failures:
        details = "; ".join(failures)
        raise RuntimeError(
            f"Route-geometry materialization failed for {len(failures)} group(s) after publishing {len(written)} completed BKS artifacts: {details}"
        )
    return {
        "generated": len(written),
        "reused": reused,
        "changed_during_run": changed_during_run,
        "groups": len(planned_groups),
        "processed_groups": len(groups),
        "skipped_missing_osm_groups": len(skipped_groups),
        "skipped_missing_osm_bks": sum(len(group["entries"]) for group in skipped_groups),
        "missing_osm_files": missing_osm_files,
        "osm": osm_summary,
        "workers": effective_workers,
        "paths": sorted(written),
    }
