from __future__ import annotations

import os
import shutil
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from mamut_routing_lib.json_utils import load_json_from_file
from mamut_routing_publish.progress import ProgressReporter
from mamut_routing_publish.site_payloads import DEFAULT_SITE_OUTPUT_DIR, DEFAULT_SITE_PAYLOAD_ROOT_DIR


SUPPORTED_PAYLOAD_MODES = {"static", "api"}


# Synchronous theme bootstrap. Must run before the stylesheet link so the very
# first paint already carries the correct data-theme attribute; otherwise the
# page paints in light defaults and re-paints once site.js applies the stored
# preference, producing a visible flash on dark-mode reloads.
THEME_INIT_SCRIPT = (
    '<script>(function(){try{var t=localStorage.getItem("mamut-theme")'
    '||localStorage.getItem("mamut-routing-theme");'
    'if(t!=="dark"&&t!=="light"){t=window.matchMedia&&window.matchMedia('
    '"(prefers-color-scheme: dark)").matches?"dark":"light";}'
    'document.documentElement.dataset.theme=t;}catch(e){'
    'document.documentElement.dataset.theme="light";}})();</script>'
)

# Same reasoning as THEME_INIT_SCRIPT, for the resizable panel widths: applied to
# <html> before first paint so a stored layout does not visibly snap into place.
LAYOUT_INIT_SCRIPT = (
    "<script>(function(){try{window.MamutLayout.applyState("
    "document.documentElement,window.MamutLayout.readState("
    'window.MamutLayout.STORAGE_KEY,{leftWidth:320}));}catch(e){}})();</script>'
)


class SiteWebappGenerationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    html_files_written: int
    asset_files_written: int
    placeholder_pages_written: int
    html_paths: list[str] | None = None
    asset_paths: list[str] | None = None
    removed_paths: list[str] | None = None


def _paths_for_summary(site_output: Path, paths: list[Path]) -> list[str]:
    values: list[str] = []
    for path in paths:
        try:
            values.append(path.relative_to(site_output).as_posix())
        except ValueError:
            values.append(path.as_posix())
    return sorted(values)


def _route_directory(output_repo_dir: Path, route_path: str) -> Path:
    return output_repo_dir / route_path.strip("/")


def _route_html_path(output_repo_dir: Path, route_path: str) -> Path:
    if route_path == "/":
        return output_repo_dir / "index.html"
    return _route_directory(output_repo_dir, route_path) / "index.html"


def _relative_path(from_dir: Path, to_path: Path) -> str:
    """A relative *URL* path, so it must use forward slashes on every platform.

    ``os.path.relpath`` yields backslashes on Windows, which are not path separators
    in a URL; browsers happen to normalise them, but the emitted HTML is wrong and
    stricter consumers reject it.
    """
    return os.path.relpath(to_path, from_dir).replace(os.sep, "/")


def _resolve_site_output_dir(output_repo_dir: Path, site_output_dir: str | Path | None) -> Path:
    if site_output_dir is None:
        return output_repo_dir / DEFAULT_SITE_OUTPUT_DIR
    candidate = Path(site_output_dir)
    return candidate if candidate.is_absolute() else output_repo_dir / candidate


def _active_nav(route_path: str) -> str:
    if route_path == "/":
        return "home"
    if route_path.startswith("/benchmarks/"):
        return "benchmarks"
    if route_path.startswith("/workbench/"):
        return "workbench"
    if route_path.startswith("/project/"):
        return "project"
    if route_path.startswith("/objectives/"):
        return "objectives"
    if route_path.startswith("/history/"):
        return "history"
    return ""


def _nav_links_html(output_repo_dir: Path, route_dir: Path, active_nav: str) -> str:
    nav_targets = {
        "home": "/",
        "benchmarks": "/benchmarks/",
        "workbench": "/workbench/",
        "project": "/project/",
        "objectives": "/objectives/",
        "history": "/history/",
    }
    return "\n".join(
        f'<a class="nav-link{active_class}" href="{_relative_path(route_dir, _route_html_path(output_repo_dir, target))}">{label}</a>'
        for label, target, active_class in [
            ("Home", nav_targets["home"], " active" if active_nav == "home" else ""),
            ("Benchmarks", nav_targets["benchmarks"], " active" if active_nav == "benchmarks" else ""),
            ("Workbench", nav_targets["workbench"], " active" if active_nav == "workbench" else ""),
            ("Project", nav_targets["project"], " active" if active_nav == "project" else ""),
            ("Objectives", nav_targets["objectives"], " active" if active_nav == "objectives" else ""),
            ("History", nav_targets["history"], " active" if active_nav == "history" else ""),
        ]
    )


