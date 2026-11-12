"""Node tests for the shared route-animation module (site_assets/mamut-trips.js)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

MAMUT_TRIPS_JS = (
    Path(__file__).resolve().parents[1] / "src" / "mamut_routing_publish" / "site_assets" / "mamut-trips.js"
)

node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _run(body: str) -> object:
    script = f"""
const fs = require("fs");
const vm = require("vm");
const context = vm.createContext({{ console }});
const before = new Set(Object.getOwnPropertyNames(context));
vm.runInContext(fs.readFileSync({json.dumps(str(MAMUT_TRIPS_JS))}, "utf8"), context);
const leaked = Object.getOwnPropertyNames(context).filter((name) => !before.has(name));
const T = context.MamutTrips;
const result = (() => {{ {body} }})();
console.log(JSON.stringify(result));
"""
    completed = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=60)
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


# Depot at the origin, two customers on a line east of it (1e-3 deg ~ 111 m).
ROUTE_LINE = """{
  routeIndex: 0,
  sequence: [0, 1, 2, 0],
  segments: [
    [[0, 0], [0.001, 0], [0.002, 0]],
    [[0.002, 0], [0.003, 0]],
    [[0.003, 0], [0.0015, 0], [0, 0]],
  ],
}"""


@node
def test_loading_exposes_only_the_namespace() -> None:
    assert _run("return leaked;") == ["MamutTrips"]


@node
def test_trips_follow_the_timeline_with_dwell_points() -> None:
    result = _run(
        f"""
const timeline = {{ clock: "checker", routes: [{{ departure: 100, return_arrival: 400, stops: [[1, 150, 160, 170], [2, 200, 200, 210]] }}] }};
const data = T.buildTrips([{ROUTE_LINE}], timeline);
const trip = data.trips[0];
const monotone = trip.timestamps.every((t, i) => i === 0 || t >= trip.timestamps[i - 1]);
return {{ origin: data.origin, span: data.span, clock: data.clock, fallback: data.fallbackRoutes,
  timestamps: trip.timestamps.map((t) => Math.round(t * 1000) / 1000), monotone,
  visits: data.visits.map((v) => [v.node, v.serviceStart, v.coord]),
  midArc: T.positionAt(trip, 25), atStop: T.positionAt(trip, 65), before: T.positionAt(trip, -1),
  served: [T.servedCountAt(data.serviceTimes, 59), T.servedCountAt(data.serviceTimes, 60), T.servedCountAt(data.serviceTimes, 1000)] }};
"""
    )
    assert result["origin"] == 100 and result["span"] == 300 and result["clock"] == "checker" and result["fallback"] == 0
    # Arc 1: 0 -> 50 s over two equal steps; dwell at customer 1 until 70 (wait + service);
    # arc 2: 70 -> 100; dwell until 110; arc 3: 110 -> 300 over two equal steps.
    assert result["timestamps"] == [0, 25, 50, 70, 100, 110, 205, 300]
    assert result["monotone"]
    assert result["visits"] == [[1, 60, [0.002, 0]], [2, 100, [0.003, 0]]]
    assert result["midArc"] == pytest.approx([0.001, 0])
    assert result["atStop"][0] == pytest.approx(0.002, abs=1e-6)  # parked at customer 1
    assert result["before"] is None
    assert result["served"] == [0, 1, 2]


@node
def test_a_mismatching_or_missing_timeline_falls_back_to_constant_speed() -> None:
    result = _run(
        f"""
const wrongNodes = {{ clock: "checker", routes: [{{ departure: 0, return_arrival: 9, stops: [[2, 1, 1, 1], [1, 2, 2, 2]] }}] }};
const a = T.buildTrips([{ROUTE_LINE}], wrongNodes);
const b = T.buildTrips([{ROUTE_LINE}], null);
const speed = T.SCHEMATIC_SPEED_MPS;
return {{ clockA: a.clock, fallbackA: a.fallbackRoutes, clockB: b.clock, sameSpan: Math.abs(a.span - b.span) < 1e-9,
  // 0.006 deg of equator ~ 667.2 m at 25 km/h.
  spanSeconds: b.span, expected: 667.17 / speed }};
"""
    )
    assert result["clockA"] == "schematic" and result["fallbackA"] == 1
    assert result["clockB"] == "schematic" and result["sameSpan"]
    assert result["spanSeconds"] == pytest.approx(result["expected"], rel=1e-3)


@node
def test_td_schedules_convert_and_routes_keep_their_own_departure() -> None:
    result = _run(
        f"""
const td = [
  {{ departure_time: 500, duration: 300, return_arrival: 800, stops: [{{ node: 1, arrival: 550, wait: 0, service_start: 550, departure: 560 }}, {{ node: 2, arrival: 600, wait: 5, service_start: 605, departure: 610 }}] }},
  {{ departure_time: 300, duration: 100, return_arrival: 400, stops: [{{ node: 3, arrival: 350, wait: 0, service_start: 350, departure: 350 }}] }},
];
const timeline = T.timelineFromTdSchedules(td);
const second = {{ routeIndex: 1, sequence: [0, 3, 0], segments: [[[0, 0], [0.001, 0]], [[0.001, 0], [0, 0]]] }};
const data = T.buildTrips([{ROUTE_LINE}, second], timeline);
return {{ clock: timeline.clock, first: timeline.routes[0], origin: data.origin, departures: data.trips.map((t) => t.departure), empty: T.timelineFromTdSchedules([]) }};
"""
    )
    assert result["clock"] == "td_schedule"
    assert result["first"] == {"departure": 500, "return_arrival": 800, "stops": [[1, 550, 550, 560], [2, 600, 605, 610]]}
    # Times are relative to the earliest departure (300): route 0 leaves 200 s later.
    assert result["origin"] == 300 and result["departures"] == [200, 0]
    assert result["empty"] is None


@node
def test_clock_speed_and_colour_helpers() -> None:
    assert _run(
        """
