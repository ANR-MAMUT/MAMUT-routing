"""The viewer's geometry helpers must not have a size limit.

``Math.min(...values)`` passes an *argument list*, which every JS engine caps --
around 240 000 entries in V8, after which it throws

    RangeError: Maximum call stack size exceeded

Every array these helpers see grows with the instance. The largest published
Mamut2026 solution traverses 2.2 million road-geometry points, so the four
biggest instances in the collection had unopenable pages: the spread form was a
size limit wearing the costume of a convenience.

There is no JavaScript test harness in this repository, which is exactly why that
shipped. These tests extract the pure functions from the asset and exercise them
under node, and skip when node is absent rather than pretending to pass.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

SITE_JS = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "mamut_routing_publish"
    / "site_assets"
    / "site.js"
)

#: Helpers the viewer applies to whole-instance arrays. Any of these using a
#: spread into Math.min/Math.max would reintroduce the ceiling.
SIZE_SCALING_FUNCTIONS = ("minOf", "maxOf", "coordinateBounds", "thinProjectedPath")

node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _extract(names: tuple[str, ...]) -> str:
    source = SITE_JS.read_text(encoding="utf-8")
    parts = [
        match.group(0)
        for match in [re.search(r"^const PREVIEW_MIN_POINT_SPACING_PX = .*$", source, re.M)]
        if match
    ]
    for name in names:
        found = re.search(rf"^function {name}\(.*?^\}}", source, re.S | re.M)
        assert found, f"{name} not found in site.js"
        parts.append(found.group(0))
    return "\n\n".join(parts)


def _run(script: str) -> dict:
    bundle = _extract(SIZE_SCALING_FUNCTIONS) + "\n" + textwrap.dedent(script)
    result = subprocess.run(
        ["node", "-e", bundle], capture_output=True, text=True, timeout=120
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_no_size_scaling_helper_spreads_into_math() -> None:
    """A source check, so the guard holds even where node is unavailable."""
    body = _extract(SIZE_SCALING_FUNCTIONS)
    assert "Math.min(..." not in body
    assert "Math.max(..." not in body


@node
def test_bounds_survive_a_solution_sized_point_cloud() -> None:
    """2.2 million points is what the largest published instance actually has."""
    out = _run(
        """
        const N = 2_200_000;
        const points = new Array(N);
        for (let i = 0; i < N; i += 1) points[i] = [Math.sin(i) * 100, Math.cos(i) * 50];
        const bounds = coordinateBounds(points);
        console.log(JSON.stringify(bounds));
        """
    )
    assert out["minX"] == pytest.approx(-100, abs=1e-3)
    assert out["maxX"] == pytest.approx(100, abs=1e-3)
    assert out["minY"] == pytest.approx(-50, abs=1e-3)
    assert out["maxY"] == pytest.approx(50, abs=1e-3)


@node
def test_bounds_span_several_point_lists_without_concatenating_them() -> None:
    """The preview measures node coordinates and one list per route."""
    out = _run(
        """
        console.log(JSON.stringify(
          coordinateBounds([[0, 0]], [[10, 20]], [[-5, 3]], [])
        ));
        """
    )
    assert out == {"minX": -5, "maxX": 10, "minY": 0, "maxY": 20}


@node
def test_bounds_reject_input_with_nothing_finite_in_it() -> None:
    out = _run(
        """
        console.log(JSON.stringify([
          coordinateBounds([]),
          coordinateBounds(),
          coordinateBounds([[NaN, 1], ["x", "y"], [1]]),
          coordinateBounds(null),
        ]));
        """
    )
    assert out == [None, None, None, None]


@node
def test_thinning_keeps_the_shape_and_both_endpoints() -> None:
    """Sub-pixel detail is dropped; the route still starts and ends where it did."""
    out = _run(
        """
        const N = 200_000;
        const path = new Array(N);
        for (let i = 0; i < N; i += 1) {
          path[i] = { x: 430 + 400 * Math.sin(i / 5000), y: 260 + 240 * Math.cos(i / 3000) };
        }
        const kept = thinProjectedPath(path);
        let widestGap = 0;
        for (let i = 1; i < kept.length; i += 1) {
          widestGap = Math.max(widestGap, Math.hypot(kept[i].x - kept[i - 1].x, kept[i].y - kept[i - 1].y));
        }
        console.log(JSON.stringify({
          before: N,
          after: kept.length,
          widestGap,
          firstKept: kept[0] === path[0],
          lastKept: kept[kept.length - 1] === path[N - 1],
        }));
        """
    )
    assert out["after"] < out["before"] / 5, "dense sub-pixel detail should collapse"
    assert out["firstKept"] and out["lastKept"]
    # Nothing is moved: consecutive kept points stay about a pixel apart, so the
    # stroke is indistinguishable at the preview's 860x520.
    assert out["widestGap"] < 2.0


@node
def test_thinning_leaves_short_paths_alone() -> None:
    out = _run(
        """
        console.log(JSON.stringify([
          thinProjectedPath([]).length,
          thinProjectedPath([{ x: 0, y: 0 }]).length,
          thinProjectedPath([{ x: 0, y: 0 }, { x: 1, y: 1 }]).length,
        ]));
        """
    )
    assert out == [0, 1, 2]
