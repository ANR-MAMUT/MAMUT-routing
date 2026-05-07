from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest

from mamut_routing_lib.enums import ObjectiveFunction
from mamut_routing_lib.json_utils import save_json_to_file
from mamut_routing_lib.models import BenchmarkBKS, BenchmarkInstance, BenchmarkInstanceCVRP
from mamut_routing_publish.site_payloads import derive_historical_taxonomy, generate_site_payloads
from mamut_routing_publish.site_webapp import generate_site_webapp


def make_generated_cvrp_instance() -> BenchmarkInstanceCVRP:
    return BenchmarkInstanceCVRP(
        instance_name="mamut-n2-cafe123",
        instance_origin="OsmCvrpGen",
        benchmark_name="Mamut2026",
        num_customers=2,
        vehicle_capacity=10,
        coordinates=[(0.0, 0.0), (1.0, 1.0), (2.0, 2.0)],
        demands=[0, 1, 2],
        depot=0,
        arc_costs=[[0, 1, 2], [1, 0, 3], [2, 3, 0]],
        metadata={
            "authors": "Florian Rascoussier (0nyr) and Adrien Pichon (Anzury)",
            "generated_at": "2026-04-23T10:00:00",
            "problem_type": "CVRP",
            "metric_variant": "fastest",
            "place_slug": "brest",
            "source_base_name": "brest_poi-n3-k2",
            "source_city": "Brest",
            "source_seed": 123,
            "source_folder": "instances_v2/osm/brest/n3",
            "num_vehicles_lb": 2,
            "generator_version": "fixture",
            "artifact_paths": {
                "vrp_json": "benchmarks/CVRP/Mamut2026/fastest/brest/n=2/mamut-n2-cafe123/mamut-n2-cafe123.vrp.json",
                "vrp": "benchmarks/CVRP/Mamut2026/fastest/brest/n=2/mamut-n2-cafe123/mamut-n2-cafe123.vrp",
                "meta": "benchmarks/CVRP/Mamut2026/sidecars/brest/n=2/mamut-n2-cafe123/mamut-n2-cafe123.meta.json",
                "manifest": "benchmarks/CVRP/Mamut2026/sidecars/brest/n=2/mamut-n2-cafe123/mamut-n2-cafe123.manifest.json",
            },
            "sibling_variant_paths": {
                "euclidean": "benchmarks/CVRP/Mamut2026/euclidean/brest/n=2/mamut-n2-cafe123/mamut-n2-cafe123.vrp.json"
            },
            "derived_problem_paths": {
                "fastest": "benchmarks/VRPTW/Mamut2026/fastest/brest/n=2/mamut-n2-beef456/mamut-n2-beef456.vrp.json"
            },
            "source_problem_paths": {},
        },
    )


def make_generated_vrptw_instance() -> BenchmarkInstance:
    return BenchmarkInstance(
        instance_name="mamut-n2-beef456",
        instance_origin="OsmCvrpGen",
        benchmark_name="Mamut2026",
        num_customers=2,
        vehicle_capacity=10,
        coordinates=[(0.0, 0.0), (1.0, 1.0), (2.0, 2.0)],
        demands=[0, 1, 2],
        service_times=[0, 10, 10],
        time_windows=[(0, 1000), (10, 500), (10, 500)],
        depot=0,
        arc_costs=[[0, 1, 2], [1, 0, 3], [2, 3, 0]],
        metadata={
            "authors": "Florian Rascoussier (0nyr) and Adrien Pichon (Anzury)",
            "generated_at": "2026-04-23T10:00:00",
            "problem_type": "VRPTW",
            "metric_variant": "fastest",
            "place_slug": "brest",
            "source_base_name": "brest_poi-n3-k2",
            "source_city": "Brest",
            "source_seed": 123,
            "source_folder": "instances_v2/osm/brest/n3",
            "num_vehicles_lb": 2,
            "generator_version": "fixture",
            "artifact_paths": {
                "vrp_json": "benchmarks/VRPTW/Mamut2026/fastest/brest/n=2/mamut-n2-beef456/mamut-n2-beef456.vrp.json",
                "vrp": "benchmarks/VRPTW/Mamut2026/fastest/brest/n=2/mamut-n2-beef456/mamut-n2-beef456.vrp",
                "meta": "benchmarks/VRPTW/Mamut2026/sidecars/brest/n=2/mamut-n2-beef456/mamut-n2-beef456.meta.json",
                "manifest": "benchmarks/VRPTW/Mamut2026/sidecars/brest/n=2/mamut-n2-beef456/mamut-n2-beef456.manifest.json",
            },
            "sibling_variant_paths": {
                "euclidean": "benchmarks/VRPTW/Mamut2026/euclidean/brest/n=2/mamut-n2-beef456/mamut-n2-beef456.vrp.json"
            },
            "derived_problem_paths": {},
            "source_problem_paths": {
                "cvrp_vrp_json": "benchmarks/CVRP/Mamut2026/fastest/brest/n=2/mamut-n2-cafe123/mamut-n2-cafe123.vrp.json"
            },
        },
    )


def make_historical_instance() -> BenchmarkInstance:
    return BenchmarkInstance(
        instance_name="C101",
        instance_origin="Solomon1987",
        benchmark_name="Sintef2008",
        num_customers=2,
        num_vehicles=2,
        vehicle_capacity=10,
        coordinates=[(0, 0), (1, 1), (2, 2)],
        demands=[0, 1, 2],
        service_times=[0, 10, 10],
        time_windows=[(0, 100), (0, 100), (0, 100)],
        depot=0,
        arc_costs=[[0, 1, 2], [1, 0, 3], [2, 3, 0]],
    )


def make_bks(instance_name: str, objective_function: ObjectiveFunction, method: str) -> BenchmarkBKS:
    return BenchmarkBKS(
        instance_name=instance_name,
        objective_function=objective_function,
        routes=[[1, 2]],
        cost=12,
        metadata={
            "authors": "Florian Rascoussier (0nyr) and Adrien Pichon (Anzury)",
            "source": "fixture",
            "method": method,
            "validated_num_routes": 1,
        },
    )


def write_json(path: Path, payload: dict) -> None:
    save_json_to_file(payload, path)


