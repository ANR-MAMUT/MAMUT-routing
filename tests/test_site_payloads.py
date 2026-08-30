from __future__ import annotations

import json
from pathlib import Path
import shutil
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from mamut_routing_lib.artifacts import discover_benchmark_instances
from mamut_routing_lib.enums import MetricVariant, ObjectiveFunction, ProblemType
from mamut_routing_lib.json_utils import load_json_from_file, save_json_to_file
from mamut_routing_lib.models import BenchmarkBKS, BenchmarkInstance, BenchmarkInstanceCVRP
from mamut_routing_publish.cli import app
from mamut_routing_lib.td.pwlf import NDCPWLF, PWLFError
from mamut_routing_publish.site_payloads import (
    _TD_SCHEDULE_DOMAIN_TOL,
    _atf_group_key,
    _resolve_instance_group,
    _schedule_groups,
    _deduplicate_discovered_instances,
    _evaluate_on_domain,
    _home_preview_metric_rank,
    derive_historical_taxonomy,
    generate_site_payloads,
)
from mamut_routing_publish.site_webapp import generate_site_webapp


def make_generated_cvrp_instance() -> BenchmarkInstanceCVRP:
    return BenchmarkInstanceCVRP(
        instance_name="poryos-n2-cafe123",
        instance_origin="OsmCvrpGen",
        benchmark_name="Poryos2026",
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
                "vrp_json": "benchmarks/CVRP/Poryos2026/fastest/brest/n=2/poryos-n2-cafe123/poryos-n2-cafe123.vrp.json",
                "vrp": "benchmarks/CVRP/Poryos2026/fastest/brest/n=2/poryos-n2-cafe123/poryos-n2-cafe123.vrp",
                "meta": "benchmarks/CVRP/Poryos2026/sidecars/brest/n=2/poryos-n2-cafe123/poryos-n2-cafe123.meta.json",
                "manifest": "benchmarks/CVRP/Poryos2026/sidecars/brest/n=2/poryos-n2-cafe123/poryos-n2-cafe123.manifest.json",
            },
            "sibling_variant_paths": {
                "euclidean": "benchmarks/CVRP/Poryos2026/euclidean/brest/n=2/poryos-n2-cafe123/poryos-n2-cafe123.vrp.json"
            },
            "derived_problem_paths": {
                "fastest": "benchmarks/VRPTW/Poryos2026/fastest/brest/n=2/poryos-n2-beef456/poryos-n2-beef456.vrp.json"
            },
            "source_problem_paths": {},
        },
    )


