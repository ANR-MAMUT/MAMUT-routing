"""Planar instances in the workbench (site.js ``withPlanarDisplayFrame``).

Solomon / Gehring-Homberger and most TD families publish planar x, y. Leaflet drew them
unprojected; MapLibre throws "Invalid LngLat latitude" past ±90. They are scaled into a
synthetic frame around (0, 0) instead, keeping the original x, y for the popups, while
geographic instances (ENU with ``reference_lla``, or lon/lat) pass through unchanged.
Blauth2024 is a benchmark family without ``reference_lla`` whose coordinates are real
longitudes and latitudes: it declares them and stays on its city.
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


def test_a_family_that_declares_lon_lat_stays_on_its_city() -> None:
    """Blauth2024: no reference_lla, but WGS84 coordinates (here Cincinnati), as its files say."""
    blauth = {
        "benchmark_name": "Blauth2024",
        "instance_origin": "Blauth2024",
        "coordinates": [[-84.42893201054736, 39.10539700726847], [-84.39911700610546, 38.98441000453519]],
        "metadata": {"coordinates_convention": "[longitude, latitude], WGS84 degrees, informative only"},
    }
    assert _frame(blauth) == blauth
    # The declaration is what counts: the same numbers without it are a plane, like any other family's.
    undeclared = {key: value for key, value in blauth.items() if key != "metadata"}
    assert _frame(undeclared)["planar"] is True
    # A declaration cannot make out-of-range coordinates geographic.
    assert _frame({**blauth, "coordinates": [[250.0, 120.0], [0.0, 0.0]]})["planar"] is True


def test_published_blauth_instances_declare_their_coordinates() -> None:
    """The rule above rests on the published files: every Blauth2024 instance must carry the declaration."""
    root = Path(__file__).resolve().parents[1] / "benchmarks" / "TDVRPTW" / "Blauth2024"
    files = sorted(root.rglob("*.vrp.json"))
    if not files:
        pytest.skip("the Blauth2024 satellite is not checked out")
    for path in files:
        instance = json.loads(path.read_text(encoding="utf-8"))
        assert not instance.get("reference_lla"), path.name
        assert "WGS84" in instance["metadata"]["coordinates_convention"], path.name
        assert _frame({key: instance[key] for key in ("benchmark_name", "instance_origin", "metadata")}
                      | {"coordinates": instance["coordinates"][:50]}).get("planar") is None, path.name