def build_fixture_site_inputs(output_repo_dir: Path) -> tuple[BenchmarkInstanceCVRP, BenchmarkInstance]:
    generated_cvrp = make_generated_cvrp_instance()
    generated_vrptw = make_generated_vrptw_instance()
    historical = make_historical_instance()

    generated_cvrp_path = (
        output_repo_dir
        / "benchmarks"
        / "CVRP"
        / "Mamut2026"
        / "fastest"
        / "brest"
        / "n=2"
        / generated_cvrp.instance_name
        / f"{generated_cvrp.instance_name}.vrp.json"
    )
    generated_vrptw_path = (
        output_repo_dir
        / "benchmarks"
        / "VRPTW"
        / "Mamut2026"
        / "fastest"
        / "brest"
        / "n=2"
        / generated_vrptw.instance_name
        / f"{generated_vrptw.instance_name}.vrp.json"
    )
    historical_path = (
        output_repo_dir
        / "benchmarks"
        / "VRPTW"
        / "Sintef2008"
        / "n=2"
        / "C101.vrp.json"
    )

    write_json(generated_cvrp_path, generated_cvrp.model_dump(mode="json"))
    write_json(generated_vrptw_path, generated_vrptw.model_dump(mode="json"))
    write_json(historical_path, historical.model_dump(mode="json"))

    (generated_cvrp_path.with_suffix("")).write_text("NAME : fixture\n", encoding="utf-8")
    (generated_vrptw_path.with_suffix("")).write_text("NAME : fixture\n", encoding="utf-8")
    write_json(
        output_repo_dir
        / "benchmarks"
        / "CVRP"
        / "Mamut2026"
        / "sidecars"
        / "brest"
        / "n=2"
        / generated_cvrp.instance_name
        / f"{generated_cvrp.instance_name}.meta.json",
        {"instance_id": generated_cvrp.instance_name},
    )
    write_json(
        output_repo_dir
        / "benchmarks"
        / "CVRP"
        / "Mamut2026"
        / "sidecars"
        / "brest"
        / "n=2"
        / generated_cvrp.instance_name
        / f"{generated_cvrp.instance_name}.manifest.json",
        {"instance_id": generated_cvrp.instance_name},
    )
    write_json(
        output_repo_dir
        / "benchmarks"
        / "VRPTW"
        / "Mamut2026"
        / "sidecars"
        / "brest"
        / "n=2"
        / generated_vrptw.instance_name
        / f"{generated_vrptw.instance_name}.meta.json",
        {"instance_id": generated_vrptw.instance_name},
    )
    write_json(
        output_repo_dir
        / "benchmarks"
        / "VRPTW"
        / "Mamut2026"
        / "sidecars"
        / "brest"
        / "n=2"
        / generated_vrptw.instance_name
        / f"{generated_vrptw.instance_name}.manifest.json",
        {"instance_id": generated_vrptw.instance_name},
    )

    write_json(
        generated_cvrp_path.with_name(f"{generated_cvrp.instance_name}.bks.MonoCost.json"),
        make_bks(generated_cvrp.instance_name, ObjectiveFunction.MONO_COST, "hgs-v1").model_dump(mode="json"),
    )
    write_json(
        generated_vrptw_path.with_name(f"{generated_vrptw.instance_name}.bks.HierarchicalVehicleCost.json"),
        make_bks(generated_vrptw.instance_name, ObjectiveFunction.HIERARCHICAL_VEHICLE_COST, "hgs-v3").model_dump(
            mode="json"
        ),
    )
    write_json(
        generated_vrptw_path.with_name(f"{generated_vrptw.instance_name}.bks.MonoCost.json"),
        make_bks(generated_vrptw.instance_name, ObjectiveFunction.MONO_COST, "hgs-v3").model_dump(mode="json"),
    )
    write_json(
        historical_path.with_name("C101.bks.HierarchicalVehicleCost.json"),
        make_bks("C101", ObjectiveFunction.HIERARCHICAL_VEHICLE_COST, "fixture-historical").model_dump(mode="json"),
    )

    return generated_cvrp, generated_vrptw


def probe_julia_site_payload_types(output_repo_dir: Path, snapshot_id: str, instance_id: str) -> dict[str, str]:
    julia_executable = shutil.which("julia")
    if julia_executable is None:
        pytest.skip("Julia executable is not available on PATH")

    loader_path = Path(__file__).resolve().parents[1] / "webapp" / "io-json-vrp.jl"
    site_output = output_repo_dir / "dist"
    payload_root = site_output / "site-payloads"
    payload_paths = [
        ("home", payload_root / "index.json"),
        ("snapshot", site_output / "site" / "snapshot.json"),
        ("history", site_output / "site" / "history.json"),
        ("benchmarks", payload_root / "benchmarks" / "index.json"),
        ("project", payload_root / "project" / "index.json"),
        ("objectives", payload_root / "objectives" / "index.json"),
        ("problem", payload_root / "benchmarks" / "vrptw" / "index.json"),
        ("family", payload_root / "benchmarks" / "vrptw" / "sintef2008" / "index.json"),
        ("variant", payload_root / "benchmarks" / "vrptw" / "mamut2026" / "fastest" / "index.json"),
        ("place", payload_root / "benchmarks" / "vrptw" / "mamut2026" / "fastest" / "brest" / "index.json"),
        (
            "size",
            payload_root / "benchmarks" / "vrptw" / "mamut2026" / "fastest" / "brest" / "n=2" / "index.json",
        ),
        ("history_detail", payload_root / "history" / snapshot_id / "index.json"),
        (
            "instance",
            payload_root
            / "benchmarks"
            / "vrptw"
            / "mamut2026"
            / "fastest"
            / "brest"
            / "n=2"
            / instance_id
            / "index.json",
        ),
    ]

    checks_literal = ",\n        ".join(
        f"({json.dumps(name)}, {json.dumps(str(path))})" for name, path in payload_paths
    )
    julia_code = f"""
include({json.dumps(str(loader_path))})
checks = [
        {checks_literal}
]
for (name, path) in checks
    println(name * "\\t" * string(typeof(load_json_site_payload(path))))
end
"""
    result = subprocess.run(
        [julia_executable, "--startup-file=no", "--quiet", "-e", julia_code],
        check=True,
        capture_output=True,
        text=True,
    )
    return dict(line.split("\t", 1) for line in result.stdout.splitlines() if line.strip())


def probe_julia_site_api_routes(output_repo_dir: Path, snapshot_id: str, instance_id: str) -> dict[str, dict[str, str]]:
    julia_executable = shutil.which("julia")
    if julia_executable is None:
        pytest.skip("Julia executable is not available on PATH")

    api_path = Path(__file__).resolve().parents[1] / "webapp" / "site_api.jl"
    checks = [
        ("home", "/", "/api/site-payload"),
        ("project", "/project/", "/api/site-payload/project"),
        ("problem", "benchmarks/vrptw", "/api/site-payload?route=benchmarks%2Fvrptw"),
        (
            "instance",
            f"/benchmarks/vrptw/mamut2026/fastest/brest/n=2/{instance_id}/",
            f"/api/site-payload/benchmarks/vrptw/mamut2026/fastest/brest/n=2/{instance_id}",
        ),
        (
            "history_detail",
            f"/history/{snapshot_id}/",
            f"/api/site-payload/history/{snapshot_id}",
        ),
    ]
    checks_literal = ",\n        ".join(
        f"({json.dumps(name)}, {json.dumps(route)}, {json.dumps(target)})" for name, route, target in checks
    )
    julia_code = f"""
include({json.dumps(str(api_path))})
checks = [
        {checks_literal}
]
for (name, route, target) in checks
    summary = site_payload_summary({json.dumps(str(output_repo_dir))}, route)
    extracted = extract_site_payload_route(target)
    rendered = render_site_payload_json({json.dumps(str(output_repo_dir))}, route)
    has_kind = occursin("\\\"payload_kind\\\": \\\"" * summary.payload_kind * "\\\"", rendered)
    println(name * "\\t" * summary.model_type * "\\t" * summary.payload_kind * "\\t" * summary.route_path * "\\t" * extracted * "\\t" * string(has_kind))
end
"""
    result = subprocess.run(
        [julia_executable, "--startup-file=no", "--quiet", "-e", julia_code],
        check=True,
        capture_output=True,
        text=True,
    )

    parsed: dict[str, dict[str, str]] = {}
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        name, model_type, payload_kind, route_path, extracted_route, has_kind = line.split("\t")
        parsed[name] = {
            "model_type": model_type,
            "payload_kind": payload_kind,
            "route_path": route_path,
            "extracted_route": extracted_route,
            "has_kind": has_kind,
        }
    return parsed