def make_generated_vrptw_instance() -> BenchmarkInstance:
    return BenchmarkInstance(
        instance_name="poryos-n2-beef456",
        instance_origin="OsmCvrpGen",
        benchmark_name="Poryos2026",
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
                "vrp_json": "benchmarks/VRPTW/Poryos2026/fastest/brest/n=2/poryos-n2-beef456/poryos-n2-beef456.vrp.json",
                "vrp": "benchmarks/VRPTW/Poryos2026/fastest/brest/n=2/poryos-n2-beef456/poryos-n2-beef456.vrp",
                "meta": "benchmarks/VRPTW/Poryos2026/sidecars/brest/n=2/poryos-n2-beef456/poryos-n2-beef456.meta.json",
                "manifest": "benchmarks/VRPTW/Poryos2026/sidecars/brest/n=2/poryos-n2-beef456/poryos-n2-beef456.manifest.json",
            },
            "sibling_variant_paths": {
                "euclidean": "benchmarks/VRPTW/Poryos2026/euclidean/brest/n=2/poryos-n2-beef456/poryos-n2-beef456.vrp.json"
            },
            "derived_problem_paths": {},
            "source_problem_paths": {
                "cvrp_vrp_json": "benchmarks/CVRP/Poryos2026/fastest/brest/n=2/poryos-n2-cafe123/poryos-n2-cafe123.vrp.json"
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
        / "Poryos2026"
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
        / "Poryos2026"
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
        / "Poryos2026"
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
        / "Poryos2026"
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
        / "Poryos2026"
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
        / "Poryos2026"
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
    (output_repo_dir / "AUTHORS.md").write_text(
        """# Authors, Supervision, and Contributors

This page records the authorship, scientific supervision, project context, and contributor policy for MAMUT-routing.

## Original Authors and Maintainers

- Florian Rascoussier, aka Onyr
- Adrien Pichon, aka Anzury
""",
        encoding="utf-8",
    )

    return generated_cvrp, generated_vrptw


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
    assert root_index["breadcrumbs"] == [{"label": "benchmarks", "route_path": "/benchmarks/"}]
    assert [problem["problem_type"] for problem in root_index["problems"]] == ["CVRP", "VRPTW"]
    assert not (output_repo_dir / "benchmarks" / "vrptw" / "index.json").exists()

    objectives_payload = json.loads((payload_root / "objectives" / "index.json").read_text(encoding="utf-8"))
    assert objectives_payload["payload_kind"] == "objectives_page"
    assert objectives_payload["breadcrumbs"] == []
    assert [entry["objective_function"] for entry in objectives_payload["explainers"]] == [
        "HierarchicalVehicleCost",
        "MonoCost",
        "Duration",
        "FleetCostDuration",
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
    expected_project_routes = [
        "/project/legal-mentions/",
        "/project/authors/",
        "/project/citing/",
        "/project/glossary/",
        "/project/faq/",
        "/project/related-projects/",
        "/project/funding/",
    ]
    assert [page["route_path"] for page in project_payload["related_pages"]] == expected_project_routes

    project_text_payloads = {
        route: json.loads((payload_root / route.strip("/") / "index.json").read_text(encoding="utf-8"))
        for route in expected_project_routes
    }
    for route, payload in project_text_payloads.items():
        assert payload["payload_kind"] == "project_text_page"
        assert payload["route_path"] == route
        assert payload["project_route_path"] == "/project/"

    authors_payload = project_text_payloads["/project/authors/"]
    assert authors_payload["title"] == "Authors, Supervision, and Contributors"
    assert authors_payload["markdown"].startswith("# Authors, Supervision, and Contributors")
    assert "Florian Rascoussier, aka Onyr" in authors_payload["markdown"]
    assert "Adrien Pichon, aka Anzury" in authors_payload["markdown"]

    citing_payload = project_text_payloads["/project/citing/"]
    assert "CITATION.cff" in citing_payload["markdown"]
    assert "Software Heritage rolling pointer" in citing_payload["markdown"]
    assert "swh:1:rev:5dd0e60f69816a5e6afa3fa8c3c95902c5de3245" in citing_payload["markdown"]

    related_projects_payload = project_text_payloads["/project/related-projects/"]
    assert "mamut-routing-lib" in related_projects_payload["markdown"]
    assert "PyVRP" in related_projects_payload["markdown"]
    assert "KAYROS" in related_projects_payload["markdown"]

    legal_payload = project_text_payloads["/project/legal-mentions/"]
    assert legal_payload["title"] == "Legal Mentions"
    assert legal_payload["markdown"].startswith("# Legal Mentions")
    assert "MIT License" in legal_payload["markdown"]
    assert "CC BY-NC 4.0" in legal_payload["markdown"]
    assert "ODbL" in legal_payload["markdown"]
    assert "does not require cookies" in legal_payload["markdown"]
    assert "self-hosted" in legal_payload["markdown"]
    assert "tile.openstreetmap.org" in legal_payload["markdown"]
    assert "Google Fonts" not in legal_payload["markdown"]
    assert "unpkg.com" not in legal_payload["markdown"]

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
            / "poryos2026"
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
    assert vrptw_instance_page["source_problem_routes"]["cvrp_vrp_json"] == "/benchmarks/cvrp/poryos2026/fastest/brest/n=2/poryos-n2-cafe123/"

    history_payload = json.loads((site_output / "site" / "history.json").read_text(encoding="utf-8"))
    routed_history_payload = json.loads((payload_root / "history" / "index.json").read_text(encoding="utf-8"))
    assert routed_history_payload == history_payload
    assert history_payload["route_path"] == "/history/"
    assert history_payload["current_snapshot_id"] == "2026-04-23-abcdef1"
    assert history_payload["entries"][0]["snapshot"]["source_commit"] == "abcdef123456"

    history_detail_payload = json.loads(
        (payload_root / "history" / "2026-04-23-abcdef1" / "index.json").read_text(encoding="utf-8")
    )
    assert history_detail_payload["payload_kind"] == "history_detail"
    assert history_detail_payload["affected_objective_functions"] == ["HierarchicalVehicleCost", "MonoCost"]

    webapp_summary = generate_site_webapp(output_repo_dir)
    # 7 css/js bundles (incl. the shared nocturne tokens/runtime) + 4 icons + 8 logos
    # + 1 font + 9 vendored Leaflet files.
    assert webapp_summary.asset_files_written == 28
    assert webapp_summary.html_files_written > 0
    assert (site_output / "index.html").exists()
    assert (site_output / "benchmarks" / "index.html").exists()
    assert (site_output / "project" / "index.html").exists()
    for route in expected_project_routes:
        assert (site_output / route.strip("/") / "index.html").exists()
    assert not (output_repo_dir / "index.html").exists()
    assert not (output_repo_dir / "site").exists()
    assert not (output_repo_dir / "benchmarks" / "vrptw" / "index.json").exists()
    assert (site_output / "history" / "index.html").exists()
    assert (site_output / "workbench" / "index.html").exists()
    assert (
        site_output
        / "benchmarks"
        / "vrptw"
        / "poryos2026"
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
    assert (site_output / "webapp" / "fonts" / "InterVariable.woff2").exists()
    assert (site_output / "webapp" / "vendor" / "leaflet" / "leaflet.js").exists()
    assert (site_output / "webapp" / "vendor" / "leaflet" / "leaflet.css").exists()

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
    # Nocturne reskin: fonts are self-hosted, no third-party asset hosts.
    assert "webapp/fonts/InterVariable.woff2" in root_html
    assert "fonts.googleapis.com" not in root_html
    assert "unpkg.com" not in root_html

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
    assert 'id="benchmarkGeometryFilter"' in workbench_html
    assert 'id="benchmarkSortDirection"' in workbench_html
    assert 'id="map"' in workbench_html
    # Nocturne reskin: Leaflet and fonts are self-hosted.
    assert "vendor/leaflet/leaflet.js" in workbench_html
    assert "vendor/leaflet/leaflet.css" in workbench_html
    assert "unpkg.com" not in workbench_html
    assert "fonts.googleapis.com" not in workbench_html
    assert 'id="benchmarkInstanceSelect"' in workbench_html
    assert 'id="benchmarkObjectiveSelect"' in workbench_html
    assert 'id="routeSelectorCard" hidden' in workbench_html
    assert 'id="routeSelectorContainer"' in workbench_html
    assert 'id="routeLegend"' not in workbench_html
    assert 'id="routeSelectorDetails"' not in workbench_html
    assert "Historical benchmark families use straight-line rendering" in workbench_html
    assert "Road geometry will be rendered automatically" not in workbench_html
    assert 'id="pageTitle"' not in workbench_html
    assert 'id="pageIntro"' not in workbench_html
    assert not (site_output / "workbench" / "derive" / "index.html").exists()

    site_js = (site_output / "webapp" / "site.js").read_text(encoding="utf-8")
    workbench_js = (site_output / "webapp" / "workbench.js").read_text(encoding="utf-8")
    assert "GITHUB_BENCHMARKS_ROOT" in site_js
    assert "GitHub_Invertocat_Black.svg" in site_js
    assert "breadcrumb-github-link" in site_js
    assert 'FILE_BACKED_BENCHMARK_FAMILIES = new Set(["Dimacs2021", "Sintef2008"])' in site_js
    assert "pointsToHistoricalInstance ? sourceSegments.slice(0, -1) : sourceSegments" in site_js
    assert "Open Derive Mode" not in site_js
    assert "deriveBenchmarkBtn" not in workbench_js
    assert "Promise.allSettled" in workbench_js
    assert "compareCatalogItems" in site_js
    assert "catalogSortOptions" in site_js
    assert 'publicCatalogSelect("geometry", "Geometry", items)' in site_js
    assert "data-public-sort-direction" in site_js
    assert 'direction: normalizeSortDirection(runtimeParams.get("dir"))' in site_js
    assert "hiddenRoutes: new Set()" in workbench_js
    assert "focusedRoute: null" in workbench_js
    assert "data-route-visibility" in workbench_js
    assert 'usesRoadMetric(summary) ? "full" : "faded"' in workbench_js
    assert 'usesRoadMetric(payload.summary) ? "full" : "faded"' in site_js
    assert 'class="route-view-opacity" type="range" min="0" max="0.8"' in workbench_js
    assert "addArrowsToPolyline(polyline, color, opacity)" in workbench_js
    assert "const hasSeparableLegs = rawSegments.length > 1;" in workbench_js
    assert "visibleLimit" not in workbench_js
    assert "selectedRoutes" not in workbench_js
    assert "route-pager" not in workbench_js
    assert "Straight-line rendering is the default for historical benchmark families." in workbench_js
    # The road-geometry status is keyed on whether the family ships a geo sidecar,
    # not on its name, so every generated OSM collection gets the same wording.
    assert "Published road geometry is unavailable for this BKS." in workbench_js
    assert "Poryos2026 BKS" not in workbench_js
    assert "Straight-line rendering matches the Euclidean metric for this instance." in workbench_js
    assert "Road geometry will be rendered automatically" not in workbench_js
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


def test_generate_site_payloads_writes_family_context_pages_from_report(tmp_path: Path) -> None:
    output_repo_dir = tmp_path / "MAMUT-routing"
    build_fixture_site_inputs(output_repo_dir)
    context_report = output_repo_dir / "family_context.md"
    context_report.write_text(
        """# Benchmark families

### `Sintef2008` (VRPTW)

SINTEF context first paragraph with `HierarchicalVehicleCost` and a [source](https://example.com/sintef).

- Preserves a bullet as report Markdown.

### Related benchmark infrastructure

This heading is intentionally not a benchmark-family page.

### `Poryos2026` (CVRP)

MAMUT CVRP context first paragraph.
""",
        encoding="utf-8",
    )
    sintef_license = output_repo_dir / "benchmarks" / "VRPTW" / "Sintef2008" / "LICENSE"
    sintef_license.write_text(
        """SPDX-License-Identifier: MIT

MAMUT curation artifacts use the MIT License.
https://mit-license.org/
""",
        encoding="utf-8",
    )
    mamut_cvrp_license = output_repo_dir / "benchmarks" / "CVRP" / "Poryos2026" / "LICENSE"
    mamut_cvrp_license.write_text(
        """SPDX-License-Identifier: ODbL-1.0

OSM-derived artifacts use ODbL.
https://opendatacommons.org/licenses/odbl/1-0/
""",
        encoding="utf-8",
    )

    generate_site_payloads(
        output_repo_dir=output_repo_dir,
        source_commit="abcdef123456",
        published_at="2026-04-23T12:00:00",
        snapshot_id="2026-04-23-abcdef1",
        history_summary="Fixture publication.",
        family_context_report_path=context_report,
    )

    payload_root = output_repo_dir / "dist" / "site-payloads"
    vrptw_problem = json.loads((payload_root / "benchmarks" / "vrptw" / "index.json").read_text(encoding="utf-8"))
    sintef_card = next(family for family in vrptw_problem["families"] if family["benchmark_name"] == "Sintef2008")
    mamut_vrptw_card = next(family for family in vrptw_problem["families"] if family["benchmark_name"] == "Poryos2026")
    assert sintef_card["context_route_path"] == "/benchmarks/vrptw/sintef2008/context/"
    assert mamut_vrptw_card["context_route_path"] is None

    family_payload = json.loads(
        (payload_root / "benchmarks" / "vrptw" / "sintef2008" / "index.json").read_text(encoding="utf-8")
    )
    assert family_payload["context_route_path"] == "/benchmarks/vrptw/sintef2008/context/"
    assert family_payload["context_summary"] == (
        "SINTEF context first paragraph with `HierarchicalVehicleCost` and a [source](https://example.com/sintef)."
    )

    context_payload = json.loads(
        (payload_root / "benchmarks" / "vrptw" / "sintef2008" / "context" / "index.json").read_text(encoding="utf-8")
    )
    assert context_payload["payload_kind"] == "family_context_page"
    assert context_payload["title"] == "Sintef2008 (VRPTW) Context"
    assert context_payload["family_route_path"] == "/benchmarks/vrptw/sintef2008/"
    assert "Preserves a bullet" in context_payload["markdown"]
    assert context_payload["license_spdx_id"] == "MIT"
    assert "MAMUT curation artifacts use the MIT License." in context_payload["license_markdown"]
    assert "[https://mit-license.org/](https://mit-license.org/)" in context_payload["license_markdown"]
    assert not (payload_root / "benchmarks" / "related-benchmark-infrastructure").exists()

    cvrp_problem = json.loads((payload_root / "benchmarks" / "cvrp" / "index.json").read_text(encoding="utf-8"))
    mamut_cvrp_card = next(family for family in cvrp_problem["families"] if family["benchmark_name"] == "Poryos2026")
    assert mamut_cvrp_card["context_route_path"] == "/benchmarks/cvrp/poryos2026/context/"
    mamut_cvrp_context_payload = json.loads(
        (payload_root / "benchmarks" / "cvrp" / "poryos2026" / "context" / "index.json").read_text(encoding="utf-8")
    )
    assert mamut_cvrp_context_payload["license_spdx_id"] == "ODbL-1.0"
    assert (
        "[https://opendatacommons.org/licenses/odbl/1-0/](https://opendatacommons.org/licenses/odbl/1-0/)"
        in mamut_cvrp_context_payload["license_markdown"]
    )

    webapp_summary = generate_site_webapp(output_repo_dir)
    assert webapp_summary.html_files_written > 0
    assert (output_repo_dir / "dist" / "benchmarks" / "vrptw" / "sintef2008" / "context" / "index.html").exists()
    site_js = (output_repo_dir / "dist" / "webapp" / "site.js").read_text(encoding="utf-8")
    assert 'renderCard(\n        "License"' in site_js
    assert "payload.license_spdx_id" in site_js
    assert "payload.license_markdown" in site_js


def test_family_license_section_falls_back_to_collection_layout(tmp_path: Path) -> None:
    # Poryos2026 stores its problem-type layers under benchmarks/Poryos2026/<PT>/
    # with a single LICENSE at the collection root; the standard per-family
    # path benchmarks/<PT>/Poryos2026/LICENSE does not exist there.
    from mamut_routing_lib.enums import BenchmarkName, ProblemType
    from mamut_routing_publish.site_payloads import _load_family_license_section

    repo = tmp_path / "repo"
    collection_license = repo / "benchmarks" / "Poryos2026" / "LICENSE"
    collection_license.parent.mkdir(parents=True)
    collection_license.write_text(
        """SPDX-License-Identifier: ODbL-1.0

OSM-derived artifacts use ODbL.
""",
        encoding="utf-8",
    )
    for problem_type in (ProblemType.CVRP, ProblemType.VRPTW, ProblemType.TDVRP, ProblemType.TDVRPTW):
        section = _load_family_license_section(repo, problem_type, BenchmarkName.PORYOS_2026)
        assert section.spdx_id == "ODbL-1.0"
        assert "ODbL" in (section.markdown or "")

    # A per-family LICENSE at the standard path wins over the collection root.
    family_license = repo / "benchmarks" / "TDVRP" / "Poryos2026" / "LICENSE"
    family_license.parent.mkdir(parents=True)
    family_license.write_text("SPDX-License-Identifier: MIT\n", encoding="utf-8")
    assert _load_family_license_section(repo, ProblemType.TDVRP, BenchmarkName.PORYOS_2026).spdx_id == "MIT"
    assert _load_family_license_section(repo, ProblemType.CVRP, BenchmarkName.PORYOS_2026).spdx_id == "ODbL-1.0"


def test_generate_site_payloads_accepts_legacy_history_without_change_counts(tmp_path: Path) -> None:
    """A pre-``change_counts`` ledger entry is read back and diffed, not rejected."""
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
                    "affected_benchmark_names": ["Poryos2026"],
                    "affected_objective_functions": ["MonoCost"],
                }
            ],
        },
        output_repo_dir / "dist" / "site" / "history.json",
    )
    save_json_to_file(
        {
            "snapshot_id": legacy_snapshot["snapshot_id"],
            "generated_at": legacy_snapshot["published_at"],
            "instances": {
                "cvrp-poryos2026-fastest-brest-n2-poryos-n2-cafe123": {
                    "problem_type": "CVRP",
                    "benchmark_name": "Poryos2026",
                    "metric_variant": "fastest",
                    "place_slug": "brest",
                    "num_customers": 2,
                    "instance_name": "poryos-n2-cafe123",
                    "bks": {
                        "MonoCost": {
                            "cost": 12,
                            "num_routes": 1,
                            "authors": "Florian Rascoussier (0nyr) and Adrien Pichon (Anzury)",
                            "method": "hgs-v1",
                        }
                    },
                }
            },
        },
        output_repo_dir / "dist" / "site" / "snapshots" / "2026-04-22-legacy.inventory.json",
    )

    generate_site_payloads(
        output_repo_dir=output_repo_dir,
        source_commit="abcdef123456",
        published_at="2026-04-23T12:00:00",
        snapshot_id="2026-04-23-abcdef1",
    )

    ledger = json.loads((output_repo_dir / "dist" / "site" / "history.json").read_text(encoding="utf-8"))
    assert ledger["entries"][0]["snapshot"]["snapshot_id"] == "2026-04-23-abcdef1"
    assert ledger["entries"][0]["change_counts"] == {
        "families_added": 2,
        "families_removed": 0,
        "instances_added": 2,
        "instances_removed": 0,
        "bks_added": 3,
        "bks_removed": 0,
        "bks_improved": 0,
        "bks_regressed": 0,
    }
    assert ledger["entries"][1]["snapshot"]["snapshot_id"] == "2026-04-22-legacy"
    assert ledger["entries"][1]["affected_benchmark_names"] == ["Poryos2026"]
    assert ledger["entries"][1]["change_counts"] == {
        "families_added": 1,
        "families_removed": 0,
        "instances_added": 1,
        "instances_removed": 0,
        "bks_added": 1,
        "bks_removed": 0,
        "bks_improved": 0,
        "bks_regressed": 0,
    }


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
        {
            "objective_function": "HierarchicalVehicleCost",
            "cost": 12,
            "num_routes": 1,
            "artifact_path": "benchmarks/VRPTW/Sintef2008/n=2/C101.bks.HierarchicalVehicleCost.json",
            "optimality_proven": False,
        },
    ]

    vrptw_size_index = json.loads(
        (
            payload_root
            / "benchmarks"
            / "vrptw"
            / "poryos2026"
            / "fastest"
            / "brest"
            / "n=2"
            / "index.json"
        ).read_text(encoding="utf-8")
    )
    assert len(vrptw_size_index["items"]) == 1
    mamut_item = vrptw_size_index["items"][0]
    assert mamut_item["num_customers"] == 2
    assert mamut_item["instance_id"] == f"vrptw-poryos2026-fastest-brest-n2-{generated_vrptw.instance_name}"
    mamut_dir = f"benchmarks/VRPTW/Poryos2026/fastest/brest/n=2/{generated_vrptw.instance_name}"
    assert mamut_item["objective_availability"] == [
        {
            "objective_function": "HierarchicalVehicleCost",
            "cost": 12,
            "num_routes": 1,
            "artifact_path": f"{mamut_dir}/{generated_vrptw.instance_name}.bks.HierarchicalVehicleCost.json",
            "optimality_proven": False,
        },
        {
                "objective_function": "MonoCost",
                "cost": 12,
                "num_routes": 1,
            "artifact_path": f"{mamut_dir}/{generated_vrptw.instance_name}.bks.MonoCost.json",
            "optimality_proven": False,
        },
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
            "cvrp-poryos2026-fastest-brest-n2-foo": _bks_only_record(
                problem_type="CVRP", benchmark_name="Poryos2026",
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
    assert family_kinds == [("added", "CVRP", "Poryos2026")]


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

    inv_dir = output_repo_dir / "publish-state" / "snapshots"
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
        / "Poryos2026"
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


def test_site_build_reports_progress_on_stderr_and_keeps_stdout_json(tmp_path: Path) -> None:
    output_repo_dir = tmp_path / "MAMUT-routing"
    build_fixture_site_inputs(output_repo_dir)
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "site",
            "build",
            "--output-repo-dir",
            str(output_repo_dir),
            "--source-commit",
            "abcdef123456",
            "--published-at",
            "2026-04-23T12:00:00",
            "--snapshot-id",
            "fixture-progress",
            "--jobs",
            "1",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["payload_summary"]["snapshot_id"] == "fixture-progress"
    assert payload["build_summary"]["generated_files_written"] == (
        payload["payload_summary"]["payload_files_written"]
        + payload["webapp_summary"]["html_files_written"]
        + payload["webapp_summary"]["asset_files_written"]
    )
    assert payload["build_summary"]["wall_time_seconds"] >= 0
    assert payload["build_summary"]["max_memory_gib"] is None or payload["build_summary"]["max_memory_gib"] > 0
    assert "payload_paths" not in payload["payload_summary"]
    assert "[site build]" in result.stderr
    assert "resolving instances" in result.stderr
    assert "build summary" in result.stderr


def test_site_build_quiet_suppresses_progress(tmp_path: Path) -> None:
    output_repo_dir = tmp_path / "MAMUT-routing"
    build_fixture_site_inputs(output_repo_dir)
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "site",
            "build",
            "--output-repo-dir",
            str(output_repo_dir),
            "--source-commit",
            "abcdef123456",
            "--published-at",
            "2026-04-23T12:00:00",
            "--snapshot-id",
            "fixture-quiet",
            "--jobs",
            "1",
            "--quiet",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["payload_summary"]["snapshot_id"] == "fixture-quiet"
    assert payload["build_summary"]["generated_files_written"] > 0
    assert result.stderr == ""


def test_site_build_json_progress_and_file_listing(tmp_path: Path) -> None:
    output_repo_dir = tmp_path / "MAMUT-routing"
    build_fixture_site_inputs(output_repo_dir)
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "site",
            "build",
            "--output-repo-dir",
            str(output_repo_dir),
            "--source-commit",
            "abcdef123456",
            "--published-at",
            "2026-04-23T12:00:00",
            "--snapshot-id",
            "fixture-json-progress",
            "--jobs",
            "1",
            "--progress-format",
            "json",
            "--list-files",
        ],
    )

    assert result.exit_code == 0, result.output
    stderr_events = [json.loads(line) for line in result.stderr.splitlines() if line.strip()]
    assert any(event["event"] == "phase" and event["message"] == "resolved repository" for event in stderr_events)
    assert any(event["event"] == "progress" and event["message"] == "resolve instances" for event in stderr_events)
    assert any(event["event"] == "phase" and event["message"] == "build summary" for event in stderr_events)
    payload = json.loads(result.stdout)
    assert payload["build_summary"]["jobs_resolved"] == 1
    assert "site-payloads/index.json" in payload["payload_summary"]["payload_paths"]
    assert "index.html" in payload["webapp_summary"]["html_paths"]
    assert "webapp/site.css" in payload["webapp_summary"]["asset_paths"]


