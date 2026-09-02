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
    assert 'const routeDetail = isDepot ? "" : `<br/>Route: ${routeLabel}`;' in source


@node
def test_carto_basemap_helpers_build_keyed_urls() -> None:
    helpers = "\n".join(_extract_function(name) for name in ("cartoStyleUrl", "withBasemapKey"))
    script = f"""
{helpers}
console.log(JSON.stringify({{
  style: cartoStyleUrl("positron-gl-style", "k_1-2"),
  styleEncoded: cartoStyleUrl("dark-matter-gl-style", "a b"),
  tiles: withBasemapKey("https://tiles.basemaps.cartocdn.com/vector/carto.streets/v1/3/4/2.mvt", "k_1"),
  glyphs: withBasemapKey("https://tiles.basemaps.cartocdn.com/fonts/Open%20Sans/0-255.pbf", "k_1"),
  alreadyKeyed: withBasemapKey("https://basemaps.cartocdn.com/gl/positron-gl-style/style.json?key=other", "k_1"),
  otherHost: withBasemapKey("https://tile.openstreetmap.org/1/2/3.png", "k_1"),
  lookalike: withBasemapKey("https://basemaps.cartocdn.com.evil.example/x", "k_1"),
  noKey: withBasemapKey("https://tiles.basemaps.cartocdn.com/x", ""),
  relative: withBasemapKey("/local/asset.json", "k_1"),
}}));
"""
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "style": "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json?key=k_1-2",
        "styleEncoded": "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json?key=a%20b",
        "tiles": {"url": "https://tiles.basemaps.cartocdn.com/vector/carto.streets/v1/3/4/2.mvt?key=k_1"},
        "glyphs": {"url": "https://tiles.basemaps.cartocdn.com/fonts/Open%20Sans/0-255.pbf?key=k_1"},
        "alreadyKeyed": {"url": "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json?key=other"},
        "otherHost": {"url": "https://tile.openstreetmap.org/1/2/3.png"},
        "lookalike": {"url": "https://basemaps.cartocdn.com.evil.example/x"},
        "noKey": {"url": "https://tiles.basemaps.cartocdn.com/x"},
        "relative": {"url": "/local/asset.json"},
    }


def test_basemaps_are_keyed_vector_carto_with_osm_fallback_and_linked_attribution() -> None:
    source = WORKBENCH_JS.read_text(encoding="utf-8")
    # No unkeyed CARTO raster tile template may survive: it draws a watermark.
    assert "basemaps.cartocdn.com/light_all" not in source
    assert "basemaps.cartocdn.com/dark_all" not in source
    assert "rastertiles" not in source
    assert "{s}.tile.openstreetmap.org" not in source
    assert 'const basemapApiKey = body.dataset.basemapApiKey || "";' in source
    assert 'cartoVectorLayer("positron-gl-style", basemapApiKey)' in source
    assert 'cartoVectorLayer("dark-matter-gl-style", basemapApiKey)' in source
    assert "transformRequest: (url) => withBasemapKey(url, key)" in source
    assert 'href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' in source
    assert 'href="https://carto.com/attributions">CARTO</a>' in source
    assert "const baseLayers = { OpenStreetMap: osmBaseLayer };" in source