def _render_header_html(output_repo_dir: Path, route_dir: Path, active_nav: str) -> str:
    home_href = _relative_path(route_dir, _route_html_path(output_repo_dir, "/"))
    nav_links = _nav_links_html(output_repo_dir, route_dir, active_nav)
    return f"""<header class="app-header">
    <a class="brand-link" href="{home_href}"><span class="brand-mark" aria-hidden="true"></span><span class="brand-name">MAMUT-routing</span></a>
    <nav class="primary-nav">{nav_links}</nav>
    <div class="header-tools">
      <label class="theme-toggle" title="Toggle color theme">
        <input id="themeSwitch" type="checkbox" aria-label="Use the dark theme" />
        <span class="theme-side theme-side-sun" aria-hidden="true">&#9728;</span>
        <span class="theme-side theme-side-moon" aria-hidden="true">&#9790;</span>
      </label>
      <a class="header-github" href="https://github.com/ANR-MAMUT/MAMUT-routing" target="_blank" rel="noopener">GitHub &#8599;</a>
    </div>
  </header>"""


def _render_shell_html(
    output_repo_dir: Path,
    route_path: str,
    *,
    payload_source_path: Path | None,
    page_kind: str,
    payload_mode: str,
    payload_api_prefix: str,
    payload_static_root: str,
    workbench_mode: str | None = None,
) -> str:
    route_dir = output_repo_dir if route_path == "/" else _route_directory(output_repo_dir, route_path)
    css_href = _relative_path(route_dir, output_repo_dir / "webapp" / "site.css")
    js_href = _relative_path(route_dir, output_repo_dir / "webapp" / "site.js")
    font_href = _relative_path(route_dir, output_repo_dir / "webapp" / "fonts" / "InterVariable.woff2")
    favicon_href = _relative_path(route_dir, output_repo_dir / "webapp" / "icons" / "favicon.svg")
    payload_source = _relative_path(route_dir, payload_source_path) if payload_source_path is not None else ""
    active_nav = _active_nav(route_path)
    workbench_attr = f' data-workbench-mode="{workbench_mode}"' if workbench_mode else ""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>MAMUT-routing</title>
  {THEME_INIT_SCRIPT}
  <link rel="icon" type="image/svg+xml" href="{favicon_href}" />
  <link rel="preload" href="{font_href}" as="font" type="font/woff2" crossorigin />
  <link rel="stylesheet" href="{css_href}" />
</head>
<body data-route-path="{route_path}" data-page-kind="{page_kind}" data-payload-source="{payload_source}" data-payload-mode="{payload_mode}" data-payload-api-prefix="{payload_api_prefix}" data-payload-static-root="{payload_static_root}"{workbench_attr}>
  {_render_header_html(output_repo_dir, route_dir, active_nav)}
  <div id="breadcrumbTrail" class="breadcrumbs"></div>

  <main class="layout" id="pageLayout" data-shell="catalog">
    <aside class="panel" id="pageAside"></aside>
    <section class="stage" id="pageStage"></section>
  </main>

  <div id="pageStatus" class="status-pill">Loading...</div>
  <script type="module" src="{js_href}"></script>