def test_site_build_materializes_atf_cache_unless_skipped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import mamut_routing_publish.atf_cache as atf_cache_module

    calls: list[dict] = []

    def record_materialize(repo_dir, *, max_customers, jobs=None, cache_dir=None, seed_from=None):
        calls.append({"repo_dir": Path(repo_dir), "max_customers": max_customers, "cache_dir": cache_dir})
        return atf_cache_module.ATFCacheSummary()

    monkeypatch.setattr(atf_cache_module, "materialize_atf_cache", record_materialize)
    output_repo_dir = tmp_path / "MAMUT-routing"
    build_fixture_site_inputs(output_repo_dir)
    runner = CliRunner()
    common_args = [
        "site",
        "build",
        "--output-repo-dir",
        str(output_repo_dir),
        "--source-commit",
        "abcdef123456",
        "--published-at",
        "2026-04-23T12:00:00",
        "--jobs",
        "1",
    ]

    result = runner.invoke(app, [*common_args, "--snapshot-id", "fixture-atf-default", "--atf-max-n", "123"])
    assert result.exit_code == 0, result.output
    assert calls == [
        {
            "repo_dir": output_repo_dir,
            "max_customers": 123,
            "cache_dir": output_repo_dir / "dist" / "atf-cache",
        }
    ]
    assert "materialized ATF sidecar cache" in result.stderr

    calls.clear()
    result = runner.invoke(app, [*common_args, "--snapshot-id", "fixture-atf-skip", "--skip-atf-cache"])
    assert result.exit_code == 0, result.output
    assert calls == []
    assert "ATF sidecar cache" not in result.stderr


