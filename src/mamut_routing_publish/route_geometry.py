"""Hash-addressed, publication-only BKS road geometry for Mamut2026."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any


ROUTE_GEOMETRY_FORMAT = "mamut-bks-geometry"
ROUTE_GEOMETRY_FORMAT_VERSION = 1
ROUTE_GEOMETRY_CACHE_DIR = Path("dist/route-geometry-cache")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def route_geometry_cache_path(output_repo_dir: str | Path, bks_path: str | Path) -> Path:
    repo = Path(output_repo_dir)
    bks = Path(bks_path)
    digest = _file_sha256(bks)
    return repo / ROUTE_GEOMETRY_CACHE_DIR / digest[:2] / f"{digest}.route-geometry.json.gz"


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
) -> tuple[Path, dict[str, Any]] | None:
    repo = Path(output_repo_dir)
    bks = Path(bks_path)
    target = route_geometry_cache_path(repo, bks)
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


def _discover_pending(output_repo_dir: Path, *, min_customers: int) -> tuple[list[_PendingBks], int]:
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
            cached = route_geometry_for_bks(output_repo_dir, bks_path, file_hash_cache=validation_hashes)
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


def _group_plan(output_repo_dir: Path, pending: list[_PendingBks]) -> tuple[dict[str, Any], dict[str, _PendingBks]]:
    grouped: dict[tuple[Path, str], list[_PendingBks]] = defaultdict(list)
    pending_by_relpath: dict[str, _PendingBks] = {}
    for entry in pending:
        grouped[(entry.geo_path, entry.metric)].append(entry)
        pending_by_relpath[entry.bks_path.relative_to(output_repo_dir).as_posix()] = entry

    groups: list[dict[str, Any]] = []
    for group_index, ((geo_path, metric), entries) in enumerate(sorted(grouped.items(), key=lambda item: (str(item[0][0]), item[0][1]))):
        with gzip.open(geo_path, "rt", encoding="utf-8") as handle:
            meta = json.load(handle)
        meta["depot_instance_node_id"] = 0
        groups.append(
            {
                "result_file": f"group-{group_index:03d}.json",
                "geo_path": geo_path.relative_to(output_repo_dir).as_posix(),
                "metric": metric,
                "meta": meta,
                "entries": [
                    {
                        "bks_path": entry.bks_path.relative_to(output_repo_dir).as_posix(),
                        "routes": entry.routes,
                    }
                    for entry in entries
                ],
            }
        )
    return {"groups": groups}, pending_by_relpath


def _run_julia_materializer(output_repo_dir: Path, plan: dict[str, Any], temp_dir: Path) -> int:
    julia = shutil.which("julia")
    if julia is None:
        raise RuntimeError("Route-geometry materialization requires Julia on PATH")
    plan_path = temp_dir / "plan.json"
    plan_path.write_text(json.dumps(plan, separators=(",", ":")), encoding="utf-8")
    site_api_path = output_repo_dir / "webapp" / "site_api.jl"
    julia_code = f"""
