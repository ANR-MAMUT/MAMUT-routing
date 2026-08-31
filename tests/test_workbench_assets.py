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
