"""Planar instances in the workbench (site.js ``withPlanarDisplayFrame``).

Solomon / Gehring-Homberger and the TD families publish planar x, y. Leaflet drew them
unprojected; MapLibre throws "Invalid LngLat latitude" past ±90. They are scaled into a
synthetic frame around (0, 0) instead, keeping the original x, y for the popups, while
geographic instances (ENU with ``reference_lla``, or lon/lat) pass through unchanged.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

SITE_JS = Path(__file__).resolve().parents[1] / "src" / "mamut_routing_publish" / "site_assets" / "site.js"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _frame(payload: dict) -> dict:
    source = SITE_JS.read_text(encoding="utf-8")
    parts = [re.search(r"^const MERCATOR_MAX_LATITUDE = .*$", source, re.M).group(0)]
    for name in ("isPlanarInstance", "withPlanarDisplayFrame"):
        found = re.search(rf"^function {name}\(.*?^\}}", source, re.S | re.M)
        assert found, f"{name} not found in site.js"
        parts.append(found.group(0))
    script = "\n\n".join(parts) + f"\nconsole.log(JSON.stringify(withPlanarDisplayFrame({json.dumps(payload)})));"
    completed = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


def test_gehring_homberger_coordinates_are_scaled_into_a_valid_frame() -> None:
    payload = {"benchmark_name": "Sintef2008", "coordinates": [[250, 250], [0, 0], [500, 120], [37, 499]]}
    framed = _frame(payload)
    assert framed["planar"] is True and framed["planarCoordinates"] == payload["coordinates"]
    assert all(abs(lon) <= 0.5 and abs(lat) <= 0.5 for lon, lat in framed["coordinates"])
    # To scale: one factor on both axes, the plane's centre at (0, 0).
    (x0, y0), (x1, y1) = framed["coordinates"][1], framed["coordinates"][2]
    assert (x1 - x0) / (y1 - y0) == pytest.approx(500 / 120)


def test_solomon_coordinates_in_the_lat_lon_range_are_still_planar() -> None:
    framed = _frame({"benchmark_name": "Sintef2008", "instance_origin": "Solomon1987", "coordinates": [[40, 50], [45, 68]]})
    assert framed["planar"] is True


def test_geographic_instances_pass_through() -> None:
    lon_lat = {"name": "third-party", "coordinates": [[2.35, 48.85], [2.29, 48.86]]}
    assert _frame(lon_lat) == lon_lat
    # A collection instance with a place, after its ENU coordinates were projected to lon/lat.
    projected = {"benchmark_name": "Poryos2026", "reference_lla": {"lat": 48.8, "lon": 2.3}, "coordinates": [[2.3, 48.8]]}
    assert _frame(projected) == projected
    assert _frame({"name": "x", "coordinates": [[2.3, 95.0]]})["planar"] is True  # out of range: never handed to MapLibre