</body>
</html>
"""


def _render_workbench_shell_html(
    output_repo_dir: Path,
    route_path: str,
    *,
    payload_mode: str,
    payload_api_prefix: str,
    payload_static_root: str,
    workbench_mode: str,
) -> str:
    route_dir = output_repo_dir if route_path == "/" else _route_directory(output_repo_dir, route_path)
    css_href = _relative_path(route_dir, output_repo_dir / "webapp" / "workbench.css")
    js_href = _relative_path(route_dir, output_repo_dir / "webapp" / "workbench.js")
    layout_js_href = _relative_path(route_dir, output_repo_dir / "webapp" / "layout.js")
    nocturne_js_href = _relative_path(route_dir, output_repo_dir / "webapp" / "nocturne.js")
    font_href = _relative_path(route_dir, output_repo_dir / "webapp" / "fonts" / "InterVariable.woff2")
    favicon_href = _relative_path(route_dir, output_repo_dir / "webapp" / "icons" / "favicon.svg")
    leaflet_css_href = _relative_path(route_dir, output_repo_dir / "webapp" / "vendor" / "leaflet" / "leaflet.css")
    leaflet_js_href = _relative_path(route_dir, output_repo_dir / "webapp" / "vendor" / "leaflet" / "leaflet.js")
    active_nav = _active_nav(route_path)
    benchmarks_href = _relative_path(route_dir, _route_html_path(output_repo_dir, "/benchmarks/"))
    faq_href = _relative_path(route_dir, _route_html_path(output_repo_dir, "/project/faq/"))
    return f"""<!doctype html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>MAMUT-routing Workbench</title>
    {THEME_INIT_SCRIPT}
    <script src="{layout_js_href}"></script>
    <script src="{nocturne_js_href}"></script>
    {LAYOUT_INIT_SCRIPT}
    <link rel="icon" type="image/svg+xml" href="{favicon_href}" />
    <link rel="preload" href="{font_href}" as="font" type="font/woff2" crossorigin />
    <link rel="stylesheet" href="{leaflet_css_href}" />
    <link rel="stylesheet" href="{css_href}" />
