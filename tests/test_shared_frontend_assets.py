"""The website and the MAMUT-routing-tools GUI share some frontend files byte for byte.

Both frontends load these as classic scripts or vendored libraries, so one drifting
copy would make the two maps behave differently. The tools copy lives in the pinned
submodule; the test is skipped when that submodule is not checked out.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SITE_ASSETS = REPO_ROOT / "src" / "mamut_routing_publish" / "site_assets"
TOOLS_STATIC = REPO_ROOT / "MAMUT-routing-tools" / "src" / "mamut_routing_tools" / "gui" / "static"

SHARED_FILES = [
    "nocturne.js",
    "mamut-map.js",
    "mamut-trips.js",
    "vendor/deck.gl/dist.min.js",
    "vendor/deck.gl/LICENSE",
    "vendor/maplibre-gl/maplibre-gl.js",
    "vendor/maplibre-gl/maplibre-gl.css",
    "vendor/maplibre-gl/LICENSE",
]

requires_tools = pytest.mark.skipif(not TOOLS_STATIC.is_dir(), reason="MAMUT-routing-tools submodule not checked out")


@requires_tools
@pytest.mark.parametrize("relative", SHARED_FILES)
def test_shared_frontend_file_is_identical_in_both_frontends(relative: str) -> None:
    site_copy = SITE_ASSETS / relative
    tools_copy = TOOLS_STATIC / relative
    assert site_copy.is_file(), site_copy
    assert tools_copy.is_file(), tools_copy
    assert site_copy.read_bytes() == tools_copy.read_bytes(), f"{relative} differs between the website and the tools GUI"