def test_atf_materialization_never_forks_more_workers_than_tasks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json as json_module
    from concurrent.futures import Future

    import mamut_routing_publish.atf_cache as atf_cache_module

    assert atf_cache_module.resolve_atf_jobs(8, 3) == 3
    assert atf_cache_module.resolve_atf_jobs(2, 30) == 2
    # An empty task set never reaches the pool, but the floor keeps
    # max_workers legal if it ever did.
    assert atf_cache_module.resolve_atf_jobs(8, 0) == 1

    repo_dir = tmp_path / "MAMUT-routing"
    tree = repo_dir / "benchmarks" / "TDVRPTW" / "Fake" / "n=10"
    tree.mkdir(parents=True)
    for index in (1, 2):
        payload = {
            "benchmark_name": "Fake",
            "instance_name": f"fake-{index}",
            "num_customers": 10,
            "td": {"model": atf_cache_module.TD_IGP_MODEL},
        }
        (tree / f"fake-{index}.vrp.json").write_text(json_module.dumps(payload), encoding="utf-8")

    recorded: list[int] = []

    class RecordingPool:
        def __init__(self, max_workers=None):
            recorded.append(max_workers)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def submit(self, _fn, _instance_path, cache_path):
            future: Future = Future()
            future.set_result(cache_path)
            return future

    monkeypatch.setattr(atf_cache_module, "ProcessPoolExecutor", RecordingPool)
    summary = atf_cache_module.materialize_atf_cache(repo_dir, jobs=16)
    assert len(summary.materialized) == 2
    assert recorded == [2]