</head>
<body data-route-path="{route_path}" data-page-kind="workbench-app" data-payload-mode="{payload_mode}" data-payload-api-prefix="{payload_api_prefix}" data-payload-static-root="{payload_static_root}" data-workbench-mode="{workbench_mode}">
    {_render_header_html(output_repo_dir, route_dir, active_nav)}

    <main class="wb-stage">
        <div id="map"></div>

        <div class="splitter splitter-left" data-splitter="left" role="separator" aria-orientation="vertical"
             tabindex="0" aria-label="Resize the workbench panel"></div>
        <div class="splitter splitter-right" data-splitter="right" role="separator" aria-orientation="vertical"
             tabindex="0" aria-label="Resize the selected-instance panel"></div>

        <aside class="wb-panel wb-panel-left">
            <div class="panel-rail" role="toolbar" aria-label="Expand the workbench panel">
                <button class="rail-btn" type="button" data-rail-side="left" data-rail-target="visualize" title="Visualize" aria-label="Visualize">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 6h11M9 12h11M9 18h7"/><circle cx="4.5" cy="6" r="1.1"/><circle cx="4.5" cy="12" r="1.1"/><circle cx="4.5" cy="18" r="1.1"/></svg>
                </button>
                <button class="rail-btn" type="button" data-rail-side="left" data-rail-target="generate" title="Generate" aria-label="Generate">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 7h8M17 7h3M4 17h3M12 17h8"/><circle cx="14.5" cy="7" r="2.2"/><circle cx="9.5" cy="17" r="2.2"/></svg>
                </button>
            </div>
            <div class="wb-panel-head">
            <div class="tabs">
                <button id="tabVisualize" class="tab-btn tab-active" type="button">Visualize</button>
                <button id="tabGenerate" class="tab-btn" type="button">Generate</button>
            </div>
            <button class="panel-toggle" type="button" data-panel-toggle="left" title="Collapse the panel" aria-label="Collapse the workbench panel">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 6l-6 6 6 6"/></svg>
            </button>
            </div>

            <section id="visualPanel" class="tab-panel tab-panel-active">
                <div class="source-toggle">
                    <button id="sourceBenchmarkBtn" class="selector-chip active" type="button">Benchmark</button>
                    <button id="sourceUploadBtn" class="selector-chip" type="button">Upload</button>
                </div>

                <section id="benchmarkVisualPanel" class="wb-section">
                    <div class="wb-kicker">Published instances</div>
                    <div class="benchmark-filter-grid">
                    <label class="field">
                        <span>Problem</span>
                        <select id="benchmarkProblemSelect">
                            <option value="">Loading published problems...</option>
                        </select>
                    </label>
                    <label class="field">
                        <span>Family</span>
                        <select id="benchmarkCatalogSelect">
                            <option value="">Loading published families...</option>
                        </select>
                    </label>
                    <label class="field"><span>Metric</span><select id="benchmarkMetricFilter"><option value="">All metrics</option></select></label>
                    <label class="field"><span>City</span><select id="benchmarkCityFilter"><option value="">All cities</option></select></label>
                    <label class="field"><span>Size</span><select id="benchmarkSizeFilter"><option value="">All sizes</option></select></label>
                    <label class="field"><span>Method</span><select id="benchmarkMethodFilter"><option value="">All methods</option></select></label>
                    <label class="field"><span>TW / traffic</span><select id="benchmarkScenarioFilter"><option value="">All scenarios</option></select></label>
                    <label class="field"><span>Geometry</span><select id="benchmarkGeometryFilter"><option value="">All geometry</option></select></label>
                    <label class="field"><span>Search</span><input id="benchmarkSearchFilter" type="search" placeholder="Instance or base name" /></label>
                    </div>
                    <div class="catalog-sort-controls wb-sort-controls">
                        <label class="field catalog-sort-field"><span>Sort by</span><select id="benchmarkSortSelect"><option value="catalog">Catalog order</option><option value="name">Instance name</option><option value="size">Customers</option><option value="routes">Routes</option><option value="cost" disabled>BKS cost (filter to one objective)</option></select></label>
                        <button id="benchmarkSortDirection" class="sort-direction-button" type="button" aria-label="Sort direction: ascending. Activate for descending." title="Ascending"><span aria-hidden="true">↑</span></button>
                    </div>
                    <label class="field">
                        <span>Published variant</span>
                        <select id="benchmarkInstanceSelect">
                            <option value="">Select a published family first...</option>
                        </select>
                    </label>
                    <p id="benchmarkStatus" class="meta-line">Select a published variant here, grouped by base instance to match the public benchmark catalog.</p>
                    <label id="objectiveField" class="field" hidden>
                        <span>Objective overlay</span>
                        <select id="benchmarkObjectiveSelect"></select>
                    </label>
                    <div class="inline-actions">
                        <a id="openBenchmarkBtn" class="button-link primary" href="{benchmarks_href}">Open Public Instance</a>
                        <a id="browseBenchmarksBtn" class="mini-link" href="{benchmarks_href}">Browse Benchmarks</a>
                    </div>
                </section>

                <section id="uploadVisualPanel" class="wb-section" hidden>
                    <div class="wb-kicker">Local files</div>
                    <label class="field">
                        <span>Instance file (.vrp or .json)</span>
                        <input id="vrpInput" type="file" accept=".vrp,.json,.txt" />
                    </label>
                    <label class="field">
                        <span>Solution file (.sol or .json)</span>
                        <input id="solInput" type="file" accept=".sol,.json,.txt" />
                    </label>
                    <label class="field">
                        <span>Metadata sidecar (.json)</span>
                        <input id="metaInput" type="file" accept=".json" />
                    </label>
                    <p class="meta-line">Uploaded routes draw as straight lines. Road-following rendering and solving run locally with MAMUT-routing-tools (see the Generate tab).</p>
                </section>
            </section>

            <section id="generationPanel" class="tab-panel">
                <section class="wb-section">
                    <div class="wb-kicker">Generate or solve locally</div>
                    <p class="wb-prose">Instance generation (OSM city fetch, CVRP/VRPTW sampling, TD families) and solving now run locally with the <strong>MAMUT-routing-tools</strong> suite instead of on this website. Local runs are faster, are not limited by a shared public server, and write instances straight to your machine.</p>
                    <div class="inline-actions">
                        <a class="button-link primary" href="https://github.com/ANR-MAMUT/MAMUT-routing-tools" rel="noopener">Get MAMUT-routing-tools</a>
                        <a class="mini-link" href="{faq_href}">Why local? See the FAQ</a>
                    </div>
                    <p class="meta-line">Quick start: install <a href="https://github.com/astral-sh/uv" rel="noopener">uv</a>, then run <code>uvx --from mamut-routing-tools mamut-tools gui start</code> (published on <a href="https://pypi.org/project/mamut-routing-tools/" rel="noopener">PyPI</a>). The local GUI covers the core generation and solving workflow, persists checker-validated solution runs and background-job logs, and keeps growing toward full parity with the former website workbench.</p>
                </section>
                <section class="wb-section">
                    <div class="wb-kicker">Notes</div>
                    <p class="meta-line">Published benchmark instances and their BKS stay fully browsable in the Visualize tab and the public catalog. Generated data is workbench-scoped and never part of the published collection.</p>
                </section>
            </section>
        </aside>

        <aside class="wb-panel wb-panel-right">
            <div class="panel-rail" role="toolbar" aria-label="Expand the selected-instance panel">
                <button class="rail-btn" type="button" data-rail-side="right" data-rail-target="instance" title="Selected instance" aria-label="Selected instance">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 21c4.2-4 7-7.4 7-10.6a7 7 0 1 0-14 0C5 13.6 7.8 17 12 21z"/><circle cx="12" cy="10.2" r="2.4"/></svg>
                </button>
            </div>
            <div class="wb-panel-head">
                <div class="wb-kicker wb-kicker-selected">Selected instance</div>
                <button class="panel-toggle" type="button" data-panel-toggle="right" title="Collapse the panel" aria-label="Collapse the selected-instance panel">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 6l6 6-6 6"/></svg>
                </button>
            </div>
            <dl id="stats" class="wb-stats"></dl>

            <section class="wb-section" id="routeSelectorCard" hidden>
                <div class="wb-kicker">Routes</div>
                <div id="routeSelectorContainer" class="route-selector"></div>
            </section>
        </aside>

        <button id="clearBtn" type="button" class="map-clear-btn">Clear map</button>
        <div class="wb-footer"><span class="wb-footer-dot" aria-hidden="true"></span><p id="benchmarkRenderStatus">Historical benchmark families use straight-line rendering. Poryos2026 uses published road geometry when available.</p></div>
        <div id="toast" class="toast"></div>
    </main>

    <script src="{leaflet_js_href}"></script>
    <script type="module" src="{js_href}"></script>
