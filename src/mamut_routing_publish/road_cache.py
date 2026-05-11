from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any

from mamut_routing_lib.json_utils import load_json_from_file


ROAD_CACHE_METRICS = ("fastest", "shortest")


def _sidecar_node_offset(meta_payload: dict[str, Any]) -> int:
    nodes = meta_payload.get("nodes")
    if not isinstance(nodes, list):
        return 1
    node_ids = [
        int(node["instance_node_id"])
        for node in nodes
        if isinstance(node, dict) and "instance_node_id" in node
    ]
    return 0 if node_ids and min(node_ids) == 0 else 1


def _routes_from_bks_paths(meta_payload: dict[str, Any], bks_paths: list[Path]) -> list[list[int]]:
    depot_node_id = int(meta_payload.get("depot_instance_node_id", 1))
    node_offset = _sidecar_node_offset(meta_payload)
    routes: list[list[int]] = []
    seen: set[tuple[int, ...]] = set()
    for bks_path in bks_paths:
        bks_payload = load_json_from_file(bks_path)
        raw_routes = bks_payload.get("routes") if isinstance(bks_payload, dict) else None
        if not isinstance(raw_routes, list):
            continue
        for route in raw_routes:
            if not isinstance(route, list):
                continue
            converted = [int(stop) + node_offset for stop in route]
            route_key = tuple([depot_node_id, *converted, depot_node_id])
            if route_key in seen:
                continue
            seen.add(route_key)
            routes.append(converted)
    return routes


def _bks_paths_for_sidecar(output_repo: Path, meta_path: Path, metric: str) -> list[Path]:
    parts = meta_path.relative_to(output_repo / "benchmarks").parts
    if len(parts) < 7 or parts[2] != "sidecars":
        return []
    problem_type, benchmark_name, _, place_slug, size_bucket, instance_id = parts[:6]
    bks_dir = output_repo / "benchmarks" / problem_type / benchmark_name / metric / place_slug / size_bucket / instance_id
    if not bks_dir.is_dir():
        return []
    return sorted(bks_dir.glob("*.bks.*.json"))


def build_road_cache_plan(output_repo_dir: str | Path) -> dict[str, Any]:
    """Build a Julia-consumable plan for OSM-backed route-edge cache enforcement."""
    output_repo = Path(output_repo_dir)
    entries: list[dict[str, Any]] = []
    sidecar_root = output_repo / "benchmarks"
    if not sidecar_root.exists():
        return {"entries": []}

    for meta_path in sorted(sidecar_root.glob("*/Mamut2026/sidecars/*/n=*/*/*.meta.json")):
        meta_payload = load_json_from_file(meta_path)
        if not isinstance(meta_payload, dict) or not isinstance(meta_payload.get("source_osm_file"), str):
            continue
        routes_by_metric: dict[str, list[list[int]]] = {}
        for metric in ROAD_CACHE_METRICS:
            routes = _routes_from_bks_paths(meta_payload, _bks_paths_for_sidecar(output_repo, meta_path, metric))
            if routes:
                routes_by_metric[metric] = routes
        if not routes_by_metric:
            continue
        entries.append(
            {
                "meta_path": meta_path.relative_to(output_repo).as_posix(),
                "routes_by_metric": routes_by_metric,
            }
        )
    return {"entries": entries}


def enforce_full_road_cache(output_repo_dir: str | Path, *, reporter: Any | None = None) -> dict[str, Any]:
    """Fill all route-edge road-cache entries required by published Mamut2026 BKS routes.

    The implementation delegates routing to the Julia webapp helper so cache generation uses
    the same OSM graph resolution and persistence path as the interactive workbench.
    """
    output_repo = Path(output_repo_dir).resolve()
    plan = build_road_cache_plan(output_repo)
    if not plan["entries"]:
        if reporter is not None:
            reporter.phase("road-cache skipped", entries=0)
        return {"ok": True, "entries": [], "skipped": True}
    if reporter is not None:
        reporter.phase("road-cache enforcement", entries=len(plan["entries"]))
        for entry in plan["entries"]:
            reporter.phase(
                "road-cache planned sidecar",
                meta_path=entry.get("meta_path"),
                metrics=",".join(sorted(entry.get("routes_by_metric", {}).keys())),
            )

    julia = shutil.which("julia")
    if julia is None:
        raise RuntimeError("Full road-cache enforcement requires Julia on PATH.")

    webapp_dir = output_repo / "webapp"
    site_api_path = webapp_dir / "site_api.jl"
    if not site_api_path.is_file():
        raise FileNotFoundError(f"Unable to find site API helper for road-cache enforcement: {site_api_path}")

    with tempfile.TemporaryDirectory(prefix="mamut-road-cache-") as tmp_dir:
        plan_path = Path(tmp_dir) / "road-cache-plan.json"
        result_path = Path(tmp_dir) / "road-cache-result.json"
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        julia_code = f"""
using JSON3
include({json.dumps(str(site_api_path))})
repo_root = {json.dumps(str(output_repo))}
plan = JSON3.read(read({json.dumps(str(plan_path))}, String), Dict{{String,Any}})
results = Any[]
for entry in plan["entries"]
    meta_path = String(entry["meta_path"])
    metric_results = Dict{{String,Any}}()
    for (metric, routes) in entry["routes_by_metric"]
        rendered = workbench_render_routes_from_meta_path(repo_root, meta_path, routes, String(metric))
        summary = rendered["summary"]
        straight_fallback_count = Int(get(summary, "straight_fallback_count", 0))
        if straight_fallback_count != 0
            error("Road cache enforcement failed for " * meta_path * " (" * String(metric) * "): " * string(straight_fallback_count) * " segment(s) still use straight-line fallback")
        end
        metric_results[String(metric)] = summary
    end
    push!(results, Dict("meta_path" => meta_path, "metrics" => metric_results))
end
open({json.dumps(str(result_path))}, "w") do io
    JSON3.pretty(io, JSON3.write(Dict("ok" => true, "entries" => results)))
end
"""
        subprocess.run(
            [julia, f"--project={webapp_dir}", "--startup-file=no", "--quiet", "-e", julia_code],
            check=True,
            cwd=output_repo,
            text=True,
        )
        result = json.loads(result_path.read_text(encoding="utf-8"))
        if reporter is not None:
            for entry in result.get("entries", []):
                metrics = entry.get("metrics", {})
                reporter.phase(
                    "road-cache completed sidecar",
                    meta_path=entry.get("meta_path"),
                    metrics=",".join(sorted(metrics.keys())) if isinstance(metrics, dict) else None,
                )
            reporter.phase("road-cache complete", entries=len(result.get("entries", [])))
        return result