def test_site_build_atf_jobs_pins_the_materialization_worker_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import mamut_routing_publish.atf_cache as atf_cache_module

    seen: list[int | None] = []

    def record_materialize(repo_dir, *, max_customers, jobs=None, cache_dir=None, seed_from=None):
        seen.append(jobs)
        return atf_cache_module.ATFCacheSummary()

    monkeypatch.setattr(atf_cache_module, "materialize_atf_cache", record_materialize)
    output_repo_dir = tmp_path / "MAMUT-routing"
    build_fixture_site_inputs(output_repo_dir)
    runner = CliRunner()
    common_args = [
        "site",
        "build",
        "--output-repo-dir",
        str(output_repo_dir),
        "--source-commit",
        "abcdef123456",
        "--published-at",
        "2026-04-23T12:00:00",
        "--jobs",
        "1",
    ]

    result = runner.invoke(app, [*common_args, "--snapshot-id", "fixture-atf-pinned", "--atf-jobs", "3"])
    assert result.exit_code == 0, result.output
    assert seen == [3]

    # 'auto' resolves to the phase default rather than being forwarded as None,
    # so the reported worker count is always the one actually used.
    seen.clear()
    result = runner.invoke(app, [*common_args, "--snapshot-id", "fixture-atf-auto"])
    assert result.exit_code == 0, result.output
    assert seen == [atf_cache_module.resolve_atf_jobs(None)]

    seen.clear()
    result = runner.invoke(app, [*common_args, "--snapshot-id", "fixture-atf-bad", "--atf-jobs", "0"])
    assert result.exit_code != 0
    assert seen == []
    assert "auto" in result.stderr


