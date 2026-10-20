"""Node tests for the shared MapLibre kit (site_assets/mamut-map.js).

The file is a classic script shared byte-for-byte with the MAMUT-routing-tools GUI.
It is loaded here in a bare ``vm`` context (no ``window``, no DOM) to check that it has
no load-time side effects other than ``MamutMap``, and to exercise its pure helpers.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

MAMUT_MAP_JS = (
    Path(__file__).resolve().parents[1] / "src" / "mamut_routing_publish" / "site_assets" / "mamut-map.js"
)

node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _run(body: str) -> object:
    script = f"""
const fs = require("fs");
const vm = require("vm");
const context = vm.createContext({{ URL, console }});
const before = new Set(Object.getOwnPropertyNames(context));
vm.runInContext(fs.readFileSync({json.dumps(str(MAMUT_MAP_JS))}, "utf8"), context);
const leaked = Object.getOwnPropertyNames(context).filter((name) => !before.has(name));
const M = context.MamutMap;
const result = (() => {{ {body} }})();
console.log(JSON.stringify(result));
"""
    completed = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=60)
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


@node
def test_loading_exposes_only_the_namespace() -> None:
    assert _run("return leaked;") == ["MamutMap"]


@node
def test_carto_basemap_helpers_build_keyed_urls() -> None:
    assert _run(
        """
return {
  style: M.cartoStyleUrl("positron-gl-style", "k_1-2"),
  styleEncoded: M.cartoStyleUrl("dark-matter-gl-style", "a b"),
  tiles: M.withBasemapKey("https://tiles.basemaps.cartocdn.com/vector/carto.streets/v1/3/4/2.mvt", "k_1"),
  glyphs: M.withBasemapKey("https://tiles.basemaps.cartocdn.com/fonts/Open%20Sans/0-255.pbf", "k_1"),
  alreadyKeyed: M.withBasemapKey("https://basemaps.cartocdn.com/gl/positron-gl-style/style.json?key=other", "k_1"),
  otherHost: M.withBasemapKey("https://tile.openstreetmap.org/1/2/3.png", "k_1"),
  lookalike: M.withBasemapKey("https://basemaps.cartocdn.com.evil.example/x", "k_1"),
  noKey: M.withBasemapKey("https://tiles.basemaps.cartocdn.com/x", ""),
  relative: M.withBasemapKey("/local/asset.json", "k_1"),
};
"""
    ) == {
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


@node
def test_basemap_choice_follows_theme_and_key() -> None:
    assert _run(
        """
return {
  withKey: M.availableBasemaps("k").map((b) => b.id),
  withoutKey: M.availableBasemaps("").map((b) => b.id),
  dark: M.themedBasemapId(true, "k"),
  light: M.themedBasemapId(false, "k"),
  noKey: M.themedBasemapId(true, ""),
  osm: M.osmRasterStyle(),
};
"""
    ) == {
        "withKey": ["positron", "dark-matter", "osm"],
        "withoutKey": ["osm"],
        "dark": "dark-matter",
        "light": "positron",
        "noKey": "osm",
        "osm": {
            "version": 8,
            "sources": {
                "basemap-osm": {
                    "type": "raster",
                    "tiles": ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
                    "tileSize": 256,
                    "maxzoom": 19,
                    "attribution": '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
                }
            },
            "layers": [{"id": "basemap-osm", "type": "raster", "source": "basemap-osm"}],
        },
    }


@node
def test_route_feature_style_ports_the_leaflet_rules() -> None:
    assert _run(
        """
const view = (extra) => Object.assign({ visibleRoutes: new Set([0, 1]), focusedRoute: null, fadedOpacity: 0.2,
  depotLegOpacity: 0.25, routeMode: "straight_line", roadOpacity: 0.88 }, extra);
