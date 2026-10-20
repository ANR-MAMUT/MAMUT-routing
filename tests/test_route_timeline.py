"""Workbench animation timelines published next to collection instance pages."""

from __future__ import annotations

import json
from pathlib import Path

from mamut_routing_lib.artifacts import load_benchmark_instance
from mamut_routing_lib.enums import ObjectiveFunction
from mamut_routing_lib.json_utils import save_json_to_file
from mamut_routing_lib.models import BenchmarkBKS
from mamut_routing_publish.route_timeline import (
    RouteTimelinePayload,
    build_route_timeline,
    clear_route_timeline_memo,
)
from mamut_routing_publish.site_payloads import generate_site_payloads
from test_site_payloads import _COLLECTION_BASE, _COLLECTION_CITY, build_collection_fixture


def _bks(path: Path, routes: list[list[int]], cost: float) -> None:
    save_json_to_file(
        BenchmarkBKS(
            instance_name=path.name.split(".bks.")[0],
            routes=routes,
            cost=cost,
            objective_function=ObjectiveFunction.MONO_COST,
            metadata={"authors": "fixture"},
        ).model_dump(mode="json"),
        path,
    )


def _page(payload_root: Path, problem: str, metric: str, base: str) -> dict:
    page = payload_root / "benchmarks" / problem / "poryos2026" / metric / _COLLECTION_CITY / "n=2" / base / "index.json"
    return json.loads(page.read_text(encoding="utf-8"))


def _timeline(site_output: Path, entry: dict) -> dict:
    path = site_output / "site-payloads" / entry["timeline_path"].strip("/")
    payload = json.loads(path.read_text(encoding="utf-8"))
    RouteTimelinePayload.model_validate(payload)
    return payload


def test_collection_bks_pages_link_checker_faithful_timelines(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    collection = build_collection_fixture(repo)
    # A BKS on the euclidean sibling (no time of its own) and one on the VRPTW variant.
    euclidean_dir = collection / "CVRP" / "euclidean" / _COLLECTION_CITY / "n=2" / _COLLECTION_BASE
    _bks(euclidean_dir / f"{_COLLECTION_BASE}.bks.MonoCost.json", [[1, 2]], 20.0)
    vrptw_dir = collection / "VRPTW" / "fastest" / _COLLECTION_CITY / "n=2" / _COLLECTION_BASE
    _bks(vrptw_dir / f"{_COLLECTION_BASE}.bks.MonoCost.json", [[1, 2]], 491.5)

    site_output = repo / "dist"
    generate_site_payloads(repo, source_commit="fixture123", site_output_dir=site_output)
    payload_root = site_output / "site-payloads"

    # CVRP on its own fastest metric: free-flow seconds, no waiting, no service.
    cvrp_entry = _page(payload_root, "cvrp", "fastest", _COLLECTION_BASE)["bks_entries"][0]
    route_path = f"/benchmarks/cvrp/poryos2026/fastest/{_COLLECTION_CITY}/n=2/{_COLLECTION_BASE}/"
    assert cvrp_entry["timeline_path"] == f"{route_path}timeline.MonoCost.json"
    assert cvrp_entry["timeline_clock"] == "free_flow_fastest"
    cvrp = _timeline(site_output, cvrp_entry)
    assert cvrp["route_path"] == route_path and cvrp["clock_metric"] == "fastest"
    assert cvrp["routes"] == [
        {"departure": 0.0, "return_arrival": 491.5, "stops": [[1, 120.5, 120.5, 120.5], [2, 251.25, 251.25, 251.25]]}
    ]

    # The euclidean BKS borrows the base's fastest clock: same stops, same times.
    euclidean_entry = _page(payload_root, "cvrp", "euclidean", _COLLECTION_BASE)["bks_entries"][0]
    assert euclidean_entry["timeline_clock"] == "free_flow_fastest"
    assert _timeline(site_output, euclidean_entry)["routes"] == cvrp["routes"]

    # VRPTW: the checker's schedule, with service times.
    vrptw_entry = _page(payload_root, "vrptw", "fastest", _COLLECTION_BASE)["bks_entries"][0]
    assert vrptw_entry["timeline_clock"] == "checker"
    assert _timeline(site_output, vrptw_entry)["routes"] == [
        {"departure": 0.0, "return_arrival": 511.5, "stops": [[1, 120.5, 120.5, 130.5], [2, 261.25, 261.25, 271.25]]}
    ]


def test_no_timeline_without_a_shipped_fastest_matrix(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    collection = build_collection_fixture(repo)
    euclidean_path = collection / "CVRP" / "euclidean" / _COLLECTION_CITY / "n=2" / _COLLECTION_BASE / f"{_COLLECTION_BASE}.vrp.json"
    instance = load_benchmark_instance(euclidean_path)
    # The fastest sibling is gone (as for Mamut2026 tiers above n = 1000).
    (collection / "CVRP" / "fastest" / _COLLECTION_CITY / "n=2" / _COLLECTION_BASE / f"{_COLLECTION_BASE}.vrp.json").unlink()
    clear_route_timeline_memo()
    assert build_route_timeline(instance, euclidean_path, [[1, 2]], ObjectiveFunction.MONO_COST, "/x/") is None
