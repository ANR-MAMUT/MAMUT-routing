"""The breadcrumb GitHub link opens the family repository at the directory of the page.

Every family is its own repository (``ANR-MAMUT/MAMUT-routing-<Family>``),
mounted at ``benchmarks/<Family>/`` of the main repository. A link into the
main repository's tree at ``benchmarks/<PT>/<Family>/...`` (the
problem-type-first layout) no longer exists.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

SITE_JS = Path(__file__).resolve().parents[1] / "src" / "mamut_routing_publish" / "site_assets" / "site.js"
FUNCTIONS = ("encodePathSegment", "normalizeRoute", "githubBenchmarksHref", "githubFamilyPathSegments")
CONSTANTS = (
    "GITHUB_ORG_ROOT",
    "GITHUB_BENCHMARKS_ROOT",
    "GITHUB_FAMILY_REPOSITORY_PREFIX",
    "GITHUB_FAMILY_BRANCH",
    "TIME_DEPENDENT_PROBLEM_TYPES",
    "METRIC_FACETS",
)

node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _script() -> str:
    source = SITE_JS.read_text(encoding="utf-8")
    parts = []
    for name in CONSTANTS:
        found = re.search(rf"^const {name} = .*?;$", source, re.M)
        assert found, f"{name} not found in site.js"
        parts.append(found.group(0))
    for name in FUNCTIONS:
        found = re.search(rf"^function {name}\(.*?^\}}", source, re.S | re.M)
        assert found, f"{name} not found in site.js"
        parts.append(found.group(0))
    return "\n\n".join(parts)


def _hrefs(trails: list[list[str]]) -> list[str]:
    items = [[{"label": label, "route_path": "/benchmarks/" if index == 0 else "/x/"} for index, label in enumerate(trail)] for trail in trails]
    script = _script() + f"\nconsole.log(JSON.stringify({json.dumps(items)}.map(githubBenchmarksHref)));\n"
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_site_js_defines_what_the_link_builder_needs() -> None:
    _script()


@node
def test_breadcrumb_links_open_the_family_repository() -> None:
    org = "https://github.com/ANR-MAMUT"
    assert _hrefs(
        [
            ["benchmarks"],
            ["benchmarks", "VRPTW"],
            ["benchmarks", "VRPTW", "Sintef2008"],
            ["benchmarks", "VRPTW", "Sintef2008", "n=100"],
            ["benchmarks", "VRPTW", "Sintef2008", "n=100", "C101"],
            ["benchmarks", "VRPTW", "Ortec2022", "final", "n=200", "ORTEC-x"],
            ["benchmarks", "TDVRP", "Lera2026", "S1", "n=200", "Lera-x"],
            ["benchmarks", "TDVRPTW", "Dabia2013", "n=25", "C101"],
            ["benchmarks", "CVRP", "Poryos2026", "fastest", "brest", "n=10", "poryos-brest-n10-poi"],
            ["benchmarks", "TDVRPTW", "Poryos2026", "fastest", "paris", "n=500", "poryos-paris-n500-poi-bpr-light"],
            ["benchmarks", "TDVRPTW", "Poryos2026", "fastest"],
        ]
    ) == [
        f"{org}/MAMUT-routing/tree/main/benchmarks",
        f"{org}/MAMUT-routing/tree/main/benchmarks",
        f"{org}/MAMUT-routing-Sintef2008/tree/main/VRPTW",
        f"{org}/MAMUT-routing-Sintef2008/tree/main/VRPTW/n=100",
        f"{org}/MAMUT-routing-Sintef2008/tree/main/VRPTW/n=100",
        f"{org}/MAMUT-routing-Ortec2022/tree/main/VRPTW/final/n=200",
        f"{org}/MAMUT-routing-Lera2026/tree/main/TDVRP/S1/n=200",
        f"{org}/MAMUT-routing-Dabia2013/tree/main/TDVRPTW/n=25",
        f"{org}/MAMUT-routing-Poryos2026/tree/main/CVRP/fastest/brest/n=10",
        f"{org}/MAMUT-routing-Poryos2026/tree/main/TDVRPTW/paris/n=500",
        f"{org}/MAMUT-routing-Poryos2026/tree/main/TDVRPTW",
    ]


@node
def test_pages_outside_the_benchmarks_tree_have_no_github_link() -> None:
    script = _script() + '\nconsole.log(JSON.stringify([githubBenchmarksHref([]), githubBenchmarksHref([{label: "History", route_path: "/history/"}])]));\n'
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout.strip().splitlines()[-1]) == ["", ""]