def probe_julia_site_static_routes(output_repo_dir: Path, instance_id: str) -> dict[str, dict[str, str]]:
    julia_executable = shutil.which("julia")
    if julia_executable is None:
        pytest.skip("Julia executable is not available on PATH")

    api_path = Path(__file__).resolve().parents[1] / "webapp" / "site_api.jl"
    checks = [
        ("root_html", "/", 'data-payload-mode="static"'),
        ("problem_html", "/benchmarks/vrptw/", "<title>MAMUT-routing</title>"),
        ("site_js", "/webapp/site.js", "payloadUrlForRoute"),
        ("favicon", "/webapp/icons/favicon.svg", 'sodipodi:docname="favicon.svg"'),
        ("home_json", "/site-payloads/index.json", '"payload_kind": "home_page"'),
        (
            "artifact_json",
            f"/benchmarks/VRPTW/Mamut2026/fastest/brest/n=2/{instance_id}/{instance_id}.vrp.json",
            f'"instance_name": "{instance_id}"',
        ),
        (
            "artifact_vrp",
            f"/benchmarks/VRPTW/Mamut2026/fastest/brest/n=2/{instance_id}/{instance_id}.vrp",
            "NAME : fixture",
        ),
    ]
    checks_literal = ",\n        ".join(
        f"({json.dumps(name)}, {json.dumps(target)}, {json.dumps(snippet)})" for name, target, snippet in checks
    )
    julia_code = f"""
include({json.dumps(str(api_path))})
checks = [
        {checks_literal}
]
for (name, target, snippet) in checks
    resolved = read_site_public_file({json.dumps(str(output_repo_dir))}, target)
    has_snippet = occursin(snippet, String(resolved.body))
    println(name * "\\t" * resolved.request_path * "\\t" * resolved.relative_path * "\\t" * resolved.content_type * "\\t" * string(has_snippet))
end
"""
    result = subprocess.run(
        [julia_executable, "--startup-file=no", "--quiet", "-e", julia_code],
        check=True,
        capture_output=True,
        text=True,
    )

    parsed: dict[str, dict[str, str]] = {}
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        name, request_path, relative_path, content_type, has_snippet = line.split("\t")
        parsed[name] = {
            "request_path": request_path,
            "relative_path": relative_path,
            "content_type": content_type,
            "has_snippet": has_snippet,
        }
    return parsed


