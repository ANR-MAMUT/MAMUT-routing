"""Collection pages sort by BKS cost and route count without crashing.

``compareCollectionItems`` called ``publicCatalogObjectiveNumber``, a function
renamed away long ago, so choosing "BKS cost" or "Routes" -- or opening a link
carrying ``?sort=cost`` / ``?sort=routes`` -- threw a ReferenceError and every
collection page showed "Unable to load page". The comparator is extracted from
the asset and run under node against a stubbed ``state``.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

SITE_JS = Path(__file__).resolve().parents[1] / "src" / "mamut_routing_publish" / "site_assets" / "site.js"
FUNCTIONS = (
    "minOf",
    "compareCatalogNumber",
    "normalizeCollectionSort",
    "collectionObjectiveNumber",
    "compareCollectionItems",
)

node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")

ITEMS = [
    {"display_name": "b-n20", "num_customers": 20, "objective_availability": [{"objective_function": "MonoCost", "cost": 30.5, "num_routes": 3}]},
    {"display_name": "a-n10", "num_customers": 10, "objective_availability": [{"objective_function": "MonoCost", "cost": 99.0, "num_routes": 2}]},
    {"display_name": "c-n10", "num_customers": 10, "objective_availability": []},
    {
        "display_name": "d-n30",
        "num_customers": 30,
        "objective_availability": [
            {"objective_function": "MonoCost", "cost": 10.0, "num_routes": 5},
            {"objective_function": "HierarchicalVehicleCost", "cost": 50.0, "num_routes": 1},
        ],
    },
]


def _extract() -> str:
    source = SITE_JS.read_text(encoding="utf-8")
    parts = []
    for name in FUNCTIONS:
        found = re.search(rf"^function {name}\(.*?^\}}", source, re.S | re.M)
        assert found, f"{name} not found in site.js"
        parts.append(found.group(0))
    return "\n\n".join(parts)


def _sorted_names(sort: str, objective: str = "") -> list[str]:
    script = _extract() + "\n" + textwrap.dedent(
        f"""
        const state = {{ collectionFilters: {{ sort: normalizeCollectionSort({json.dumps(sort)}), objective_function: {json.dumps(objective)} }} }};
        const items = {json.dumps(ITEMS)};
        console.log(JSON.stringify(items.slice().sort(compareCollectionItems).map((item) => item.display_name)));
        """
    )
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_the_renamed_helper_is_gone() -> None:
    assert "publicCatalogObjectiveNumber" not in SITE_JS.read_text(encoding="utf-8")


@node
def test_default_and_name_sorts() -> None:
    assert _sorted_names("size-name") == ["a-n10", "c-n10", "b-n20", "d-n30"]
    assert _sorted_names("name") == ["a-n10", "b-n20", "c-n10", "d-n30"]


@node
def test_cost_and_routes_put_missing_bks_last() -> None:
    assert _sorted_names("cost") == ["d-n30", "b-n20", "a-n10", "c-n10"]
    assert _sorted_names("routes") == ["d-n30", "a-n10", "b-n20", "c-n10"]


@node
def test_cost_respects_the_objective_filter() -> None:
    assert _sorted_names("cost", "HierarchicalVehicleCost") == ["d-n30", "a-n10", "c-n10", "b-n20"]


@node
def test_unknown_sort_values_fall_back_to_the_default() -> None:
    assert _sorted_names("bogus") == _sorted_names("size-name")
