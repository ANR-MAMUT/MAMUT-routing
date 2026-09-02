"""The website writes classic CVRPLIB ``.vrp`` files in the browser; the
JavaScript writer in ``site.js`` must produce the same bytes as the Python
writer in ``mamut_routing_lib.cvrplib`` (the CLI, the tools GUI). These tests
lift the pure functions out of the asset and run them under node against the
Python output for the same instance JSON. They skip when node is absent."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from mamut_routing_lib.cvrplib import VrpExportOptions, instance_to_vrp_text
from mamut_routing_lib.models import (
    BenchmarkInstance,
    BenchmarkInstanceCVRP,
    BenchmarkInstanceCVRPCollection,
    BenchmarkInstanceVRPTWCollection,
)

SITE_JS = Path(__file__).resolve().parents[1] / "src" / "mamut_routing_publish" / "site_assets" / "site.js"

VRP_FUNCTIONS = (
    "vrpIsIntegral",
    "vrpFormatFloat",
    "vrpVectorFormatter",
    "vrpCoordinateFormatter",
    "vrpEuclideanArcCosts",
    "vrpMetadataValue",
    "vrpIsCollection",
    "vrpIsVrptw",
    "vrpMetricVariant",
    "vrpCollectionDecimals",
    "vrpComment",
    "instanceToVrpText",
    "instanceToSolomonText",
    "vrpExportKinds",
    "vrpExportFilename",
)

node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _extract() -> str:
    source = SITE_JS.read_text(encoding="utf-8")
    parts = [match.group(0) for match in re.finditer(r"^const VRP_[A-Z_]+ = .*$", source, re.M)]
    assert parts, "VRP_* constants not found in site.js"
    for name in VRP_FUNCTIONS:
        found = re.search(rf"^function {name}\(.*?^\}}", source, re.S | re.M)
        assert found, f"{name} not found in site.js"
        parts.append(found.group(0))
    return "\n\n".join(parts)


def _run_js(script: str, payload: dict) -> dict:
    bundle = _extract() + "\n" + script
    result = subprocess.run(
        ["node", "-e", bundle], input=json.dumps(payload), capture_output=True, text=True, timeout=120
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


_JS_DRIVER = """
const input = JSON.parse(require("fs").readFileSync(0, "utf-8"));
const out = {};
for (const [key, entry] of Object.entries(input.cases)) {
  if (entry.kind === "solomon") {
    out[key] = instanceToSolomonText(entry.instance);
  } else {
    out[key] = instanceToVrpText(entry.instance, entry.arcCosts ?? null, entry.options ?? {});
  }
}
out.kinds = Object.fromEntries(Object.entries(input.kinds).map(([key, instance]) => [key, vrpExportKinds(instance).map((k) => k.kind)]));
out.filenames = input.filenames.map(([path, kind]) => vrpExportFilename(path, kind));
process.stdout.write(JSON.stringify(out));
"""


def _toy_cvrp() -> dict:
    return {
        "instance_name": "poryos-n2-testcvrp",
        "instance_origin": "OsmCvrpGen",
        "benchmark_name": "Poryos2026",
        "num_customers": 2,
        "num_vehicles": None,
        "vehicle_capacity": 10,
        "coordinates": [[0.0, 0.0], [1.0, 1.0], [2.0, 2.0]],
        "demands": [0, 3, 4],
        "depot": 0,
        "arc_costs": [[0, 5, 6], [5, 0, 3], [6, 3, 0]],
        "metadata": {"authors": "Florian Rascoussier (0nyr) and Adrien Pichon (Anzury)", "metric_variant": "fastest"},
    }


def _sintef_like() -> dict:
    return {
        "instance_name": "C101",
        "instance_origin": "Solomon1987",
        "benchmark_name": "Sintef2008",
        "num_customers": 3,
        "num_vehicles": 25,
        "vehicle_capacity": 200,
        "coordinates": [[40, 50], [45, 68], [45, 70], [42, 66]],
        "demands": [0, 10, 30, 10],
        "service_times": [0, 90, 90, 90],
        "time_windows": [[0, 1236], [912, 967], [825, 870], [65, 146]],
        "depot": 0,
        "arc_costs": [
            [0.0, 18.681541692269406, 20.615528128088304, 16.1245154965971],
            [18.681541692269406, 0.0, 2.0, 3.605551275463989],
            [20.615528128088304, 2.0, 0.0, 5.0],
            [16.1245154965971, 3.605551275463989, 5.0, 0.0],
        ],
        "metadata": {"metric_variant": "euclidean", "authors": "Marius M. Solomon"},
    }


def _collection(*, metric: str, family: str = "Mamut2026", vrptw: bool = False, source: dict | None = None) -> dict:
    payload = {
        "instance_name": "mamut-testville-n3-k2-poi",
        "instance_origin": "OsmCvrpGen",
        "benchmark_name": family,
        "num_customers": 3,
        "num_vehicles": None,
        "vehicle_capacity": 7,
        "coordinates": [[-500.874011, 70.822412], [3.0, 4.0], [-1.5, 2.25], [1234.5678901234, -0.000001]],
        "demands": [0, 3, 4, 2],
        "depot": 0,
        "reference_lla": {"lat": 45.0, "lon": 5.0, "alt": 0.0},
        "metric_variant": metric,
        "arc_costs_source": source or {"model": "euclidean", "decimals": 3},
        "metadata": {"problem_type": "VRPTW" if vrptw else "CVRP", "city": "testville", "num_vehicles_lb": 2},
    }
    if vrptw:
        payload["service_times"] = [0, 60, 90, 30]
        payload["time_windows"] = [[0, 3600], [100, 2000], [0, 3000], [10.5, 20.25]]
        payload["metadata"]["tw_set"] = {"name": "spread", "td_paired": False}
    return payload


_SIDECAR_VALUES = [
    [0.0, 10.5, 20.25, 7.0],
    [11.0, 0.0, 7.125, 3.5],
    [19.0, 8.0, 0.0, 2.001],
    [7.0, 3.5, 2.0, 0.0],
]


def _python_cases() -> tuple[dict, dict]:
    """(node input, expected texts from the Python writer)."""
    sidecar_source = {"model": "distances-sidecar", "distances": {"path": "sidecars/x.distances-shortest.json.gz", "sha256": None}}
    toy = _toy_cvrp()
    sintef = _sintef_like()
    mamut_euclid = _collection(metric="euclidean")
    poryos_vrptw = _collection(metric="shortest", family="Poryos2026", vrptw=True, source=sidecar_source)
    poryos_vrptw["instance_name"] = "poryos-testville-n3-poi-tw-spread"

    cases = {
        "toy_int_cvrp": {"instance": toy},
        "sintef_float_matrix_vrptw": {"instance": sintef},
        "sintef_euc_2d": {"instance": sintef, "options": {"edgeWeightType": "EUC_2D"}},
        "sintef_custom_comment": {"instance": sintef, "options": {"comment": "hand-written"}},
        "sintef_solomon": {"instance": sintef, "kind": "solomon"},
        "mamut_euclidean_collection": {"instance": mamut_euclid, "arcCosts": None, "options": {"decimals": 3}},
        "mamut_euclidean_euc_2d": {"instance": mamut_euclid, "options": {"edgeWeightType": "EUC_2D"}},
        "poryos_sidecar_vrptw": {"instance": poryos_vrptw, "arcCosts": _SIDECAR_VALUES, "options": {"decimals": 3}},
    }
    # The euclidean collection matrix is computed on both sides from the coordinates.
    from mamut_routing_lib.cvrplib import euclidean_arc_costs

    cases["mamut_euclidean_collection"]["arcCosts"] = None
    node_cases = json.loads(json.dumps(cases))
    node_cases["mamut_euclidean_collection"]["arcCosts"] = None

    expected = {
        "toy_int_cvrp": instance_to_vrp_text(BenchmarkInstanceCVRP(**toy)),
        "sintef_float_matrix_vrptw": instance_to_vrp_text(BenchmarkInstance(**sintef)),
        "sintef_euc_2d": instance_to_vrp_text(BenchmarkInstance(**sintef), options=VrpExportOptions(edge_weight_type="EUC_2D")),
        "sintef_custom_comment": instance_to_vrp_text(BenchmarkInstance(**sintef), options=VrpExportOptions(comment="hand-written")),
        "sintef_solomon": instance_to_vrp_text(BenchmarkInstance(**sintef), options=VrpExportOptions(format="solomon")),
        "mamut_euclidean_collection": instance_to_vrp_text(BenchmarkInstanceCVRPCollection(**mamut_euclid)),
        "mamut_euclidean_euc_2d": instance_to_vrp_text(
            BenchmarkInstanceCVRPCollection(**mamut_euclid), options=VrpExportOptions(edge_weight_type="EUC_2D")
        ),
        "poryos_sidecar_vrptw": instance_to_vrp_text(BenchmarkInstanceVRPTWCollection(**poryos_vrptw), _SIDECAR_VALUES),
    }
    # In the browser the euclidean matrix comes from vrpEuclideanArcCosts; feed
    # node the same formula's output computed in JS by leaving arcCosts null
    # and letting the driver compute it.
    node_input = {
        "cases": node_cases,
        "kinds": {
            "toy": toy,
            "sintef": sintef,
            "mamut_euclid": mamut_euclid,
            "poryos_vrptw_shortest": poryos_vrptw,
            "td": {"instance_name": "RC202", "td": {"model": "atf-ndcpwlf"}, "coordinates": [[0, 0], [1, 1]]},
        },
        "filenames": [
            ["benchmarks/VRPTW/Sintef2008/n=400/R1_4_6.vrp.json", "explicit"],
            ["benchmarks/VRPTW/Sintef2008/n=400/R1_4_6.vrp.json", "solomon"],
        ],
    }
    assert euclidean_arc_costs(mamut_euclid["coordinates"])[0][1] == round((503.874011**2 + 66.822412**2) ** 0.5, 3)
    return node_input, expected


_JS_DRIVER_WITH_EUCLID = _JS_DRIVER.replace(
    'out[key] = instanceToVrpText(entry.instance, entry.arcCosts ?? null, entry.options ?? {});',
    """let arcCosts = entry.arcCosts ?? null;
    const opts = entry.options ?? {};
    if (arcCosts === null && (opts.edgeWeightType || "EXPLICIT") === "EXPLICIT" && vrpIsCollection(entry.instance)) {
      arcCosts = vrpEuclideanArcCosts(entry.instance.coordinates, vrpCollectionDecimals(entry.instance));
    } else if (arcCosts === null && (opts.edgeWeightType || "EXPLICIT") === "EXPLICIT") {
      arcCosts = entry.instance.arc_costs;
    }
    out[key] = instanceToVrpText(entry.instance, arcCosts, opts);""",
)


@node
def test_javascript_writer_matches_the_python_writer_byte_for_byte() -> None:
    node_input, expected = _python_cases()
    produced = _run_js(_JS_DRIVER_WITH_EUCLID, node_input)
    for key, text in expected.items():
        assert produced[key] == text, f"{key}: JS output differs from Python\n{produced[key]}\n---\n{text}"
    assert produced["kinds"] == {
        "toy": ["explicit"],
        "sintef": ["explicit", "euc2d", "solomon"],
        "mamut_euclid": ["explicit", "euc2d"],
        "poryos_vrptw_shortest": ["explicit"],
        "td": [],
    }
    assert produced["filenames"] == ["R1_4_6.vrp", "R1_4_6.txt"]


def test_site_js_exposes_the_export_chips_and_handler() -> None:
    source = SITE_JS.read_text(encoding="utf-8")
    assert 'data-vrp-export="${entry.kind}"' in source
    assert "renderVrpExportChips(rawInstance" in source
    assert 'closest("[data-vrp-export]")' in source
    assert 'new DecompressionStream("gzip")' in source
    assert "artifact_distances_path" in source
    # The record page no longer links the (optional, sometimes missing) committed .vrp directly.
    assert 'artifactHref(payload.artifact_links.vrp_path)' not in source
