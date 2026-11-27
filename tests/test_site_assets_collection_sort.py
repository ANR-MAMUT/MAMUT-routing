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
    "costRatio",
    "compareCostEntries",
    "displayedCost",
    "formatCost",
    "catalogDisplayCost",
    "compareCatalogDisplayCosts",
    "lowestCostEntry",
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


@node
def test_exact_sort_breaks_display_ties_and_keeps_overflow_ahead_of_missing() -> None:
    def entry(numerator: int, display: float | None) -> dict:
        return {"cost": display, "evaluation": {"authoritative_cost": {"numerator": str(numerator), "denominator": "1"},
                                                 "display_overflow": display is None}}
    values = [entry(2**53 + 1, float(2**53)), entry(2**53, float(2**53)), entry(2**1100, None)]
    script = _extract() + f"""
    const [high, low, overflow] = {json.dumps(values)};
    const legacy = {{ cost: 2**53 }};
    const missing = lowestCostEntry({{objective_availability: [{{ cost: null }}]}});
    console.log(JSON.stringify([compareCostEntries(high,low,1), compareCostEntries(legacy,low,1),
      compareCostEntries(overflow,high,1), compareCostEntries(overflow,missing,-1)]));
    """
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
    assert json.loads(result.stdout) == [1, 0, 1, -1]


@node
def test_catalogue_badge_shows_the_exact_compact_cost_and_full_record_preserves_it() -> None:
    """The compact cost is the publisher's directly rounded string, never a rounding of the binary64 cost."""
    names = ("formatObjectiveBadge", "displayedCost", "formatCost", "costSpan", "escapeHtml", "isHierarchicalObjective")
    source = SITE_JS.read_text()
    script = "\n".join(re.search(rf"^function {n}\(.*?^\}}", source, re.S | re.M).group(0) for n in names) + """
    const sample = (cost, compact_cost, evaluation) => {
      const entry = {cost, compact_cost, evaluation, objective_function: "Duration"};
      return [formatObjectiveBadge(entry).title, displayedCost(entry), entry.cost, Number.isFinite(cost) ? cost.toFixed(2) : null];
    };
    console.log(JSON.stringify([
      sample(9150.837, "9150.84"), sample(1.135, "1.13"), sample(1.2, "1.20"), sample(0), sample(null),
      sample(2.675), sample(null, undefined, {display_overflow: true})
    ]));
    """
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
    rows = json.loads(result.stdout)
    assert [(title.removeprefix("Mono-cost objective: cost = "), full, stored) for title, full, stored, _ in rows] == [
        ("9150.84", "9150.837", 9150.837),
        # The exact value is just below 1.135, the binary64 display just above: toFixed would show 1.14.
        ("1.13", "1.135", 1.135),
        ("1.20", "1.2", 1.2),
        ("0", "0", 0),
        ("n/a", "n/a", None),
        # Without an exact value the badge shows the full binary64 display instead of a rounded one.
        ("2.675", "2.675", 2.675),
        ("Outside binary64 range", "Outside binary64 range", None),
    ]
    assert rows[1][3] == "1.14"


@node
def test_optimality_labels_show_the_claim_and_flag_an_unexpected_target() -> None:
    names = ["escapeHtml", "claimInfo", "claimBadge", "claimTooltip", "optimalityStatRows", "optimalBadgeIconHtml"]
    source = SITE_JS.read_text()
    functions = "\n".join(re.search(rf"^function {name}\(.*?^\}}", source, re.S | re.M).group(0) for name in names)
    script = functions + """
    const OPTIMAL_BADGE_ICON_PATH = "icon";
    const siteAssetHref = (path) => path;
    const base = {family_profile:"td-binary64-exact-v1", objective_function:"Duration"};
    const record = (profile) => ({...base, optimality: {status:"solver-reported-optimal", target_profile:profile}});
    const html = (entry) => JSON.stringify(optimalityStatRows(entry));
    console.log(JSON.stringify([
      html(record(base.family_profile)), html(record("synthetic-profile-v0")), html(record(undefined)), html(base),
    ]));
    """
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
    same, other, untargeted, absent = json.loads(result.stdout)
    assert "badge optimal" in same and "Solver-reported optimal" in same and "Profile warning" not in same
    assert "badge optimal" in other and "Profile warning" in other
    assert "synthetic-profile-v0" in other and "td-binary64-exact-v1" in other
    assert "Profile warning" in untargeted and "no profile" in untargeted
    assert absent == "[]"


@node
def test_history_explains_improvement_when_the_exact_delta_underflows() -> None:
    names = ("renderChangeRowBks", "escapeHtml", "isHierarchicalObjective", "costSpan", "displayedCost",
             "formatCost", "compareCostEntries", "costRatio", "renderStatGrid", "exactFractionHtml")
    source = SITE_JS.read_text()
    script = "\n".join(re.search(rf"^function {n}\(.*?^\}}", source, re.S | re.M).group(0) for n in names) + """
    const denominator = "1" + "0".repeat(6001);
    const value = (numerator, denominator) => ({cost:1, num_routes:1, evaluation:{profile:"td-binary64-exact-v1",
      benchmark_revision:"r1", authoritative_cost:{numerator,denominator}}});
    const prior = "1" + "0".repeat(6000) + "1";
    const html = renderChangeRowBks({kind:"improved", objective_function:"Duration", instance_name:"test", num_customers:1,
      prev:value(prior,denominator), new:value("1","1"), routes_delta:0, cost_delta:-0, cost_pct:-0});
    console.log(JSON.stringify([html.includes(prior),html.includes("cost decrease rounds to zero"),html.includes("Exact values")]));
    """
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
    assert json.loads(result.stdout) == [True, True, True]


@node
def test_public_catalog_sorts_the_visible_cost_and_keeps_missing_last() -> None:
    script = _extract() + """
    const row = entry => ({ objective_availability: [entry] });
    const a = row({ cost: 1.2298, compact_cost: "1.23" });
    const b = row({ cost: 1.2301, compact_cost: "1.23" });
    const overflow = row({ evaluation: { display_overflow: true } });
    const missing = row({});
    console.log(JSON.stringify([compareCatalogDisplayCosts(a, b, 1),
      compareCatalogDisplayCosts(overflow, a, -1), compareCatalogDisplayCosts(overflow, missing, -1)]));
    """
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
    assert json.loads(result.stdout) == [0, -1, -1]