def test_site_payload_generation_serial_and_parallel_outputs_match(tmp_path: Path) -> None:
    serial_repo_dir = tmp_path / "serial" / "MAMUT-routing"
    parallel_repo_dir = tmp_path / "parallel" / "MAMUT-routing"
    build_fixture_site_inputs(serial_repo_dir)
    build_fixture_site_inputs(parallel_repo_dir)

    serial_summary = generate_site_payloads(
        output_repo_dir=serial_repo_dir,
        source_commit="abcdef123456",
        published_at="2026-04-23T12:00:00",
        snapshot_id="fixture-parity",
        jobs=1,
    )
    parallel_summary = generate_site_payloads(
        output_repo_dir=parallel_repo_dir,
        source_commit="abcdef123456",
        published_at="2026-04-23T12:00:00",
        snapshot_id="fixture-parity",
        jobs=2,
    )

    assert serial_summary.model_dump() == parallel_summary.model_dump()
    serial_payload = json.loads((serial_repo_dir / "dist" / "site-payloads" / "benchmarks" / "index.json").read_text())
    parallel_payload = json.loads((parallel_repo_dir / "dist" / "site-payloads" / "benchmarks" / "index.json").read_text())
    assert serial_payload == parallel_payload


def test_evaluate_on_domain_absorbs_horizon_ulp_overshoot() -> None:
    # An arc ATF over the departure axis [0, horizon]; horizon = 1501 as on the
    # real horizon-tight instances that motivated the clamp.
    horizon = 1501.0
    fn = NDCPWLF([0.0, horizon], [10.0, 1600.0])

    # Interior points are untouched -- identical to a plain evaluate.
    assert _evaluate_on_domain(fn, 750.0) == fn.evaluate(750.0)

    # A departure time a few ULP past the horizon (the observed failure mode)
    # is clamped onto the boundary and returns the boundary image, not a raise.
    overshoot = horizon + 5e-13
    assert overshoot > horizon  # genuinely out of domain by rounding drift
    assert _evaluate_on_domain(fn, overshoot) == fn.evaluate(horizon)

    # Symmetric dust clamp at the lower edge.
    assert _evaluate_on_domain(fn, -5e-13) == fn.evaluate(0.0)

    # A genuine out-of-domain time (far beyond the dust tolerance) still raises
    # loudly -- the clamp must not mask a real infeasibility.
    with pytest.raises(PWLFError):
        _evaluate_on_domain(fn, horizon + 10 * _TD_SCHEDULE_DOMAIN_TOL)


# ---------------------------------------------------------------------------
# Family-first collection (Poryos2026 v2): slim instances, shared sidecars,
# identity-based cross-links, geo-sidecar geometry.
# ---------------------------------------------------------------------------

_COLLECTION_BASE = "poryos-toyville-n2-poi"
_COLLECTION_CITY = "toyville"


def _collection_static_payload(*, metric: str, arc_costs_source: dict, name: str | None = None, tw_set: dict | None = None, with_tw: bool = False) -> dict:
    payload = {
        "instance_name": name or _COLLECTION_BASE,
        "instance_origin": "OsmCvrpGen",
        "benchmark_name": "Poryos2026",
        "num_customers": 2,
        "num_vehicles": None,
        "vehicle_capacity": 10,
        "coordinates": [[0.0, 0.0], [3.0, 4.0], [6.0, 8.0]],
        "demands": [0, 4, 4],
        "depot": 0,
        "metric_variant": metric,
        "arc_costs_source": arc_costs_source,
        "metadata": {
            "authors": "fixture",
            "generated_at": "2026-07-10",
            "city": _COLLECTION_CITY,
            "base_instance_name": _COLLECTION_BASE,
            "sidecars": {
                "geo": {"path": f"sidecars/{_COLLECTION_CITY}/n=2/{_COLLECTION_BASE}/{_COLLECTION_BASE}.geo.json.gz"},
            },
        },
    }
    if tw_set is not None:
        payload["metadata"]["tw_set"] = tw_set
    if with_tw:
        payload["service_times"] = [0, 10, 10]
        payload["time_windows"] = [[0, 86400], [100, 5000], [200, 6000]]
    return payload