</body>
</html>
"""


def generate_site_webapp(
    output_repo_dir: str | Path,
    *,
    payload_mode: str = "static",
    payload_api_prefix: str = "/api/site-payload",
    payload_root_dir: str | Path = DEFAULT_SITE_PAYLOAD_ROOT_DIR,
    site_output_dir: str | Path | None = None,
    reporter: ProgressReporter | None = None,
    list_files: bool = False,
) -> SiteWebappGenerationSummary:
    output_repo = Path(output_repo_dir)
    site_output = _resolve_site_output_dir(output_repo, site_output_dir)
    payload_root = Path(payload_root_dir)
    if payload_root.is_absolute():
        raise ValueError(f"Site payload root must be repository-relative, got: {payload_root}")
    payload_static_root = f"/{payload_root.as_posix().strip('/')}"
    if payload_mode not in SUPPORTED_PAYLOAD_MODES:
        raise ValueError(f"Unsupported payload mode: {payload_mode!r}")
    source_assets_dir = Path(__file__).with_name("site_assets")
    if not source_assets_dir.exists():
        raise FileNotFoundError(f"Missing site asset directory: {source_assets_dir}")

    asset_targets = [
        (source_assets_dir / "site.css", site_output / "webapp" / "site.css"),
        (source_assets_dir / "site.js", site_output / "webapp" / "site.js"),
        (source_assets_dir / "workbench.css", site_output / "webapp" / "workbench.css"),
        (source_assets_dir / "workbench.js", site_output / "webapp" / "workbench.js"),
        (source_assets_dir / "layout.js", site_output / "webapp" / "layout.js"),
        (source_assets_dir / "nocturne.js", site_output / "webapp" / "nocturne.js"),
        (source_assets_dir / "nocturne-tokens.css", site_output / "webapp" / "nocturne-tokens.css"),
    ]
    asset_paths: list[Path] = []
    if reporter is not None:
        reporter.phase("copying web assets")
    with (reporter.task("copy web assets", len(asset_targets)) if reporter else _NullProgressTask()) as task:
        for source_path, target_path in asset_targets:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_bytes(source_path.read_bytes())
            asset_paths.append(target_path)
            task.update(detail=target_path.name)
    for asset_dir_name in ("icons", "logos", "fonts", "vendor"):
        asset_source_dir = source_assets_dir / asset_dir_name
        if not asset_source_dir.exists():
            continue
        asset_target_dir = site_output / "webapp" / asset_dir_name
        if asset_target_dir.exists():
            shutil.rmtree(asset_target_dir)
        shutil.copytree(asset_source_dir, asset_target_dir)
        asset_paths.extend(path for path in asset_target_dir.rglob("*") if path.is_file())

    html_paths: list[Path] = []
    route_payloads: dict[str, Path] = {}
    payload_search_root = site_output / payload_root
    if reporter is not None:
        reporter.phase("discovering route payloads", root=payload_search_root)
    payload_paths = sorted(payload_search_root.rglob("index.json")) if payload_search_root.exists() else []
    for payload_path in payload_paths:
        payload = load_json_from_file(payload_path)
        if not isinstance(payload, dict):
            continue
        route_path = payload.get("route_path")
        if not isinstance(route_path, str):
            continue
        route_payloads[route_path] = payload_path

    with (reporter.task("write HTML shells", len(route_payloads)) if reporter else _NullProgressTask()) as task:
        for route_path, payload_path in route_payloads.items():
            html_path = _route_html_path(site_output, route_path)
            html_path.parent.mkdir(parents=True, exist_ok=True)
            html_path.write_text(
                _render_shell_html(
                    site_output,
                    route_path,
                    payload_source_path=payload_path,
                    page_kind="payload",
                    payload_mode=payload_mode,
                    payload_api_prefix=payload_api_prefix,
                    payload_static_root=payload_static_root,
                ),
                encoding="utf-8",
            )
            html_paths.append(html_path)
            task.update(detail=route_path)

    if "/history/" not in route_payloads:
        history_html_path = _route_html_path(site_output, "/history/")
        history_html_path.parent.mkdir(parents=True, exist_ok=True)
        history_html_path.write_text(
            _render_shell_html(
                site_output,
                "/history/",
                payload_source_path=site_output / "site" / "history.json",
                page_kind="payload",
                payload_mode=payload_mode,
                payload_api_prefix=payload_api_prefix,
                payload_static_root=payload_static_root,
            ),
            encoding="utf-8",
        )
        html_paths.append(history_html_path)

    placeholder_pages_written = 0
    for route_path, workbench_mode in [
        ("/workbench/", "catalog"),
        ("/workbench/catalog/", "catalog"),
        ("/workbench/upload/", "upload"),
        ("/workbench/generate/", "generate"),
    ]:
        html_path = _route_html_path(site_output, route_path)
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(
            _render_workbench_shell_html(
                site_output,
                route_path,
                payload_mode=payload_mode,
                payload_api_prefix=payload_api_prefix,
                payload_static_root=payload_static_root,
                workbench_mode=workbench_mode,
            ),
            encoding="utf-8",
        )
        html_paths.append(html_path)
        placeholder_pages_written += 1

    removed_paths: list[Path] = []
    derive_html_path = _route_html_path(site_output, "/workbench/derive/")
    if derive_html_path.exists():
        derive_html_path.unlink()
        removed_paths.append(derive_html_path)
    derive_dir = derive_html_path.parent
    if derive_dir.exists():
        try:
            derive_dir.rmdir()
            removed_paths.append(derive_dir)
        except OSError:
            pass

    return SiteWebappGenerationSummary(
        html_files_written=len(html_paths),
        asset_files_written=len(asset_paths),
        placeholder_pages_written=placeholder_pages_written,
        html_paths=_paths_for_summary(site_output, html_paths) if list_files else None,
        asset_paths=_paths_for_summary(site_output, asset_paths) if list_files else None,
        removed_paths=_paths_for_summary(site_output, removed_paths) if list_files and removed_paths else None,
    )


class _NullProgressTask:
    def __enter__(self) -> "_NullProgressTask":
        return self

    def __exit__(self, *args) -> None:
        return None

    def update(self, *args, **kwargs) -> None:
        return None