using JSON3
include({json.dumps(str(site_api_path))})
repo_root = {json.dumps(str(output_repo_dir))}
result_root = {json.dumps(str(temp_dir))}
plan = materialize_json(JSON3.read(read({json.dumps(str(plan_path))}, String)))
groups = plan["groups"]
for (group_index, group) in enumerate(groups)
    meta = group["meta"]
    metric = String(group["metric"])
    geo_path = String(group["geo_path"])
    node_coordinates = workbench_node_coordinates_map(meta)
    map_options = site_api_payload_get(meta, "map_options", Dict{{String,Any}}())
    only_intersections = Bool(site_api_payload_get(map_options, "only_intersections", true))
    trim_to_connected_graph = Bool(site_api_payload_get(map_options, "trim_to_connected_graph", true))
    map_candidates = workbench_route_map_candidates(
        repo_root,
        meta,
        geo_path,
        only_intersections,
        trim_to_connected_graph,
    )
    isempty(map_candidates) && error("No usable OSM road graph was available for " * geo_path)
    edge_cache = Dict{{String,Vector{{Vector{{Float64}}}}}}()
    straight_fallback_edges = Set{{String}}()
    entry_edges = Any[]
    required_edges = Set{{Tuple{{Int,Int}}}}()
    for entry in group["entries"]
        required = Set{{String}}()
        for raw_route in entry["routes"]
            route = Int.(collect(raw_route))
            full_route = [0; route; 0]
            for index in 1:(length(full_route) - 1)
                edge = (full_route[index], full_route[index + 1])
                push!(required_edges, edge)
                push!(required, workbench_node_edge_cache_key(edge...))
            end
        end
        push!(entry_edges, Dict("bks_path" => String(entry["bks_path"]), "edge_keys" => sort!(collect(required))))
    end
    ordered_edges = sort!(collect(required_edges))
    resolved_segments = Vector{{Any}}(undef, length(ordered_edges))
    Threads.@threads for index in eachindex(ordered_edges)
        from_node, to_node = ordered_edges[index]
        resolved_segments[index] = workbench_candidate_route_segment(
            map_candidates,
            from_node,
            to_node,
            node_coordinates[from_node],
            node_coordinates[to_node],
            metric,
        )
        if resolved_segments[index] === nothing
            reverse_segment = workbench_candidate_route_segment(
                map_candidates,
                to_node,
                from_node,
                node_coordinates[to_node],
                node_coordinates[from_node],
                metric,
            )
            resolved_segments[index] = reverse_segment === nothing ? nothing : reverse(reverse_segment)
        end
    end
    for (index, edge) in enumerate(ordered_edges)
        segment = resolved_segments[index]
        if segment === nothing
            from_node, to_node = edge
            segment = [node_coordinates[from_node], node_coordinates[to_node]]
            push!(straight_fallback_edges, workbench_node_edge_cache_key(edge...))
        end
        edge_cache[workbench_node_edge_cache_key(edge...)] = segment
    end
    output = Dict("edge_cache" => edge_cache, "entries" => entry_edges, "straight_fallback_edges" => sort!(collect(straight_fallback_edges)))
    save_json_to_file(output, joinpath(result_root, String(group["result_file"])); indent=0, sort_keys=true)
    if group_index == length(groups) || String(groups[group_index + 1]["geo_path"]) != geo_path
        empty!(WORKBENCH_MAP_CACHE)
        GC.gc()
    end
end
"""
    completed = subprocess.run(
        [julia, f"--project={output_repo_dir / 'webapp'}", "--startup-file=no", "--quiet", "-e", julia_code],
        cwd=output_repo_dir,
        check=False,
        text=True,
    )
    return completed.returncode


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
    target = route_geometry_cache_path(output_repo_dir, entry.bks_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            compressed.write(canonical)
    return target


def materialize_route_geometry(output_repo_dir: str | Path, *, min_customers: int = 101) -> dict[str, Any]:
    output_repo = Path(output_repo_dir).resolve()
    pending, reused = _discover_pending(output_repo, min_customers=min_customers)
    if not pending:
        return {"generated": 0, "reused": reused, "changed_during_run": 0, "groups": 0, "paths": []}
    plan, pending_by_relpath = _group_plan(output_repo, pending)
    written: list[str] = []
    changed_during_run = 0
    with tempfile.TemporaryDirectory(prefix="mamut-route-geometry-") as temp_value:
        temp_dir = Path(temp_value)
        returncode = _run_julia_materializer(output_repo, plan, temp_dir)
        for group in plan["groups"]:
            result_path = temp_dir / group["result_file"]
            if not result_path.is_file():
                continue
            result = json.loads(result_path.read_text(encoding="utf-8"))
            edge_cache = result["edge_cache"]
            straight_fallback_edges = result.get("straight_fallback_edges", [])
            for result_entry in result["entries"]:
                entry = pending_by_relpath[result_entry["bks_path"]]
                target = _save_artifact(
                    output_repo,
                    entry,
                    edge_cache,
                    result_entry["edge_keys"],
                    straight_fallback_edges,
                )
                if target is None:
                    changed_during_run += 1
                    continue
                written.append(target.relative_to(output_repo).as_posix())
        if returncode != 0:
            raise RuntimeError(
                f"Julia route-geometry materialization failed after publishing {len(written)} completed BKS artifacts"
            )
    return {
        "generated": len(written),
        "reused": reused,
        "changed_during_run": changed_during_run,
        "groups": len(plan["groups"]),
        "paths": sorted(written),
    }