def build_collection_fixture(output_repo_dir: Path) -> Path:
    from mamut_routing_lib.distances import InstanceDistances, compute_distances_sha256, save_instance_distances
    from mamut_routing_lib.geo import GeoNode, GeoRoadCache, InstanceGeo, save_instance_geo
    from mamut_routing_lib.sidecars import CollectionMarker, save_collection_marker

    collection = output_repo_dir / "benchmarks" / "Poryos2026"
    save_collection_marker(CollectionMarker(family="Poryos2026"), collection)

    distances = InstanceDistances(
        base_name=_COLLECTION_BASE,
        benchmark_name="Poryos2026",
        metric="fastest",
        num_customers=2,
        values=[[0.0, 120.5, 240.25], [120.5, 0.0, 130.75], [240.25, 130.75, 0.0]],
    )
    distances_rel = f"sidecars/{_COLLECTION_CITY}/n=2/{_COLLECTION_BASE}/{_COLLECTION_BASE}.distances-fastest.json.gz"
    save_instance_distances(distances, collection / distances_rel)
    fastest_source = {
        "model": "distances-sidecar",
        "distances": {"path": distances_rel, "sha256": compute_distances_sha256(distances)},
    }

    nodes = [
        GeoNode(instance_node_id=i, poi_lon=4.0 + 0.01 * i, poi_lat=45.0 + 0.01 * i, enu_x=float(i), enu_y=float(i), demand=0 if i == 0 else 4, source_tag="poi", graph_vertex_id=100 + i)
        for i in range(3)
    ]
    # Complete indexed cache for both road metrics over the 6 ordered pairs.
    pair_keys = [f"{i}-{j}" for i in range(3) for j in range(3) if i != j]
    cache = GeoRoadCache(
        vertex_lonlat=[(4.0 + 0.01 * i, 45.0 + 0.01 * i) for i in range(3)] + [(4.05, 45.05)],
        paths={metric: {key: [int(key[0]), 3, int(key[2])] for key in pair_keys} for metric in ("fastest", "shortest")},
    )
    geo = InstanceGeo(
        base_name=_COLLECTION_BASE,
        benchmark_name="Poryos2026",
        city=_COLLECTION_CITY,
        method="poi",
        source_osm_file="osmdata/Toyville.osm",
        reference_lla={"lat": 45.0, "lon": 4.0, "alt": 0.0},
        map_options={},
        nodes=nodes,
        road_cache=cache,
    )
    save_instance_geo(geo, collection / f"sidecars/{_COLLECTION_CITY}/n=2/{_COLLECTION_BASE}/{_COLLECTION_BASE}.geo.json.gz")

    cvrp_dir = collection / "CVRP" / "fastest" / _COLLECTION_CITY / "n=2" / _COLLECTION_BASE
    save_json_to_file(_collection_static_payload(metric="fastest", arc_costs_source=fastest_source), cvrp_dir / f"{_COLLECTION_BASE}.vrp.json")
    save_json_to_file(
        _collection_static_payload(metric="euclidean", arc_costs_source={"model": "euclidean", "decimals": 3}),
        collection / "CVRP" / "euclidean" / _COLLECTION_CITY / "n=2" / _COLLECTION_BASE / f"{_COLLECTION_BASE}.vrp.json",
    )
    save_json_to_file(
        BenchmarkBKS(
            instance_name=_COLLECTION_BASE,
            routes=[[1, 2]],
            cost=491.5,
            objective_function=ObjectiveFunction.MONO_COST,
            metadata={"authors": "fixture"},
        ).model_dump(mode="json"),
        cvrp_dir / f"{_COLLECTION_BASE}.bks.MonoCost.json",
    )

    vrptw_dir = collection / "VRPTW" / "fastest" / _COLLECTION_CITY / "n=2" / _COLLECTION_BASE
    save_json_to_file(
        _collection_static_payload(metric="fastest", arc_costs_source=fastest_source, with_tw=True, tw_set={"name": "td-shared", "td_paired": True}),
        vrptw_dir / f"{_COLLECTION_BASE}.vrp.json",
    )
    save_json_to_file(
        _collection_static_payload(
            metric="fastest", arc_costs_source=fastest_source, with_tw=True,
            name=f"{_COLLECTION_BASE}-tw-tight", tw_set={"name": "tight", "td_paired": False},
        ),
        vrptw_dir / f"{_COLLECTION_BASE}-tw-tight.vrp.json",
    )
    return collection


def test_collection_instances_resolve_with_geometry_and_identity_links(tmp_path: Path) -> None:
    output_repo_dir = tmp_path / "repo"
    build_collection_fixture(output_repo_dir)

    site_output = output_repo_dir / "dist"
    generate_site_payloads(output_repo_dir, source_commit="fixture123", site_output_dir=site_output)
    payload_root = site_output / "site-payloads"

    cvrp_page = json.loads(
        (payload_root / "benchmarks" / "cvrp" / "poryos2026" / "fastest" / _COLLECTION_CITY / "n=2" / _COLLECTION_BASE / "index.json").read_text(encoding="utf-8")
    )
    summary = cvrp_page["summary"]
    assert summary["viewer_render_mode"] == "cached_road"
    assert summary["road_cache_status"] == "complete"
    assert summary["road_cache_metrics"] == ["fastest", "shortest"]
    assert summary["license"] == "ODbL-1.0"
    assert summary["source_city"] == _COLLECTION_CITY
    links = cvrp_page["artifact_links"]
    assert links["geo_json_path"] == f"benchmarks/Poryos2026/sidecars/{_COLLECTION_CITY}/n=2/{_COLLECTION_BASE}/{_COLLECTION_BASE}.geo.json.gz"
    assert links["meta_path"] is None
    assert cvrp_page["sibling_variant_routes"] == {
        "CVRP (euclidean)": f"/benchmarks/cvrp/poryos2026/euclidean/{_COLLECTION_CITY}/n=2/{_COLLECTION_BASE}/",
    }
    assert cvrp_page["derived_problem_routes"] == {
        "VRPTW (td-shared)": f"/benchmarks/vrptw/poryos2026/fastest/{_COLLECTION_CITY}/n=2/{_COLLECTION_BASE}/",
        "VRPTW (tight)": f"/benchmarks/vrptw/poryos2026/fastest/{_COLLECTION_CITY}/n=2/{_COLLECTION_BASE}-tw-tight/",
    }
    assert cvrp_page["source_problem_routes"] == {}
    assert [entry["objective_function"] for entry in cvrp_page["bks_entries"]] == ["MonoCost"]

    tight_page = json.loads(
        (payload_root / "benchmarks" / "vrptw" / "poryos2026" / "fastest" / _COLLECTION_CITY / "n=2" / f"{_COLLECTION_BASE}-tw-tight" / "index.json").read_text(encoding="utf-8")
    )
    assert tight_page["sibling_variant_routes"] == {
        "VRPTW (td-shared)": f"/benchmarks/vrptw/poryos2026/fastest/{_COLLECTION_CITY}/n=2/{_COLLECTION_BASE}/",
    }
    assert tight_page["source_problem_routes"] == {
        "CVRP (fastest)": f"/benchmarks/cvrp/poryos2026/fastest/{_COLLECTION_CITY}/n=2/{_COLLECTION_BASE}/",
    }
    assert tight_page["derived_problem_routes"] == {}

    shared_page = json.loads(
        (payload_root / "benchmarks" / "vrptw" / "poryos2026" / "fastest" / _COLLECTION_CITY / "n=2" / _COLLECTION_BASE / "index.json").read_text(encoding="utf-8")
    )
    # The TD twins do not exist in this fixture: no phantom links may appear.
    assert shared_page["derived_problem_routes"] == {}
    assert shared_page["sibling_variant_routes"] == {
        "VRPTW (tight)": f"/benchmarks/vrptw/poryos2026/fastest/{_COLLECTION_CITY}/n=2/{_COLLECTION_BASE}-tw-tight/",
    }

    root_index = json.loads((payload_root / "benchmarks" / "index.json").read_text(encoding="utf-8"))
    assert len(root_index["items"]) == 4
    assert [item["num_customers"] for item in root_index["items"]] == [2, 2, 2, 2]
    tight_item = next(item for item in root_index["items"] if item["instance_id"].endswith("-tw-tight"))
    assert tight_item["tw_set"] == "tight"
    assert tight_item["place_slug"] == _COLLECTION_CITY
    fastest_item = next(
        item for item in root_index["items"]
        if item["locator"]["problem_type"] == "CVRP" and item["locator"]["metric_variant"] == "fastest"
    )
    assert len(fastest_item["objective_availability"]) == 1
    fastest_objective = fastest_item["objective_availability"][0]
    assert fastest_objective["objective_function"] == "MonoCost"
    assert fastest_objective["cost"] == 491.5
    assert fastest_objective["num_routes"] == 1
    assert fastest_objective["optimality_proven"] is False