return {
  hidden: M.routeFeatureStyle(2, "body", view({})),
  straight: M.routeFeatureStyle(0, "body", view({})),
  straightLeg: M.routeFeatureStyle(0, "depot", view({})),
  road: M.routeFeatureStyle(0, "body", view({ routeMode: "cached_road" })),
  roadLegNotFaded: M.routeFeatureStyle(0, "depot", view({ routeMode: "cached_road" })),
  mixedIsRoad: M.routeFeatureStyle(0, "body", view({ routeMode: "mixed", roadOpacity: 0.9 })),
  focused: M.routeFeatureStyle(0, "body", view({ focusedRoute: 0 })),
  other: M.routeFeatureStyle(1, "body", view({ focusedRoute: 0 })),
  otherLeg: M.routeFeatureStyle(1, "depot", view({ focusedRoute: 0, depotLegOpacity: 0.1 })),
  otherAtZero: M.routeFeatureStyle(1, "body", view({ focusedRoute: 0, fadedOpacity: 0 })),
  focusOnHidden: M.routeFeatureStyle(1, "body", view({ focusedRoute: 5 })),
  legAtZero: M.routeFeatureStyle(0, "depot", view({ depotLegOpacity: 0 })),
};
"""
    ) == {
        "hidden": {"o": 0, "w": 3},
        "straight": {"o": 0.78, "w": 3},
        "straightLeg": {"o": 0.25, "w": 3},
        "road": {"o": 0.88, "w": 3},
        "roadLegNotFaded": {"o": 0.88, "w": 3},
        "mixedIsRoad": {"o": 0.9, "w": 3},
        "focused": {"o": 0.78, "w": 5},
        "other": {"o": 0.2, "w": 3},
        "otherLeg": {"o": 0.1, "w": 3},
        "otherAtZero": {"o": 0, "w": 3},
        "focusOnHidden": {"o": 0.78, "w": 3},
        "legAtZero": {"o": 0, "w": 3},
    }


@node
def test_route_features_split_body_and_depot_legs() -> None:
    result = _run(
        """
const lines = [
  { routeIndex: 0, segments: [[[0, 0], [1, 0]], [[1, 0], [2, 0]], [[2, 0], [3, 0]], [[3, 0], [0, 0]]] },
  { routeIndex: 1, segments: [[[0, 0], [5, 5]], [[5, 5], [0, 0]]] },
  { routeIndex: 21, coordinates: [[0, 0], [7, 7], [0, 0]] },
  { routeIndex: 3, segments: [[[0, 0]]] },
];
return M.buildRouteFeatures(lines).map((f) => ({ id: f.id, props: f.properties, type: f.geometry.type, coords: f.geometry.coordinates }));
"""
    )
    assert result == [
        {"id": 0, "props": {"r": 0, "leg": "body", "slot": 0}, "type": "LineString", "coords": [[1, 0], [2, 0], [3, 0]]},
        {
            "id": 1,
            "props": {"r": 0, "leg": "depot", "slot": 0},
            "type": "MultiLineString",
            "coords": [[[0, 0], [1, 0]], [[3, 0], [0, 0]]],
        },
        # One customer: no interior arc, both arcs are depot legs.
        {
            "id": 3,
            "props": {"r": 1, "leg": "depot", "slot": 1},
            "type": "MultiLineString",
            "coords": [[[0, 0], [5, 5]], [[5, 5], [0, 0]]],
        },
        # No per-arc segments: one body feature, slot wraps at 20.
        {"id": 42, "props": {"r": 21, "leg": "body", "slot": 1}, "type": "LineString", "coords": [[0, 0], [7, 7], [0, 0]]},
    ]


@node
def test_ranked_thinning_matches_douglas_peucker_at_every_tolerance() -> None:
    result = _run(
        """
