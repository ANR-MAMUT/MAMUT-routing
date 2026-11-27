from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

WORKBENCH_JS = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "mamut_routing_publish"
    / "site_assets"
    / "workbench.js"
)

MAMUT_MAP_JS = WORKBENCH_JS.with_name("mamut-map.js")

node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _extract_function(name: str) -> str:
    source = WORKBENCH_JS.read_text(encoding="utf-8")
    found = re.search(rf"^function {name}\(.*?^\}}", source, re.S | re.M)
    assert found, f"{name} not found in workbench.js"
    return found.group(0)


@node
def test_customer_markers_follow_route_visibility_and_focus() -> None:
    helper = _extract_function("customerMarkerOpacity")
    script = f"""
{helper}
const visible = new Set([0, 1]);
console.log(JSON.stringify({{
  optionOff: customerMarkerOpacity(2, visible, 0, 0.2, false),
  unassigned: customerMarkerOpacity(undefined, visible, 0, 0.2, true),
  hidden: customerMarkerOpacity(2, visible, 0, 0.2, true),
  focused: customerMarkerOpacity(0, visible, 0, 0.2, true),
  other: customerMarkerOpacity(1, visible, 0, 0.2, true),
  otherAtZero: customerMarkerOpacity(1, visible, 0, 0, true),
  noFocus: customerMarkerOpacity(1, visible, null, 0.2, true),
}}));
"""
    result = subprocess.run(
        ["node", "-e", script], capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "optionOff": 1,
        "unassigned": 1,
        "hidden": 0,
        "focused": 1,
        "other": 0.2,
        "otherAtZero": 0,
        "noFocus": 1,
    }


def test_customer_route_controls_and_popup_are_present() -> None:
    source = WORKBENCH_JS.read_text(encoding="utf-8")
    assert 'class="route-view-customers" type="checkbox"' in source
    assert "Fade/hide customers with routes" in source
    assert "state.routeView.customersFollowRoutes = event.target.checked" in source
    # Popups are DOM text nodes, never HTML strings.
    assert "if (!isDepot) lines.push(`Route: ${routeLabel}`);" in source
    assert "container.appendChild(document.createTextNode(line));" in source
    assert "bindPopup" not in source


def test_basemaps_are_keyed_vector_carto_with_osm_fallback_and_linked_attribution() -> None:
    # The basemap code now lives in the shared map kit; the CARTO helpers are
    # exercised in node by tests/test_map_assets.py.
    source = WORKBENCH_JS.read_text(encoding="utf-8")
    kit = MAMUT_MAP_JS.read_text(encoding="utf-8")
    for text in (source, kit):
        # No unkeyed CARTO raster tile template may survive: it draws a watermark.
        assert "basemaps.cartocdn.com/light_all" not in text
        assert "basemaps.cartocdn.com/dark_all" not in text
        assert "rastertiles" not in text
        assert "{s}.tile.openstreetmap.org" not in text
    assert 'const basemapApiKey = body.dataset.basemapApiKey || "";' in source
    assert "apiKey: basemapApiKey," in source
    assert not re.search(r"\bL\.[a-zA-Z]", source) and "leaflet" not in source.lower()
    assert '{ id: "positron", label: "Positron", carto: "positron-gl-style" }' in kit
    assert '{ id: "dark-matter", label: "Dark Matter", carto: "dark-matter-gl-style" }' in kit
    assert "transformRequest: (url) => withBasemapKey(url, apiKey)" in kit
    assert 'href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' in kit
    assert 'href="https://carto.com/attributions">CARTO</a>' in kit


def test_route_rendering_controls_replace_unused_filters() -> None:
    source = WORKBENCH_JS.read_text(encoding="utf-8")
    assert 'class="route-view-render"' in source
    assert '<option value="straight_line">Straight lines</option>' in source
    assert '<option value="cached_road"' in source
    assert 'class="route-view-depot-opacity" type="range"' in source
    assert 'state.routeView.renderMode = event.target.value' in source
    assert '<summary>Filters' not in source
    assert 'data-route-filter=' not in source


def test_the_webgl2_notice_does_not_count_as_a_running_animation() -> None:
    """state.animation also holds the "needs WebGL2" notice (so that it closes with the solution):
    dimming the routes, the button label and the reopen-on-rerender follow animationPlaying()."""
    source = WORKBENCH_JS.read_text(encoding="utf-8")
    assert "return Boolean(state.animation && !state.animation.unavailable);" in source
    assert "dim: animationPlaying() ? 0.35 : 1," in source
    assert '${animationPlaying() ? "Stop animation" : "Animate"}' in source
    assert "const reopen = animationPlaying() &&" in source
    for stale in ("dim: state.animation ?", 'state.animation ? "Stop animation"', "reopen = Boolean(state.animation)"):
        assert stale not in source


@node
def test_catalog_groups_preserve_legacy_counts_and_load_only_requested_families() -> None:
    source = WORKBENCH_JS.read_text(encoding="utf-8")
    loader = re.search(r"^async function loadWorkbenchCatalogGroup\(.*?^\}", source, re.S | re.M)
    assert loader
    helpers = "\n".join(_extract_function(name) for name in (
        "benchmarkCatalogLocator", "benchmarkCatalogGroupKey", "buildBenchmarkCatalogGroups",
    ))
    script = helpers + "\n" + loader.group(0) + """
const assert = require("node:assert/strict");
const row = (family, city) => ({
  locator: { problem_type: "CVRP", benchmark_name: family, place_slug: city },
  route_path: "/" + family + "/" + city,
});
const a = row("A", "Paris"), b = row("B", "Lyon"), noMap = row("C", null);
const legacy = buildBenchmarkCatalogGroups({ items: [a, a, b, noMap] });
const groups = buildBenchmarkCatalogGroups({ shards: ["A", "B", "C"].map(family => ({
  problem: "CVRP", family, workbench_count: family === "C" ? 0 : 1,
})) });
for (const map of [groups, legacy]) {
  assert.deepEqual([...map].map(([key, g]) => [key, g.count]), [["CVRP::A", 1], ["CVRP::B", 1]]);
}
const state = { benchmarkCatalog: { groups, selectedGroupKey: "CVRP::A" } };
const requests = new Map();
const rendered = [];
function fetchBenchmarkCatalogShard(shard) {
  assert(!requests.has(shard.family));
  return new Promise(resolve => requests.set(shard.family, resolve));
}
function renderBenchmarkCatalogOptions() { rendered.push(state.benchmarkCatalog.selectedGroupKey); }
function syncWorkbenchUrl() {}
(async () => {
  const first = loadWorkbenchCatalogGroup(groups.get("CVRP::A"));
  assert.deepEqual([...requests.keys()], ["A"]);
  await loadWorkbenchCatalogGroup(groups.get("CVRP::A"));
  state.benchmarkCatalog.selectedGroupKey = "CVRP::B";
  const second = loadWorkbenchCatalogGroup(groups.get("CVRP::B"));
  requests.get("B")([b]);
  await second;
  requests.get("A")([a, noMap]);
  await first;
  assert.deepEqual(rendered, ["CVRP::B"]);
  assert.deepEqual(groups.get("CVRP::A").items, [a]);
})().catch(error => { console.error(error); process.exitCode = 1; });
"""
    subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True, timeout=30)