def test_site_payloads_deduplicate_retired_collection_checkout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_repo_dir = tmp_path / "repo"
    canonical_collection = build_collection_fixture(output_repo_dir)
    # A stale checkout under a directory that does not match the marker's family.
    # (This used to be spelled "Mamut2026"; that name is a live family again, so
    # reusing it here would no longer exercise the mismatch this test is about.)
    shutil.copytree(canonical_collection, output_repo_dir / "benchmarks" / "Poryos2026-retired")
    monkeypatch.chdir(tmp_path)

    discovered = discover_benchmark_instances(Path("repo/benchmarks"))
    deduplicated = _deduplicate_discovered_instances(discovered, Path("repo/benchmarks"))
    assert len(deduplicated) == 4
    assert all("/benchmarks/Poryos2026/" in item.instance_path.as_posix() for item in deduplicated)

    with pytest.warns(UserWarning, match="Ignored 4 duplicate benchmark instance path"):
        generate_site_payloads(output_repo_dir, source_commit="fixture123")

    payload_root = output_repo_dir / "dist" / "site-payloads"
    root_index = json.loads((payload_root / "benchmarks" / "index.json").read_text(encoding="utf-8"))
    assert len(root_index["items"]) == 4
    assert all(
        item["artifact_vrp_json_path"].startswith("benchmarks/Poryos2026/")
        for item in root_index["items"]
    )


def test_home_preview_metric_preferences_include_all_static_metrics() -> None:
    cvrp_order = sorted(
        MetricVariant,
        key=lambda metric: _home_preview_metric_rank("CVRP", metric),
    )
    vrptw_order = sorted(
        MetricVariant,
        key=lambda metric: _home_preview_metric_rank("VRPTW", metric),
    )

    assert cvrp_order == [MetricVariant.SHORTEST, MetricVariant.FASTEST, MetricVariant.EUCLIDEAN]
    assert vrptw_order == [MetricVariant.EUCLIDEAN, MetricVariant.FASTEST, MetricVariant.SHORTEST]


def _fake_discovered(problem_type: ProblemType, relative_path: str, **extra):
    """A discovery item stub carrying just what the scheduler reads."""
    return SimpleNamespace(
        problem_type=problem_type,
        benchmark_name="Dabia2013",
        instance_path=Path("benchmarks") / relative_path,
        base_instance_name=extra.get("base_instance_name"),
        place_slug=extra.get("place_slug"),
        instance_name=Path(relative_path).name,
    )


def test_schedule_groups_keep_td_twins_together_without_merging_size_buckets() -> None:
    # C101 exists once per size bucket; only the TDVRPTW/TDVRP pair within one
    # bucket shares an ATF sidecar.
    items = [
        _fake_discovered(ProblemType.TDVRP, "TDVRP/Dabia2013/n=25/C101.vrp.json"),
        _fake_discovered(ProblemType.TDVRP, "TDVRP/Dabia2013/n=50/C101.vrp.json"),
        _fake_discovered(ProblemType.TDVRPTW, "TDVRPTW/Dabia2013/n=25/C101.vrp.json"),
        _fake_discovered(ProblemType.TDVRPTW, "TDVRPTW/Dabia2013/n=50/C101.vrp.json"),
    ]
    groups = _schedule_groups(items)

    assert sorted(index for group in groups for index, _ in group) == [0, 1, 2, 3]
    grouped = {
        tuple(sorted(item.instance_path.as_posix() for _, item in group)) for group in groups
    }
    assert grouped == {
        ("benchmarks/TDVRP/Dabia2013/n=25/C101.vrp.json", "benchmarks/TDVRPTW/Dabia2013/n=25/C101.vrp.json"),
        ("benchmarks/TDVRP/Dabia2013/n=50/C101.vrp.json", "benchmarks/TDVRPTW/Dabia2013/n=50/C101.vrp.json"),
    }


def test_schedule_groups_never_split_a_shared_sidecar_at_the_size_cap() -> None:
    # A collection base with more variants than the cap: it must be split, but
    # never through a pair that shares an ATF sidecar.
    items = []
    for subinstance in ("bpr-heavy", "bpr-light", "bpr-moderate", "wave-heavy", "wave-light"):
        for problem_type in (ProblemType.TDVRP, ProblemType.TDVRPTW):
            items.append(
                _fake_discovered(
                    problem_type,
                    f"Poryos2026/{problem_type.value}/lyon/n=10/base/{subinstance}/base-{subinstance}.vrp.json",
                    base_instance_name="base",
                    place_slug="lyon",
                )
            )
    groups = _schedule_groups(items)

    assert len(groups) > 1  # 10 variants, cap is 6
    assert sorted(index for group in groups for index, _ in group) == list(range(len(items)))
    for group in groups:
        keys = [_atf_group_key(item) for _, item in group]
        # Every shared sidecar is a contiguous run inside exactly one group.
        assert keys == sorted(keys, key=keys.index)
    placement: dict[str, set[int]] = {}
    for group_index, group in enumerate(groups):
        for _, item in group:
            placement.setdefault(_atf_group_key(item), set()).add(group_index)
    assert all(len(indices) == 1 for indices in placement.values())


def test_resolve_instance_group_isolates_a_failing_instance(monkeypatch) -> None:
    items = [
        _fake_discovered(ProblemType.TDVRP, "TDVRP/Dabia2013/n=25/C101.vrp.json"),
        _fake_discovered(ProblemType.TDVRP, "TDVRP/Dabia2013/n=25/C102.vrp.json"),
    ]

    def fake_resolve(_repo, item, _atf_dir, _geometry_dir):
        if item.instance_path.name == "C101.vrp.json":
            raise ValueError("broken instance")
        return "resolved"

    monkeypatch.setattr("mamut_routing_publish.site_payloads._resolve_instance", fake_resolve)
    results = _resolve_instance_group(Path("."), list(enumerate(items)))

    assert results == [(0, None, "ValueError: broken instance"), (1, "resolved", None)]
