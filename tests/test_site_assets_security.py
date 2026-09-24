"""The public site cannot be turned into an injection vector by a link or a payload string.

Before: ``?payloadMode=api&apiPrefix=https://attacker/...`` made any page load
its payloads from another origin, and payload paths went into ``href="..."``
unescaped, so a crafted link ran attacker markup on the site's origin. The
query overrides are gone, every relative href is percent-encoded segment by
segment in one place (``relativeFromCurrent``), external links are
scheme-checked, the HTML shells escape their attributes and ship a
Content-Security-Policy.
"""

from __future__ import annotations

import base64
import hashlib
import html
import json
import re
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

from mamut_routing_publish import site_webapp

ASSETS = Path(__file__).resolve().parents[1] / "src" / "mamut_routing_publish" / "site_assets"
SITE_JS = ASSETS / "site.js"
WORKBENCH_JS = ASSETS / "workbench.js"
HREF_FUNCTIONS = (
    "escapeHtml",
    "encodePathSegment",
    "safeExternalHref",
    "normalizeRoute",
    "routeSegments",
    "relativeFromCurrent",
    "routeHref",
    "artifactHref",
)
SAFE_HREF_PREFIXES = ("routeHref(", "artifactHref(", "siteAssetHref(", "safeExternalHref(")
#: Locals audited by hand: built by the helpers above or from constants.
AUDITED_HREF_LOCALS = {"href", "vrpHref", "repoCommitUrl", "escapeHtml(href)"}

node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _extract(names: tuple[str, ...]) -> str:
    source = SITE_JS.read_text(encoding="utf-8")
    parts = []
    for name in names:
        found = re.search(rf"^function {name}\(.*?^\}}", source, re.S | re.M)
        assert found, f"{name} not found in site.js"
        parts.append(found.group(0))
    return "\n\n".join(parts)


def _run(route_path: str, expression: str):
    script = _extract(HREF_FUNCTIONS) + "\n" + textwrap.dedent(
        f"""
        const state = {{ routePath: {json.dumps(route_path)} }};
        console.log(JSON.stringify({expression}));
        """
    )
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


@node
def test_a_route_cannot_become_a_script_url() -> None:
    href = _run("/", 'routeHref("javascript:alert(1)")')
    assert not href.lower().startswith("javascript:")
    assert ":" not in href.split("/")[0]


@node
def test_a_path_cannot_leave_the_attribute() -> None:
    href = _run("/benchmarks/cvrp/", 'artifactHref("/benchmarks/cvrp/x\\"><img src=x onerror=alert(1)>")')
    assert not set('"<>') & set(href)
    assert _run("/", 'artifactHref("\\\\\\\\evil.example/x")').startswith("%5C%5C")


@node
def test_real_paths_are_unchanged() -> None:
    assert (
        _run("/benchmarks/vrptw/", 'artifactHref("benchmarks/VRPTW/Sintef2008/n=100/C101.vrp.json")')
        == "../VRPTW/Sintef2008/n=100/C101.vrp.json"
    )
    assert _run("/benchmarks/vrptw/sintef2008/", 'routeHref("/benchmarks/vrptw/sintef2008/n=100/")') == "n=100/index.html"


@node
def test_external_links_are_scheme_checked() -> None:
    assert _run("/", 'safeExternalHref("javascript:alert(1)")') == "#"
    assert _run("/", 'safeExternalHref("data:text/html,x")') == "#"
    assert _run("/", 'safeExternalHref("relative/path")') == "#"
    assert _run("/", 'safeExternalHref("https://creativecommons.org/licenses/by/4.0/?a=1&b=2")') == (
        "https://creativecommons.org/licenses/by/4.0/?a=1&amp;b=2"
    )


def test_the_url_no_longer_chooses_the_payload_source() -> None:
    source = SITE_JS.read_text(encoding="utf-8")
    for parameter in ("payloadMode", "apiPrefix", "payloadRoot"):
        assert f'runtimeParams.get("{parameter}")' not in source
    assert "payloadApiPrefix" not in source


@pytest.mark.parametrize("path", [SITE_JS, WORKBENCH_JS], ids=["site.js", "workbench.js"])
def test_every_href_goes_through_a_safe_helper(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    offenders = []
    for match in re.finditer(r'href="\$\{([^}]*(?:\([^)]*\))?[^}]*)\}"', source):
        expression = match.group(1).strip()
        if expression.startswith(SAFE_HREF_PREFIXES) or expression in AUDITED_HREF_LOCALS:
            continue
        offenders.append(expression)
    assert not offenders, offenders


def _csp_of(shell: str) -> str:
    match = re.search(r'<meta http-equiv="Content-Security-Policy" content="([^"]+)"', shell)
    assert match, "no CSP meta"
    return html.unescape(match.group(1))


def _sha(script_tag: str) -> str:
    inner = script_tag.removeprefix("<script>").removesuffix("</script>")
    return "'sha256-" + base64.b64encode(hashlib.sha256(inner.encode()).digest()).decode() + "'"


def test_shells_escape_attributes_and_pin_their_inline_scripts(tmp_path: Path) -> None:
    hostile = '/benchmarks/x"><script>alert(1)</script>/'
    shell = site_webapp._render_shell_html(
        tmp_path, hostile, payload_source_path=None, page_kind="payload", payload_static_root="/site-payloads"
    )
    assert "<script>alert(1)" not in shell
    assert "&quot;&gt;&lt;script&gt;" in shell
    csp = _csp_of(shell)
    assert _sha(site_webapp.THEME_INIT_SCRIPT) in csp
    assert "object-src 'none'" in csp and "base-uri 'self'" in csp
    assert shell.index("Content-Security-Policy") < shell.index(site_webapp.THEME_INIT_SCRIPT)

    workbench = site_webapp._render_workbench_shell_html(
        tmp_path, "/workbench/", payload_static_root="/site-payloads", workbench_mode="catalog"
    )
    csp = _csp_of(workbench)
    assert _sha(site_webapp.THEME_INIT_SCRIPT) in csp and _sha(site_webapp.LAYOUT_INIT_SCRIPT) in csp
    assert "worker-src 'self' blob:" in csp


@pytest.mark.parametrize("route", ["/../../etc/", "relative/", "/a\\b/", "/a/\x07/"])
def test_unsafe_route_paths_are_refused(route: str) -> None:
    with pytest.raises(ValueError, match="Unsafe route path"):
        site_webapp._validate_route_path(route)
