"""Run the TD route chart renderer with exact and historical curve sidecars."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest


SITE_JS = Path(__file__).resolve().parents[1] / "src/mamut_routing_publish/site_assets/site.js"
node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def run_chart_script(script: str) -> None:
    names = (
        "escapeHtml", "minOf", "maxOf", "chartFraction", "chartInterpolate", "chartScale",
        "chartTickLabel", "formatScheduleTime", "evaluateNdcpwlf", "renderArcFunctionChart",
        "routeChartDurations", "renderTdRouteFunctionCharts",
    )
    source = SITE_JS.read_text()
    functions = [re.search(rf"^function {name}\(.*?^\}}", source, re.S | re.M).group(0) for name in names]
    preamble = 'const assert = require("node:assert/strict"); const PALETTE = ["blue", "green"];'
    subprocess.run(["node", "-"], input="\n".join([preamble, *functions, script]), text=True, check=True)


@node
def test_exact_route_knot_projections_and_jumps() -> None:
    run_chart_script("""
        const exact = "td-binary64-exact-v1";
        const t = 2 ** 53;
        // Two attained departures project to t. The next pair is a genuine jump.
        const entry = {xs:[t,t,t+2,t+2,t+4], ys:[t,t+2,t+2,t+4,t+6],
          durations:[0.125,1,0,2,2], jump_indices:[3], duration:0, departure_time:t+2};
        const durations = routeChartDurations(exact, entry);
        assert.equal(durations[0], 0.125);
        assert.equal(evaluateNdcpwlf(entry.xs, durations, t+2), 0);
        assert.equal(evaluateNdcpwlf([0,2,2,8], [4,4,8,14], 3), 9);
        const html = renderTdRouteFunctionCharts({curve_profile:exact, routes:[entry]}, "ready", 0);
        assert.ok(html.includes(exact));
        // Only the true jump splits a polyline in each chart.
        assert.equal((html.match(/<polyline /g) || []).length, 4);
        assert.equal((html.match(/class="curve-jump-attained"/g) || []).length, 2);
        assert.equal((html.match(/class="curve-jump-limit"/g) || []).length, 2);
        assert.ok(html.includes("4 breakpoints"));
        assert.ok(html.includes("Horizontal ticks relative to " + t));
        assert.ok(html.includes("Minimum duration 0 at t* = " + (t+2)));
        assert.deepEqual(routeChartDurations("td-fold/2", {xs:[0,1],ys:[1,3]}), [1,2]);
    """)


@node
def test_single_departure_and_large_finite_route_coordinates() -> None:
    run_chart_script("""
        const render = (routes, i) => renderTdRouteFunctionCharts(
            {curve_profile:"td-binary64-exact-v1", routes}, "ready", i);
        const high = Number.MAX_VALUE;
        const low = high / 2;
        const routes = [
          {xs:[5], ys:[6], durations:[1], duration:1, departure_time:5},
          {xs:[low,high], ys:[high,high], durations:[low,0], duration:0, departure_time:high},
        ];
        const html = render(routes,0);
        assert.ok(html.includes("1 breakpoint."));
        assert.equal((html.match(/<polyline /g) || []).length, 2);
        assert.ok(!html.includes("NaN") && !html.includes("Infinity"));
        const singleton = chartScale([5], [6]);
        assert.equal(singleton.departure(0), 5);
        assert.equal(singleton.departure(420), 5);
        const large = render(routes,1);
        assert.ok(large.includes("2 breakpoints."));
        assert.ok(!large.includes("NaN") && !large.includes("Infinity"));
        const scale = chartScale([low,high], [high,high]);
        assert.equal(scale.departure(scale.px(high)), high);
        assert.equal(scale.departure(scale.px(low)), low);
    """)


def test_route_chart_grid_and_preview_toolbar_selectors() -> None:
    css = SITE_JS.with_suffix(".css").read_text()
    assert re.search(r"^\.home-preview-card \.viewer-toolbar \{\s*display: none;", css, re.M)
    assert re.search(r"^\.viewer-toolbar \{\s*display: flex;", css, re.M)
    grid = re.search(r"^\.route-function-charts \{([^}]+)\}", css, re.M)
    assert grid and "display: grid" in grid[1]
    assert "minmax(min(100%, 300px), 1fr)" in grid[1]