// A wiggly line ~ 2 km long near the equator (1e-5 deg ~ 1.1 m).
const points = [];
for (let i = 0; i <= 400; i += 1) points.push([i * 5e-5, Math.sin(i / 7) * 2e-4 + (i % 3) * 3e-6]);
function dp(pts, tol) {
  const lat0 = pts[0][1] * Math.PI / 180, R = 6371008.8;
  const kx = Math.PI / 180 * R * Math.cos(lat0), ky = Math.PI / 180 * R;
  const keep = new Array(pts.length).fill(false); keep[0] = keep[pts.length - 1] = true;
  (function rec(a, b) {
    let best = -1, bestD = tol;
    const ax = pts[a][0] * kx, ay = pts[a][1] * ky, bx = pts[b][0] * kx, by = pts[b][1] * ky;
    const dx = bx - ax, dy = by - ay, l2 = dx * dx + dy * dy;
    for (let i = a + 1; i < b; i += 1) {
      let px = pts[i][0] * kx - ax, py = pts[i][1] * ky - ay;
      if (l2 > 0) { const t = Math.max(0, Math.min(1, (px * dx + py * dy) / l2)); px -= t * dx; py -= t * dy; }
      const d = Math.sqrt(px * px + py * py);
      if (d > bestD) { bestD = d; best = i; }
    }
    if (best >= 0) { keep[best] = true; rec(a, best); rec(best, b); }
  })(0, pts.length - 1);
  return pts.filter((_, i) => keep[i]).length;
}
const ranked = M.rankRouteLines([{ routeIndex: 0, segments: [points] }], { minTolerance: 0.5 });
const out = {};
for (const tol of [0.5, 1, 2, 5, 10, 20]) {
  const ours = ranked.routes[0].segments[0].ranks.filter((r) => r > tol).length;
  out[tol] = [ours, dp(points, tol)];
}
const thin = M.thinRouteLines(ranked, 40);
const first = thin.routeLines[0].segments[0];
out.budget = { tolerance: thin.tolerance, fits: thin.pointCount <= 40, keepsEnds: first[0] === points[0] && first[first.length - 1] === points[points.length - 1] };
const roomy = M.thinRouteLines(ranked, 1e9);
out.roomy = { tolerance: roomy.tolerance, count: roomy.pointCount === ranked.pointCount };
return out;
"""
    )
    for tolerance in ("0.5", "1", "2", "5", "10", "20"):
        ours, reference = result[tolerance]
        assert ours == reference, (tolerance, ours, reference)
    assert result["budget"]["fits"] and result["budget"]["keepsEnds"]
    assert result["budget"]["tolerance"] > 0.5
    assert result["roomy"] == {"tolerance": 0.5, "count": True}


@node
def test_panel_padding_and_bounds() -> None:
    assert _run(
        """
const mapRect = { left: 0, top: 0, right: 1000, bottom: 600, width: 1000, height: 600 };
return {
  panels: M.panelPadding(mapRect, [{ left: 12, right: 332, width: 320, height: 500 }, { left: 700, right: 988, width: 288, height: 500 }], 20),
  hiddenPanel: M.panelPadding(mapRect, [{ left: 0, right: 0, width: 0, height: 0 }], 20),
  squeezed: M.panelPadding({ ...mapRect, right: 400, width: 400 }, [{ left: 0, right: 300, width: 300, height: 10 }], 20, 160).left <= 240,
  bounds: M.boundsOf([[2, 48], [2.5, 47.5]], [[1.5, 49], "junk", [NaN, 1]]),
  empty: M.boundsOf([]),
};
"""
    ) == {
        "panels": {"top": 20, "bottom": 20, "left": 352, "right": 320},
        "hiddenPanel": {"top": 20, "bottom": 20, "left": 20, "right": 20},
        "squeezed": True,
        "bounds": [[1.5, 47.5], [2.5, 49]],
        "empty": None,
    }


def test_shared_kit_never_injects_html_or_spreads_large_arrays() -> None:
    source = MAMUT_MAP_JS.read_text(encoding="utf-8")
    assert "innerHTML" not in source
    assert "setHTML" not in source
    assert "insertAdjacentHTML" not in source
    assert "Math.min(..." not in source and "Math.max(..." not in source
    # Styling is feature-state only: no paint/filter rewrites after the layers exist.
    assert "setPaintProperty" not in source
    assert "setFilter" not in source
    assert ".setStyle(" not in source