return { clock: [T.formatClock(0), T.formatClock(3725.9), T.formatClock(86400 + 61)],
  speeds: [T.defaultSpeed(30), T.defaultSpeed(3600), T.defaultSpeed(86400), T.defaultSpeed(1e9)],
  rgb: [T.hexToRgb("#ff8000"), T.hexToRgb("#0f0"), T.hexToRgb("var(--x)")] };
"""
    ) == {
        "clock": ["00:00:00", "01:02:05", "00:01:01 +1d"],
        "speeds": [1, 60, 1800, 3600],
        "rgb": [[255, 128, 0], [0, 255, 0], [136, 136, 136]],
    }


def test_animation_module_never_injects_html() -> None:
    source = MAMUT_TRIPS_JS.read_text(encoding="utf-8")
    assert "innerHTML" not in source and "insertAdjacentHTML" not in source


# A DOM, a map and a deck.gl just large enough for openAnimation: no layout, no WebGL.
_BROWSER = r"""
const fs = require("fs");
const vm = require("vm");
class El {
  constructor(tag) { this.tagName = tag; this.children = []; this.listeners = {}; this.attrs = {}; this.hidden = false; }
  append(...nodes) { this.children.push(...nodes); }
  appendChild(node) { this.children.push(node); return node; }
  replaceChildren(...nodes) { this.children = nodes; }
  setAttribute(key, value) { this.attrs[key] = value; }
  addEventListener(type, listener) { (this.listeners[type] ||= []).push(listener); }
  fire(type) { (this.listeners[type] || []).forEach((listener) => listener({})); }
  querySelectorAll() { return []; }
  remove() {}
  getContext(kind) { return WEBGL2 && kind === "webgl2" ? { getExtension: () => null } : null; }
  find(className) {
    if (this.className === className) return this;
    for (const child of this.children) { const found = child.find?.(className); if (found) return found; }
    return null;
  }
}
let onWindow = [];  // [type, listener] pairs, as addEventListener keys them
const context = vm.createContext({
  console,
  document: { createElement: (tag) => new El(tag), head: new El("head") },
  performance: { now: () => 0 },
  requestAnimationFrame: () => 1,
  cancelAnimationFrame: () => {},
  addEventListener: (type, listener) => { onWindow.push([type, listener]); },
  removeEventListener: (type, listener) => { onWindow = onWindow.filter((pair) => pair[0] !== type || pair[1] !== listener); },
  deck: {
    TripsLayer: class {}, ScatterplotLayer: class {}, DataFilterExtension: class {},
    MapLibreOverlay: class { onAdd() { return new El("div"); } onRemove() {} setProps() {} },
  },
});
vm.runInContext(fs.readFileSync(TRIPS_JS, "utf8"), context);
const map = {
  addControl(control) { control.onAdd(this); },
  removeControl(control) { control.onRemove(this); },
  getCanvas: () => ({ parentNode: { insertBefore() {} }, nextSibling: null }),
};
const routeLine = { routeIndex: 0, sequence: [0, 1, 0], segments: [[[0, 0], [0.001, 0]], [[0.001, 0], [0, 0]]] };
const open = (host, extra = {}) => context.MamutTrips.openAnimation(map, host, {
  deckSrc: "deck.js", routeLines: [routeLine], timeline: null, palette: ["#ff0000"], visibleRoutes: new Set([0]),
  autoplay: false, ...extra,
});
"""


def _browser(body: str, *, webgl2: bool = True) -> object:
    script = (
        f"const WEBGL2 = {json.dumps(webgl2)};\nconst TRIPS_JS = {json.dumps(str(MAMUT_TRIPS_JS))};\n{_BROWSER}\n"
        f"(async () => {{ {body} }})().then((result) => console.log(JSON.stringify(result)));"
    )
    completed = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=60)
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


@node
def test_a_scrubber_drag_leaves_nothing_on_the_window() -> None:
    """Only one of pointerup / pointercancel ends a drag; the other listener must not stay behind,
    holding a closed animation's trips."""
    assert _browser(
        """
const host = new El("div");
const animation = await open(host);
const scrub = host.find("trips-scrub");
const counts = [];
scrub.fire("pointerdown");
counts.push(onWindow.length);                                  // a drag is on: listening for both ends
onWindow.filter(([type]) => type === "pointerup").forEach(([, listener]) => listener({}));
counts.push(onWindow.length);                                  // released: both listeners gone
scrub.fire("pointerdown");
scrub.fire("pointerdown");                                     // a second pointer: still one drag
counts.push(onWindow.length);
animation.close();                                             // closed in the middle of a drag
counts.push(onWindow.length);
return counts;
"""
    ) == [2, 0, 2, 0]


@node
def test_without_webgl2_the_notice_is_not_an_animation() -> None:
    """The frontends keep the handle to close the notice, but must not treat it as a running animation."""
    assert _browser(
        """
const host = new El("div");
let closed = 0;
const notice = await open(host, { onClose: () => { closed += 1; } });
const text = host.find("trips-note").textContent;
host.find("trips-close").fire("click");
return { unavailable: notice.unavailable, playing: notice.playing, text, closed, hidden: host.hidden };
""",
        webgl2=False,
    ) == {
        "unavailable": True,
        "playing": False,
        "text": "The route animation needs WebGL2, which this browser does not provide.",
        "closed": 1,
        "hidden": True,
    }
    assert _browser("const animation = await open(new El('div')); return animation.unavailable === undefined;") is True
