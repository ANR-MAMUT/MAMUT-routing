"""The route vectors published for reimplementations of the TD fold price as stated on the data.

``MAMUT-routing-lib/tests/fixtures/td/fold-v2-vectors.json`` lists published
BKS routes with their td-fold/2 duration and optimal departure time (the lib
checks its micro vectors itself; these need the benchmark trees).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mamut_routing_lib.td.checker import compute_route_duration
from mamut_routing_lib.td.reprice import load_td_instance_for_routes

REPO_ROOT = Path(__file__).resolve().parents[1]
BENCHMARKS = REPO_ROOT / "benchmarks"
VECTORS = json.loads(
    (REPO_ROOT / "MAMUT-routing-lib" / "tests" / "fixtures" / "td" / "fold-v2-vectors.json").read_text(encoding="utf-8")
)
PRESENT = [vector for vector in VECTORS["routes"] if (BENCHMARKS / vector["instance"]).is_file()]


@pytest.mark.skipif(not PRESENT, reason="benchmark satellites not checked out")
@pytest.mark.parametrize("vector", PRESENT, ids=[f"{v['tree']}:{Path(v['instance']).name}" for v in PRESENT])
def test_route_vector_prices_as_published(vector: dict) -> None:
    loaded = load_td_instance_for_routes(BENCHMARKS / vector["instance"], [vector["route"]])
    evaluation = compute_route_duration(loaded.instance, loaded.atfs, vector["route"])
    assert evaluation.feasible
    assert (evaluation.duration, evaluation.departure_time) == (
        vector["expected"]["duration"],
        vector["expected"]["departure_time"],
    )