def probe_julia_site_api_cli_help() -> str:
    julia_executable = shutil.which("julia")
    if julia_executable is None:
        pytest.skip("Julia executable is not available on PATH")

    runner_path = Path(__file__).resolve().parents[1] / "webapp" / "run_site_api.jl"
    project_path = runner_path.parent
    result = subprocess.run(
        [julia_executable, "--startup-file=no", f"--project={project_path}", str(runner_path), "--help"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def probe_julia_workbench_generation_helpers(repo_root: Path, sample_root: Path) -> dict[str, object]:
    julia_executable = shutil.which("julia")
    if julia_executable is None:
        pytest.skip("Julia executable is not available on PATH")

    api_path = Path(__file__).resolve().parents[1] / "webapp" / "site_api.jl"
    julia_code = f"""
include({json.dumps(str(api_path))})
workbench_ensure_local_osm_for_city!({json.dumps(str(repo_root))}, "London")
cities = workbench_generation_cities_payload({json.dumps(str(repo_root))}; sample_root={json.dumps(str(sample_root))})
preview = workbench_generation_preview_payload(
    {json.dumps(str(repo_root))},
    Dict("city" => "london", "method" => "hybrid", "nCustomers" => 90);
    sample_root={json.dumps(str(sample_root))},
)
london_entry = only(filter(city -> city["slug"] == "london", cities["cities"]))
summary = Dict(
    "city_count" => length(cities["cities"]),
    "preview_available" => cities["preview_available"],
    "city_slugs" => [city["slug"] for city in cities["cities"]],
    "london_counts" => london_entry["customer_counts"],
    "preview_feature_count" => length(preview["geojson"]["features"]),
    "preview_mode" => preview["summary"]["preview_mode"],
    "preview_city" => preview["summary"]["city"],
    "preview_method" => preview["summary"]["method"],
    "sample_method" => preview["summary"]["sample_method"],
    "sample_size_dir" => preview["summary"]["sample_size_dir"],
)
println(custom_json_encode(summary; indent=2, sort_keys=true))
"""
    result = subprocess.run(
        [julia_executable, "--startup-file=no", "--quiet", "-e", julia_code],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def probe_julia_workbench_render_routes_helper() -> dict[str, object]:
    julia_executable = shutil.which("julia")
    if julia_executable is None:
        pytest.skip("Julia executable is not available on PATH")

    api_path = Path(__file__).resolve().parents[1] / "webapp" / "site_api.jl"
    julia_code = f"""
include({json.dumps(str(api_path))})
cached = workbench_render_routes_payload(Dict(
    "meta" => Dict(
        "depot_instance_node_id" => 1,
        "nodes" => Any[
            Dict("instance_node_id" => 1, "graph_vertex_id" => 10, "demand" => 0, "poi_lon" => 0.0, "poi_lat" => 0.0),
            Dict("instance_node_id" => 2, "graph_vertex_id" => 20, "demand" => 4, "poi_lon" => 1.0, "poi_lat" => 0.0),
        ],
        "road_cache" => Dict(
            "shortest" => Dict(
                "10_20" => Any[[0.0, 0.0], [0.5, 0.25], [1.0, 0.0]],
                "20_10" => Any[[1.0, 0.0], [0.5, -0.25], [0.0, 0.0]],
            ),
        ),
    ),
    "solText" => "Route #1: 2",
    "metric" => "shortest",
))
fallback = workbench_render_routes_payload(Dict(
    "meta" => Dict(
        "depot_instance_node_id" => 1,
        "nodes" => Any[
            Dict("instance_node_id" => 1, "graph_vertex_id" => 10, "demand" => 0, "poi_lon" => 0.0, "poi_lat" => 0.0),
            Dict("instance_node_id" => 2, "graph_vertex_id" => 20, "demand" => 4, "poi_lon" => 1.0, "poi_lat" => 0.0),
        ],
    ),
    "routes" => Any[Any[2]],
    "metric" => "shortest",
))
cache_only_repo = mktempdir()
cache_only_meta_path = joinpath(cache_only_repo, "cached.meta.json")
save_json_to_file(Dict(
    "depot_instance_node_id" => 1,
    "source_osm_file" => "does-not-exist.osm",
    "nodes" => Any[
        Dict("instance_node_id" => 1, "graph_vertex_id" => 10, "demand" => 0, "poi_lon" => 0.0, "poi_lat" => 0.0),
        Dict("instance_node_id" => 2, "graph_vertex_id" => 20, "demand" => 4, "poi_lon" => 1.0, "poi_lat" => 0.0),
    ],
    "road_cache" => Dict(
        "fastest" => Dict(
            "node:1_2" => Any[[0.0, 0.0], [0.5, 0.25], [1.0, 0.0]],
            "node:2_1" => Any[[1.0, 0.0], [0.5, -0.25], [0.0, 0.0]],
        ),
    ),
), cache_only_meta_path; indent=2, sort_keys=true)
cache_only = workbench_render_routes_from_meta_path(cache_only_repo, "cached.meta.json", Any[Any[2]], "fastest")
summary = Dict(
    "cached_render_mode" => cached["summary"]["render_mode"],
    "cached_used_cache" => cached["summary"]["used_cache"],
    "cached_cache_miss_count" => cached["summary"]["cache_miss_count"],
    "cached_feature_count" => length(cached["geojson"]["features"]),
    "cached_coordinate_count" => length(cached["geojson"]["features"][1]["geometry"]["coordinates"]),
    "cached_route_load" => cached["geojson"]["features"][1]["properties"]["load"],
    "fallback_render_mode" => fallback["summary"]["render_mode"],
    "fallback_used_cache" => fallback["summary"]["used_cache"],
    "fallback_cache_miss_count" => fallback["summary"]["cache_miss_count"],
    "fallback_feature_count" => length(fallback["geojson"]["features"]),
    "fallback_coordinate_count" => length(fallback["geojson"]["features"][1]["geometry"]["coordinates"]),
    "fallback_route_load" => fallback["geojson"]["features"][1]["properties"]["load"],
    "cache_only_render_mode" => cache_only["summary"]["render_mode"],
    "cache_only_cache_miss_count" => cache_only["summary"]["cache_miss_count"],
    "cache_only_straight_fallback_count" => cache_only["summary"]["straight_fallback_count"],
    "cache_only_cache_persisted" => cache_only["summary"]["cache_persisted"],
    "cache_only_coordinate_count" => length(cache_only["geojson"]["features"][1]["geometry"]["coordinates"]),
)
println(custom_json_encode(summary; indent=2, sort_keys=true))
"""
    result = subprocess.run(
        [julia_executable, "--startup-file=no", "--quiet", "-e", julia_code],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_derive_historical_taxonomy_supports_solomon_and_gehring_homberger_names() -> None:
    assert derive_historical_taxonomy("C101") == ("C", "1")
    assert derive_historical_taxonomy("RC208") == ("RC", "2")
    assert derive_historical_taxonomy("C1_4_1") == ("C", "1")
    assert derive_historical_taxonomy("R2_2_10") == ("R", "2")


def test_generate_site_payloads_writes_problem_catalogs_instance_pages_and_history(tmp_path: Path) -> None:
    output_repo_dir = tmp_path / "MAMUT-routing"

    generated_cvrp, generated_vrptw = build_fixture_site_inputs(output_repo_dir)

    summary = generate_site_payloads(
        output_repo_dir=output_repo_dir,
        source_commit="abcdef123456",
        published_at="2026-04-23T12:00:00",
        snapshot_id="2026-04-23-abcdef1",
        history_summary="Fixture publication.",
    )

    assert summary.snapshot_id == "2026-04-23-abcdef1"
    assert summary.payload_files_written > 0

    site_output = output_repo_dir / "dist"
    payload_root = site_output / "site-payloads"

    home_payload = json.loads((payload_root / "index.json").read_text(encoding="utf-8"))
    assert home_payload["payload_kind"] == "home_page"
    assert [problem["problem_type"] for problem in home_payload["problems"]] == ["CVRP", "VRPTW"]

    root_index = json.loads((payload_root / "benchmarks" / "index.json").read_text(encoding="utf-8"))
    assert root_index["payload_kind"] == "benchmarks_index"
    assert root_index["breadcrumbs"] == [{"label": "Benchmarks", "route_path": "/benchmarks/"}]
    assert [problem["problem_type"] for problem in root_index["problems"]] == ["CVRP", "VRPTW"]
    assert not (output_repo_dir / "benchmarks" / "vrptw" / "index.json").exists()

    objectives_payload = json.loads((payload_root / "objectives" / "index.json").read_text(encoding="utf-8"))
    assert objectives_payload["payload_kind"] == "objectives_page"
    assert objectives_payload["breadcrumbs"] == []
    assert [entry["objective_function"] for entry in objectives_payload["explainers"]] == [
        "HierarchicalVehicleCost",
        "MonoCost",
    ]

    project_payload = json.loads((payload_root / "project" / "index.json").read_text(encoding="utf-8"))
    assert project_payload["payload_kind"] == "project_page"
    assert project_payload["breadcrumbs"] == []
    assert project_payload["anr_project_code"] == "ANR-22-CE22-0016"
    assert project_payload["anr_project_url"] == "https://anr.fr/Projet-ANR-22-CE22-0016"
    assert [thread["title"] for thread in project_payload["research_threads"]] == [
        "Shared project frame",
        "Onyr's benchmark thread",
        "A. Pichon's instance-generation thread",
    ]

    historical_instance_page = json.loads(
        (payload_root / "benchmarks" / "vrptw" / "sintef2008" / "n=2" / "C101" / "index.json").read_text(encoding="utf-8")
    )
    assert historical_instance_page["summary"]["historical_topology_type"] == "C"
    assert historical_instance_page["summary"]["historical_tw_type"] == "1"

    vrptw_instance_page = json.loads(
        (
            payload_root
            / "benchmarks"
            / "vrptw"
            / "mamut2026"
            / "fastest"
            / "brest"
            / "n=2"
            / generated_vrptw.instance_name
            / "index.json"
        ).read_text(encoding="utf-8")
    )
    assert [entry["objective_function"] for entry in vrptw_instance_page["bks_entries"]] == [
        "HierarchicalVehicleCost",
        "MonoCost",
    ]
    assert vrptw_instance_page["source_problem_routes"]["cvrp_vrp_json"] == "/benchmarks/cvrp/mamut2026/fastest/brest/n=2/mamut-n2-cafe123/"

    history_payload = json.loads((site_output / "site" / "history.json").read_text(encoding="utf-8"))
    assert history_payload["current_snapshot_id"] == "2026-04-23-abcdef1"
    assert history_payload["entries"][0]["snapshot"]["source_commit"] == "abcdef123456"

    history_detail_payload = json.loads(
        (payload_root / "history" / "2026-04-23-abcdef1" / "index.json").read_text(encoding="utf-8")
    )
    assert history_detail_payload["payload_kind"] == "history_detail"
    assert history_detail_payload["affected_objective_functions"] == ["HierarchicalVehicleCost", "MonoCost"]

    webapp_summary = generate_site_webapp(output_repo_dir)
    assert webapp_summary.asset_files_written == 14
    assert webapp_summary.html_files_written > 0
    assert (site_output / "index.html").exists()
    assert (site_output / "benchmarks" / "index.html").exists()
    assert (site_output / "project" / "index.html").exists()
    assert not (output_repo_dir / "index.html").exists()
    assert not (output_repo_dir / "site").exists()
    assert not (output_repo_dir / "benchmarks" / "vrptw" / "index.json").exists()
    assert (site_output / "history" / "index.html").exists()
    assert (site_output / "workbench" / "index.html").exists()
    assert (
        site_output
        / "benchmarks"
        / "vrptw"
        / "mamut2026"
        / "fastest"
        / "brest"
        / "n=2"
        / generated_vrptw.instance_name
        / "index.html"
    ).exists()
    assert (site_output / "webapp" / "site.css").exists()
    assert (site_output / "webapp" / "site.js").exists()
    assert (site_output / "webapp" / "workbench.css").exists()
    assert (site_output / "webapp" / "workbench.js").exists()

    root_html = (site_output / "index.html").read_text(encoding="utf-8")
    assert 'data-payload-mode="static"' in root_html
    assert 'data-payload-api-prefix="/api/site-payload"' in root_html
    assert 'data-payload-static-root="/site-payloads"' in root_html
    assert 'webapp/site.js' in root_html
    assert 'rel="icon" type="image/svg+xml"' in root_html
    assert 'webapp/icons/favicon.svg' in root_html
    assert "Project" in root_html
    assert 'id="pageTitle"' not in root_html
    assert 'id="pageIntro"' not in root_html

    workbench_html = (site_output / "workbench" / "index.html").read_text(encoding="utf-8")
    assert 'data-page-kind="workbench-app"' in workbench_html
    assert 'data-workbench-mode="catalog"' in workbench_html
    assert 'webapp/workbench.css' in workbench_html
    assert 'webapp/workbench.js' in workbench_html
    assert '../webapp/icons/favicon.svg' in workbench_html
    assert 'webapp/site.js' not in workbench_html
    assert 'id="tabVisualize"' in workbench_html
    assert 'id="tabGenerate"' in workbench_html
    assert 'id="benchmarkCatalogSelect"' in workbench_html
    assert 'id="map"' in workbench_html
    assert 'id="benchmarkInstanceSelect"' in workbench_html
    assert 'id="benchmarkObjectiveSelect"' in workbench_html
    assert 'id="pageTitle"' not in workbench_html
    assert 'id="pageIntro"' not in workbench_html
    assert not (site_output / "workbench" / "derive" / "index.html").exists()

    site_js = (site_output / "webapp" / "site.js").read_text(encoding="utf-8")
    workbench_js = (site_output / "webapp" / "workbench.js").read_text(encoding="utf-8")
    assert "Open Derive Mode" not in site_js
    assert "deriveBenchmarkBtn" not in workbench_js
    assert "projectCoordinates(routeLine.coordinates, width, height, projectionBounds)" in site_js
    assert "supportsWorkbenchInstance(item)" in site_js
    assert "supportsWorkbenchInstance(payload.summary)" in site_js
    assert 'id="benchmarkCatalogSelect"' not in site_js
    assert vrptw_instance_page["summary"]["place_slug"] == "brest"
    assert historical_instance_page["summary"]["place_slug"] is None

    api_webapp_summary = generate_site_webapp(output_repo_dir, payload_mode="api")
    assert api_webapp_summary.html_files_written == webapp_summary.html_files_written
    root_html_api = (site_output / "index.html").read_text(encoding="utf-8")
    assert 'data-payload-mode="api"' in root_html_api
    assert 'data-payload-api-prefix="/api/site-payload"' in root_html_api
    assert 'data-payload-static-root="/site-payloads"' in root_html_api


def test_generate_site_payloads_accepts_legacy_history_without_change_counts(tmp_path: Path) -> None:
    output_repo_dir = tmp_path / "MAMUT-routing"
    build_fixture_site_inputs(output_repo_dir)

    legacy_snapshot = {
        "snapshot_id": "2026-04-22-legacy",
        "published_at": "2026-04-22T12:00:00",
        "source_commit": "legacycommit",
        "source_branch": "main",
    }
    save_json_to_file(
        {
            "payload_kind": "site_history",
            "schema_version": "1.0.0",
            "generated_at": "2026-04-22T12:00:00",
            "snapshot": legacy_snapshot,
            "current_snapshot_id": legacy_snapshot["snapshot_id"],
            "entries": [
                {
                    "snapshot": legacy_snapshot,
                    "summary": "Legacy history entry before change counts.",
                    "detail_route_path": "/history/2026-04-22-legacy/",
                    "affected_problem_types": ["CVRP"],
                    "affected_benchmark_names": ["Mamut2026"],
                    "affected_objective_functions": ["MonoCost"],
                }
            ],
        },
        output_repo_dir / "dist" / "site" / "history.json",
    )

    generate_site_payloads(
        output_repo_dir=output_repo_dir,
        source_commit="abcdef123456",
        published_at="2026-04-23T12:00:00",
        snapshot_id="2026-04-23-abcdef1",
    )

    ledger = json.loads((output_repo_dir / "dist" / "site" / "history.json").read_text(encoding="utf-8"))
    assert ledger["entries"][0]["snapshot"]["snapshot_id"] == "2026-04-23-abcdef1"
    assert ledger["entries"][1]["snapshot"]["snapshot_id"] == "2026-04-22-legacy"
    assert ledger["entries"][1]["change_counts"] == {
        "families_added": 0,
        "families_removed": 0,
        "instances_added": 0,
        "instances_removed": 0,
        "bks_added": 0,
        "bks_removed": 0,
        "bks_improved": 0,
        "bks_regressed": 0,
    }


def test_julia_loader_parses_generated_site_payloads_as_typed_models(tmp_path: Path) -> None:
    output_repo_dir = tmp_path / "MAMUT-routing"
    _, generated_vrptw = build_fixture_site_inputs(output_repo_dir)
    generate_site_payloads(
        output_repo_dir=output_repo_dir,
        source_commit="abcdef123456",
        published_at="2026-04-23T12:00:00",
        snapshot_id="2026-04-23-abcdef1",
        history_summary="Fixture publication.",
    )

    parsed_types = probe_julia_site_payload_types(
        output_repo_dir=output_repo_dir,
        snapshot_id="2026-04-23-abcdef1",
        instance_id=generated_vrptw.instance_name,
    )

    assert parsed_types == {
        "home": "HomePagePayload",
        "snapshot": "SiteSnapshotManifest",
        "history": "SiteHistoryLedger",
        "benchmarks": "BenchmarksIndexPayload",
        "project": "ProjectPagePayload",
        "objectives": "ObjectivesPagePayload",
        "problem": "ProblemIndexPayload",
        "family": "CatalogIndexPayload",
        "variant": "CatalogIndexPayload",
        "place": "CatalogIndexPayload",
        "size": "CatalogIndexPayload",
        "history_detail": "HistoryDetailPayload",
        "instance": "InstancePagePayload",
    }


def test_julia_site_api_resolves_routes_and_renders_payload_json(tmp_path: Path) -> None:
    output_repo_dir = tmp_path / "MAMUT-routing"
    _, generated_vrptw = build_fixture_site_inputs(output_repo_dir)
    generate_site_payloads(
        output_repo_dir=output_repo_dir,
        source_commit="abcdef123456",
        published_at="2026-04-23T12:00:00",
        snapshot_id="2026-04-23-abcdef1",
        history_summary="Fixture publication.",
    )

    route_info = probe_julia_site_api_routes(
        output_repo_dir=output_repo_dir,
        snapshot_id="2026-04-23-abcdef1",
        instance_id=generated_vrptw.instance_name,
    )

    assert route_info == {
        "home": {
            "model_type": "HomePagePayload",
            "payload_kind": "home_page",
            "route_path": "/",
            "extracted_route": "/",
            "has_kind": "true",
        },
        "project": {
            "model_type": "ProjectPagePayload",
            "payload_kind": "project_page",
            "route_path": "/project/",
            "extracted_route": "/project/",
            "has_kind": "true",
        },
        "problem": {
            "model_type": "ProblemIndexPayload",
            "payload_kind": "problem_index",
            "route_path": "/benchmarks/vrptw/",
            "extracted_route": "/benchmarks/vrptw/",
            "has_kind": "true",
        },
        "instance": {
            "model_type": "InstancePagePayload",
            "payload_kind": "instance_page",
            "route_path": f"/benchmarks/vrptw/mamut2026/fastest/brest/n=2/{generated_vrptw.instance_name}/",
            "extracted_route": f"/benchmarks/vrptw/mamut2026/fastest/brest/n=2/{generated_vrptw.instance_name}/",
            "has_kind": "true",
        },
        "history_detail": {
            "model_type": "HistoryDetailPayload",
            "payload_kind": "history_detail",
            "route_path": "/history/2026-04-23-abcdef1/",
            "extracted_route": "/history/2026-04-23-abcdef1/",
            "has_kind": "true",
        },
    }


def test_julia_site_api_serves_static_site_files_and_artifacts(tmp_path: Path) -> None:
    output_repo_dir = tmp_path / "MAMUT-routing"
    _, generated_vrptw = build_fixture_site_inputs(output_repo_dir)
    generate_site_payloads(
        output_repo_dir=output_repo_dir,
        source_commit="abcdef123456",
        published_at="2026-04-23T12:00:00",
        snapshot_id="2026-04-23-abcdef1",
        history_summary="Fixture publication.",
    )
    generate_site_webapp(output_repo_dir, payload_mode="static")

    static_info = probe_julia_site_static_routes(output_repo_dir=output_repo_dir, instance_id=generated_vrptw.instance_name)

    assert static_info == {
        "root_html": {
            "request_path": "/",
            "relative_path": "dist/index.html",
            "content_type": "text/html; charset=utf-8",
            "has_snippet": "true",
        },
        "problem_html": {
            "request_path": "/benchmarks/vrptw/",
            "relative_path": "dist/benchmarks/vrptw/index.html",
            "content_type": "text/html; charset=utf-8",
            "has_snippet": "true",
        },
        "site_js": {
            "request_path": "/webapp/site.js",
            "relative_path": "dist/webapp/site.js",
            "content_type": "text/javascript; charset=utf-8",
            "has_snippet": "true",
        },
        "favicon": {
            "request_path": "/webapp/icons/favicon.svg",
            "relative_path": "dist/webapp/icons/favicon.svg",
            "content_type": "image/svg+xml",
            "has_snippet": "true",
        },
        "home_json": {
            "request_path": "/site-payloads/index.json",
            "relative_path": "dist/site-payloads/index.json",
            "content_type": "application/json; charset=utf-8",
            "has_snippet": "true",
        },
        "artifact_json": {
            "request_path": f"/benchmarks/VRPTW/Mamut2026/fastest/brest/n=2/{generated_vrptw.instance_name}/{generated_vrptw.instance_name}.vrp.json",
            "relative_path": f"benchmarks/VRPTW/Mamut2026/fastest/brest/n=2/{generated_vrptw.instance_name}/{generated_vrptw.instance_name}.vrp.json",
            "content_type": "application/json; charset=utf-8",
            "has_snippet": "true",
        },
        "artifact_vrp": {
            "request_path": f"/benchmarks/VRPTW/Mamut2026/fastest/brest/n=2/{generated_vrptw.instance_name}/{generated_vrptw.instance_name}.vrp",
            "relative_path": f"benchmarks/VRPTW/Mamut2026/fastest/brest/n=2/{generated_vrptw.instance_name}/{generated_vrptw.instance_name}.vrp",
            "content_type": "text/plain; charset=utf-8",
            "has_snippet": "true",
        },
    }


def test_julia_site_api_cli_runner_prints_help() -> None:
    help_output = probe_julia_site_api_cli_help()
    assert "Usage: julia --project=webapp webapp/run_site_api.jl [options]" in help_output
    assert "--repo-root PATH" in help_output
    assert "--api-prefix PREFIX" in help_output


def test_julia_site_api_builds_catalog_backed_workbench_generation_preview() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    # OSM samples live in the parent VRPTW-benchmarks repo when MAMUT-routing is
    # checked out as a submodule; absent in standalone clones.
    sample_root = repo_root.parents[2] / "external" / "osm-cvrpgen" / "instances_v2" / "osm"
    if not sample_root.exists():
        pytest.skip(f"OSM sample fixtures not present at {sample_root}")

    info = probe_julia_workbench_generation_helpers(repo_root=repo_root, sample_root=sample_root)

    assert info["city_count"] >= 1
    assert isinstance(info["preview_available"], bool)
    assert "london" in info["city_slugs"]
    assert 100 in info["london_counts"]
    assert info["preview_feature_count"] == 101
    assert info["preview_mode"] == "catalog_sample"
    assert info["preview_city"] == "London"
    assert info["preview_method"] == "hybrid"
    assert info["sample_method"] == "poi_categories"
    assert info["sample_size_dir"] == "n101"


def test_julia_site_api_renders_uploaded_routes_from_embedded_cache_and_falls_back_to_straight_lines() -> None:
    info = probe_julia_workbench_render_routes_helper()

    assert info["cached_render_mode"] == "cached_road"
    assert info["cached_used_cache"] is True
    assert info["cached_cache_miss_count"] == 0
    assert info["cached_feature_count"] == 1
    assert info["cached_coordinate_count"] == 5
    assert info["cached_route_load"] == 4

    assert info["fallback_render_mode"] == "straight_line"
    assert info["fallback_used_cache"] is False
    assert info["fallback_cache_miss_count"] == 2
    assert info["fallback_feature_count"] == 1
    assert info["fallback_coordinate_count"] == 3
    assert info["fallback_route_load"] == 4

    assert info["cache_only_render_mode"] == "cached_road"
    assert info["cache_only_cache_miss_count"] == 0
    assert info["cache_only_straight_fallback_count"] == 0
    assert info["cache_only_cache_persisted"] is False
    assert info["cache_only_coordinate_count"] == 5


def test_instance_list_items_carry_size_and_id_and_per_objective_bks_values(tmp_path: Path) -> None:
    output_repo_dir = tmp_path / "MAMUT-routing"
    _, generated_vrptw = build_fixture_site_inputs(output_repo_dir)

    generate_site_payloads(
        output_repo_dir=output_repo_dir,
        source_commit="abcdef123456",
        published_at="2026-04-23T12:00:00",
        snapshot_id="2026-04-23-abcdef1",
    )

    payload_root = output_repo_dir / "dist" / "site-payloads"

    sintef_family = json.loads(
        (payload_root / "benchmarks" / "vrptw" / "sintef2008" / "index.json").read_text(encoding="utf-8")
    )
    assert len(sintef_family["items"]) == 1
    historical_item = sintef_family["items"][0]
    assert historical_item["display_name"] == "C101"
    assert historical_item["num_customers"] == 2
    assert historical_item["instance_id"] == "vrptw-sintef2008-n2-C101"
    assert historical_item["objective_availability"] == [
        {"objective_function": "HierarchicalVehicleCost", "cost": 12, "num_routes": 1},
    ]

    vrptw_size_index = json.loads(
        (
            payload_root
            / "benchmarks"
            / "vrptw"
            / "mamut2026"
            / "fastest"
            / "brest"
            / "n=2"
            / "index.json"
        ).read_text(encoding="utf-8")
    )
    assert len(vrptw_size_index["items"]) == 1
    mamut_item = vrptw_size_index["items"][0]
    assert mamut_item["num_customers"] == 2
    assert mamut_item["instance_id"] == f"vrptw-mamut2026-fastest-brest-n2-{generated_vrptw.instance_name}"
    assert mamut_item["objective_availability"] == [
        {"objective_function": "HierarchicalVehicleCost", "cost": 12, "num_routes": 1},
        {"objective_function": "MonoCost", "cost": 12, "num_routes": None},
    ]


def test_objective_availability_rejects_duplicate_objective_entries() -> None:
    from mamut_routing_publish.site_payloads import BKSPageEntry, _objective_availability

    duplicate = [
        BKSPageEntry(
            objective_function=ObjectiveFunction.MONO_COST,
            artifact_path="a.bks.MonoCost.json",
            num_routes=1,
            cost=10,
        ),
        BKSPageEntry(
            objective_function=ObjectiveFunction.MONO_COST,
            artifact_path="b.bks.MonoCost.json",
            num_routes=1,
            cost=11,
        ),
    ]
    with pytest.raises(ValueError, match="one-BKS-per-"):
        _objective_availability(duplicate)


def test_catalog_items_are_sorted_by_size_then_display_name(tmp_path: Path) -> None:
    """Sintef-style fixture with two sizes — items must come back sorted by num_customers, then name."""
    from mamut_routing_lib.models import BenchmarkInstance

    output_repo_dir = tmp_path / "MAMUT-routing"

    def _historical(name: str, n: int) -> BenchmarkInstance:
        coords = [(0, 0)] + [(i, i) for i in range(1, n + 1)]
        return BenchmarkInstance(
            instance_name=name,
            instance_origin="Solomon1987",
            benchmark_name="Sintef2008",
            num_customers=n,
            num_vehicles=2,
            vehicle_capacity=10,
            coordinates=coords,
            demands=[0] + [1] * n,
            service_times=[0] + [10] * n,
            time_windows=[(0, 100)] * (n + 1),
            depot=0,
            arc_costs=[[0] * (n + 1) for _ in range(n + 1)],
        )

    fixtures = [
        ("R201", 5),
        ("C101", 5),
        ("C102", 2),
        ("R101", 2),
    ]
    for name, n in fixtures:
        instance = _historical(name, n)
        instance_path = (
            output_repo_dir / "benchmarks" / "VRPTW" / "Sintef2008" / f"n={n}" / f"{name}.vrp.json"
        )
        write_json(instance_path, instance.model_dump(mode="json"))
        write_json(
            instance_path.with_name(f"{name}.bks.HierarchicalVehicleCost.json"),
            make_bks(name, ObjectiveFunction.HIERARCHICAL_VEHICLE_COST, "fixture").model_dump(mode="json"),
        )

    generate_site_payloads(
        output_repo_dir=output_repo_dir,
        source_commit="abcdef123456",
        published_at="2026-04-23T12:00:00",
        snapshot_id="2026-04-23-abcdef1",
    )

    family = json.loads(
        (output_repo_dir / "dist" / "site-payloads" / "benchmarks" / "vrptw" / "sintef2008" / "index.json").read_text(encoding="utf-8")
    )
    ordering = [(item["num_customers"], item["display_name"]) for item in family["items"]]
    assert ordering == [(2, "C102"), (2, "R101"), (5, "C101"), (5, "R201")]


def _bks_only_record(*, problem_type="VRPTW", benchmark_name="Sintef2008", instance_name="C101", num_customers=2, metric_variant=None, place_slug=None, bks=None):
    return {
        "problem_type": problem_type,
        "benchmark_name": benchmark_name,
        "metric_variant": metric_variant,
        "place_slug": place_slug,
        "num_customers": num_customers,
        "instance_name": instance_name,
        "bks": bks or {},
    }


def test_compute_change_log_initial_mode_marks_everything_added() -> None:
    from mamut_routing_publish.site_payloads import _compute_change_log

    new_inventory = {
        "instances": {
            "vrptw-sintef2008-n2-C101": _bks_only_record(
                bks={"HierarchicalVehicleCost": {"cost": 12, "num_routes": 1, "authors": "test", "method": "fixture"}},
            ),
        }
    }
    log = _compute_change_log(None, new_inventory)
    assert log.is_initial is True
    assert log.counts.families_added == 1
    assert log.counts.instances_added == 1
    assert log.counts.bks_added == 1
    assert [c.kind for c in log.bks_changes] == ["added"]
    assert log.bks_changes[0].new is not None and log.bks_changes[0].new.cost == 12


def test_compute_change_log_pure_family_addition() -> None:
    from mamut_routing_publish.site_payloads import _compute_change_log

    prev = {"instances": {"vrptw-sintef2008-n2-C101": _bks_only_record(bks={"MonoCost": {"cost": 100}})}}
    new = {
        "instances": {
            "vrptw-sintef2008-n2-C101": _bks_only_record(bks={"MonoCost": {"cost": 100}}),
            "cvrp-mamut2026-fastest-brest-n2-foo": _bks_only_record(
                problem_type="CVRP", benchmark_name="Mamut2026",
                metric_variant="fastest", place_slug="brest", instance_name="foo",
                bks={"MonoCost": {"cost": 50, "num_routes": 2}},
            ),
        }
    }
    log = _compute_change_log(prev, new)
    assert log.is_initial is False
    assert log.counts.families_added == 1
    assert log.counts.families_removed == 0
    assert log.counts.instances_added == 1
    assert log.counts.bks_added == 1
    family_kinds = [(c.kind, c.problem_type.value, c.benchmark_name.value) for c in log.family_changes]
    assert family_kinds == [("added", "CVRP", "Mamut2026")]


def test_compute_change_log_instance_removal_emits_bks_removed_per_objective() -> None:
    from mamut_routing_publish.site_payloads import _compute_change_log

    prev = {
        "instances": {
            "vrptw-sintef2008-n2-C101": _bks_only_record(bks={
                "MonoCost": {"cost": 100},
                "HierarchicalVehicleCost": {"cost": 100, "num_routes": 2},
            }),
        }
    }
    new = {"instances": {}}
    log = _compute_change_log(prev, new)
    assert log.counts.instances_removed == 1
    assert log.counts.bks_removed == 2
    assert log.counts.families_removed == 1


def test_compute_change_log_monocost_improvement_and_regression() -> None:
    from mamut_routing_publish.site_payloads import _compute_change_log

    prev = {
        "instances": {
            "improve": _bks_only_record(instance_name="A", bks={"MonoCost": {"cost": 100}}),
            "regress": _bks_only_record(instance_name="B", bks={"MonoCost": {"cost": 200}}),
        }
    }
    new = {
        "instances": {
            "improve": _bks_only_record(instance_name="A", bks={"MonoCost": {"cost": 90}}),
            "regress": _bks_only_record(instance_name="B", bks={"MonoCost": {"cost": 220}}),
        }
    }
    log = _compute_change_log(prev, new)
    by_id = {c.instance_id: c for c in log.bks_changes}
    assert by_id["improve"].kind == "improved"
    assert by_id["improve"].cost_delta == -10
    assert by_id["improve"].cost_pct == -10.0
    assert by_id["regress"].kind == "regressed"
    assert by_id["regress"].cost_delta == 20
    assert by_id["regress"].cost_pct == 10.0


def test_compute_change_log_hvc_lex_order_vehicle_drop_wins() -> None:
    from mamut_routing_publish.site_payloads import _compute_change_log

    prev = {
        "instances": {
            "iid": _bks_only_record(bks={"HierarchicalVehicleCost": {"cost": 100, "num_routes": 5}}),
        }
    }
    new = {
        "instances": {
            "iid": _bks_only_record(bks={"HierarchicalVehicleCost": {"cost": 200, "num_routes": 4}}),
        }
    }
    log = _compute_change_log(prev, new)
    assert log.counts.bks_improved == 1
    change = log.bks_changes[0]
    assert change.kind == "improved"
    assert change.routes_delta == -1
    assert change.cost_delta == 100  # cost went up but vehicles dropped — still improved


def test_compute_change_log_drops_exactly_equal_pairs() -> None:
    from mamut_routing_publish.site_payloads import _compute_change_log

    prev = {"instances": {"iid": _bks_only_record(bks={"MonoCost": {"cost": 12345.6789}})}}
    new = {"instances": {"iid": _bks_only_record(bks={"MonoCost": {"cost": 12345.6789}})}}
    log = _compute_change_log(prev, new)
    assert log.bks_changes == []
    assert log.counts.bks_improved == 0


def test_compute_change_log_tiny_cost_diff_is_an_improvement() -> None:
    """BKS costs are canonical/exact — a 1e-12 difference is a real improvement."""
    from mamut_routing_publish.site_payloads import _compute_change_log

    prev_cost = 12345.6789
    new_cost = prev_cost - 1e-12
    prev = {"instances": {"iid": _bks_only_record(bks={"MonoCost": {"cost": prev_cost}})}}
    new = {"instances": {"iid": _bks_only_record(bks={"MonoCost": {"cost": new_cost}})}}
    log = _compute_change_log(prev, new)
    assert log.counts.bks_improved == 1
    assert log.bks_changes[0].kind == "improved"


def test_road_cache_enforcement_plan_targets_bks_route_edges(tmp_path: Path) -> None:
    from mamut_routing_publish.road_cache import build_road_cache_plan

    output_repo_dir = tmp_path / "MAMUT-routing"
    _, generated_vrptw = build_fixture_site_inputs(output_repo_dir)
    meta_path = (
        output_repo_dir
        / "benchmarks"
        / "VRPTW"
        / "Mamut2026"
        / "sidecars"
        / "brest"
        / "n=2"
        / generated_vrptw.instance_name
        / f"{generated_vrptw.instance_name}.meta.json"
    )
    write_json(
        meta_path,
        {
            "instance_id": generated_vrptw.instance_name,
            "source_osm_file": "osmdata/Brest.osm",
            "depot_instance_node_id": 1,
            "nodes": [
                {"instance_node_id": 1, "poi_lon": 0.0, "poi_lat": 0.0},
                {"instance_node_id": 2, "poi_lon": 1.0, "poi_lat": 1.0},
                {"instance_node_id": 3, "poi_lon": 2.0, "poi_lat": 2.0},
            ],
        },
    )

    plan = build_road_cache_plan(output_repo_dir)

    assert plan["entries"] == [
        {
            "meta_path": "benchmarks/VRPTW/Mamut2026/sidecars/brest/n=2/mamut-n2-beef456/mamut-n2-beef456.meta.json",
            "routes_by_metric": {
                "fastest": [[2, 3]],
            },
        },
    ]


def test_generate_site_payloads_persists_inventory_and_change_log_across_runs(tmp_path: Path) -> None:
    """End-to-end: first run is initial; second run with mutated state shows real diffs."""
    from mamut_routing_lib.json_utils import load_json_from_file

    output_repo_dir = tmp_path / "MAMUT-routing"
    _, generated_vrptw = build_fixture_site_inputs(output_repo_dir)

    # First run — initial snapshot
    generate_site_payloads(
        output_repo_dir=output_repo_dir,
        source_commit="firstcommit01",
        published_at="2026-04-23T12:00:00",
        snapshot_id="2026-04-23-firstcom",
    )

    inv_dir = output_repo_dir / "dist" / "site" / "snapshots"
    first_inventory_path = inv_dir / "2026-04-23-firstcom.inventory.json"
    assert first_inventory_path.exists()

    first_detail = json.loads(
        (
            output_repo_dir / "dist" / "site-payloads" / "history" / "2026-04-23-firstcom" / "index.json"
        ).read_text(encoding="utf-8")
    )
    assert first_detail["change_log"]["is_initial"] is True
    initial_counts = first_detail["change_log"]["counts"]
    assert initial_counts["instances_added"] == 3  # cvrp + vrptw + sintef historical
    assert initial_counts["bks_added"] == 4  # cvrp:MC, vrptw:HVC+MC, sintef:HVC
    assert initial_counts["families_added"] == 3
    assert initial_counts["bks_improved"] == 0
    assert initial_counts["bks_regressed"] == 0

    # Mutate state: tweak the VRPTW MonoCost BKS (improvement); delete the HVC BKS
    vrptw_dir = (
        output_repo_dir
        / "benchmarks"
        / "VRPTW"
        / "Mamut2026"
        / "fastest"
        / "brest"
        / "n=2"
        / generated_vrptw.instance_name
    )
    mc_path = vrptw_dir / f"{generated_vrptw.instance_name}.bks.MonoCost.json"
    mc_data = load_json_from_file(mc_path)
    mc_data["cost"] = 10  # was 12 — improvement
    save_json_to_file(mc_data, mc_path)
    hvc_path = vrptw_dir / f"{generated_vrptw.instance_name}.bks.HierarchicalVehicleCost.json"
    hvc_path.unlink()

    # Second run — non-initial snapshot
    generate_site_payloads(
        output_repo_dir=output_repo_dir,
        source_commit="secondcommit2",
        published_at="2026-04-30T12:00:00",
        snapshot_id="2026-04-30-secondc",
    )

    second_inventory_path = inv_dir / "2026-04-30-secondc.inventory.json"
    assert second_inventory_path.exists()
    assert first_inventory_path.exists()  # prior inventory must remain intact

    second_detail = json.loads(
        (
            output_repo_dir / "dist" / "site-payloads" / "history" / "2026-04-30-secondc" / "index.json"
        ).read_text(encoding="utf-8")
    )
    log = second_detail["change_log"]
    assert log["is_initial"] is False
    assert log["counts"]["bks_improved"] == 1
    assert log["counts"]["bks_removed"] == 1
    assert log["counts"]["bks_regressed"] == 0
    improved = [c for c in log["bks_changes"] if c["kind"] == "improved"]
    assert len(improved) == 1
    assert improved[0]["objective_function"] == "MonoCost"
    assert improved[0]["cost_delta"] == -2
    removed = [c for c in log["bks_changes"] if c["kind"] == "removed"]
    assert len(removed) == 1
    assert removed[0]["objective_function"] == "HierarchicalVehicleCost"

    # Ledger entry for current snapshot exposes change_counts
    ledger = json.loads((output_repo_dir / "dist" / "site" / "history.json").read_text(encoding="utf-8"))
    assert ledger["entries"][0]["snapshot"]["snapshot_id"] == "2026-04-30-secondc"
    assert ledger["entries"][0]["change_counts"]["bks_improved"] == 1
    assert ledger["entries"][1]["change_counts"]["bks_added"] == 4  # initial entry preserved
