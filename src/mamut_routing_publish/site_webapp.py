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
# first paint already carries the correct data-theme attribute — otherwise the
# page paints in light defaults and re-paints once site.js applies the stored
# preference, producing a visible flash on dark-mode reloads.
THEME_INIT_SCRIPT = (
    '<script>(function(){try{var t=localStorage.getItem("mamut-routing-theme");'
    'if(t!=="dark"&&t!=="light"){t=window.matchMedia&&window.matchMedia('
    '"(prefers-color-scheme: dark)").matches?"dark":"light";}'
    'document.documentElement.dataset.theme=t;}catch(e){'
    'document.documentElement.dataset.theme="light";}})();</script>'
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
    return os.path.relpath(to_path, from_dir)


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
    logo_href = _relative_path(route_dir, output_repo_dir / "webapp" / "logos" / "logo_anr_mamut.png")
    favicon_href = _relative_path(route_dir, output_repo_dir / "webapp" / "icons" / "favicon.svg")
    payload_source = _relative_path(route_dir, payload_source_path) if payload_source_path is not None else ""
    nav_targets = {
        "home": "/",
        "benchmarks": "/benchmarks/",
        "workbench": "/workbench/",
        "project": "/project/",
        "objectives": "/objectives/",
        "history": "/history/",
    }
    active_nav = _active_nav(route_path)
    nav_links = "\n".join(
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
    tagline_by_nav = {
        "home": "Open benchmark catalog (CVRP, VRPTW, TDVRPTW, TDVRP), provenance, and routing workbench.",
        "benchmarks": "Lists of problems and benchmark families with instance and BKS data.",
        "project": "Research context for the MAMUT ANR project and its participants.",
        "objectives": "Reference of objective functions used to compare routing solutions.",
        "history": "Snapshot ledger tracking catalog updates and benchmark changes.",
    }
    tagline_text = tagline_by_nav.get(active_nav, "")
    tagline_html = f'<p class="brand-tagline">{tagline_text}</p>' if tagline_text else ""
    workbench_attr = f' data-workbench-mode="{workbench_mode}"' if workbench_mode else ""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>MAMUT-routing</title>
  {THEME_INIT_SCRIPT}
  <link rel="icon" type="image/svg+xml" href="{favicon_href}" />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="{css_href}" />
</head>
<body data-route-path="{route_path}" data-page-kind="{page_kind}" data-payload-source="{payload_source}" data-payload-mode="{payload_mode}" data-payload-api-prefix="{payload_api_prefix}" data-payload-static-root="{payload_static_root}"{workbench_attr}>
  <div class="bg-shape bg-shape-a"></div>
  <div class="bg-shape bg-shape-b"></div>
  <header class="app-header">
    <div class="header-row">
      <div>
        <a class="brand-link brand-link-with-logo" href="{_relative_path(route_dir, _route_html_path(output_repo_dir, '/'))}"><img class="brand-logo" src="{logo_href}" alt="MAMUT project logo" /><span>MAMUT-routing</span></a>
        {tagline_html}
      </div>
      <label class="theme-toggle" title="Toggle dark mode">
        <input id="themeSwitch" type="checkbox" />
        <span class="toggle-track"></span>
        <span class="toggle-label-icon" id="themeIcon">&#9790;</span>
      </label>
    </div>
    <nav class="primary-nav">{nav_links}</nav>
    <div id="breadcrumbTrail" class="breadcrumbs"></div>
  </header>

  <main class="layout" id="pageLayout" data-shell="catalog">
    <aside class="panel" id="pageAside"></aside>
    <section class="stage card" id="pageStage"></section>
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
    logo_href = _relative_path(route_dir, output_repo_dir / "webapp" / "logos" / "logo_anr_mamut.png")
    favicon_href = _relative_path(route_dir, output_repo_dir / "webapp" / "icons" / "favicon.svg")
    nav_targets = {
        "home": "/",
        "benchmarks": "/benchmarks/",
        "workbench": "/workbench/",
        "project": "/project/",
        "objectives": "/objectives/",
        "history": "/history/",
    }
    active_nav = _active_nav(route_path)
    nav_links = "\n".join(
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
    benchmarks_href = _relative_path(route_dir, _route_html_path(output_repo_dir, "/benchmarks/"))
    faq_href = _relative_path(route_dir, _route_html_path(output_repo_dir, "/project/faq/"))
    return f"""<!doctype html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>MAMUT-routing Workbench</title>
    {THEME_INIT_SCRIPT}
    <link rel="icon" type="image/svg+xml" href="{favicon_href}" />
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin="" />
    <link rel="stylesheet" href="{css_href}" />
</head>
<body data-route-path="{route_path}" data-page-kind="workbench-app" data-payload-mode="{payload_mode}" data-payload-api-prefix="{payload_api_prefix}" data-payload-static-root="{payload_static_root}" data-workbench-mode="{workbench_mode}">
    <div class="bg-shape bg-shape-a"></div>
    <div class="bg-shape bg-shape-b"></div>

    <header class="app-header">
        <div class="header-row">
            <div>
                <a class="brand-link brand-link-with-logo" href="{_relative_path(route_dir, _route_html_path(output_repo_dir, '/'))}"><img class="brand-logo" src="{logo_href}" alt="MAMUT project logo" /><span>MAMUT-routing</span></a>
                <p class="brand-tagline">Workbench for visualizing published benchmarks and local uploads. Instance generation and solving run locally with MAMUT-routing-tools.</p>
            </div>
            <label class="theme-toggle" title="Toggle dark mode">
                <input id="themeSwitch" type="checkbox" />
                <span class="toggle-track"></span>
                <span class="toggle-label-icon" id="themeIcon">&#9790;</span>
            </label>
        </div>
        <nav class="primary-nav">{nav_links}</nav>
    </header>

    <main class="layout workbench-layout">
        <aside class="panel">
            <section class="card tabs-card">
                <div class="tabs">
                    <button id="tabVisualize" class="tab-btn tab-active" type="button">Visualize</button>
                    <button id="tabGenerate" class="tab-btn" type="button">Generate</button>
                </div>
            </section>

            <section id="visualPanel" class="tab-panel tab-panel-active">
                <section class="card workbench-source-card">
                    <h2>Visualize Source</h2>
                    <div class="source-toggle source-toggle-wide">
                        <button id="sourceBenchmarkBtn" class="selector-chip active" type="button">Benchmark</button>
                        <button id="sourceUploadBtn" class="selector-chip" type="button">Upload</button>
                    </div>
                </section>

                <section id="benchmarkVisualPanel" class="card workbench-context-card">
                    <div class="card-heading">
                        <h2>Benchmark Instance</h2>
                    </div>
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
                    <label class="field"><span>Search</span><input id="benchmarkSearchFilter" type="search" placeholder="Instance or base name" /></label>
                    <label class="field"><span>Sort</span><select id="benchmarkSortSelect"><option value="city-size">City, size</option><option value="size">Numerical size</option><option value="metric">Metric</option><option value="cost">BKS cost</option><option value="routes">Routes</option><option value="cache">Geometry cache</option><option value="name">Name</option></select></label>
                    </div>
                    <label class="field">
                        <span>Published variant</span>
                        <select id="benchmarkInstanceSelect">
                            <option value="">Select a published family first...</option>
                        </select>
                    </label>
                    <p id="benchmarkStatus" class="workbench-card-intro">Select a published variant here, grouped by base instance to match the public benchmark catalog.</p>
                    <p id="benchmarkRenderStatus" class="meta-line">Road geometry will be rendered automatically when a benchmark sidecar is available.</p>
                    <label id="objectiveField" class="field" hidden>
                        <span>Objective overlay</span>
                        <select id="benchmarkObjectiveSelect"></select>
                    </label>
                    <div class="inline-actions">
                        <a id="openBenchmarkBtn" class="button-link primary" href="{benchmarks_href}">Open Public Instance</a>
                        <a id="browseBenchmarksBtn" class="mini-link" href="{benchmarks_href}">Browse Benchmarks</a>
                    </div>
                </section>

                <section id="uploadVisualPanel" class="card" hidden>
                    <h2>Files</h2>
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

                <section class="card" id="routeSelectorCard" style="display:none;">
                    <details id="routeSelectorDetails" open>
                        <summary><h2 style="display:inline;cursor:pointer;">Route Selection</h2></summary>
                        <div id="routeSelectorContainer" class="route-selector"></div>
                    </details>
                </section>

                <section class="card stats-card">
                    <h2>Instance Summary</h2>
                    <dl id="stats"></dl>
                </section>

                <section class="card legend-card">
                    <h2>Legend</h2>
                    <ul id="routeLegend" class="route-legend-list"></ul>
                </section>
            </section>

            <section id="generationPanel" class="tab-panel">
                <section class="card">
                    <h2>Generate Or Solve Locally</h2>
                    <p class="workbench-card-intro">Instance generation (OSM city fetch, CVRP/VRPTW sampling, TD families) and solving now run locally with the <strong>MAMUT-routing-tools</strong> suite instead of on this website. Local runs are faster, are not limited by a shared public server, and write instances straight to your machine.</p>
                    <div class="inline-actions">
                        <a class="button-link primary" href="https://github.com/ANR-MAMUT/MAMUT-routing-tools" rel="noopener">Get MAMUT-routing-tools</a>
                        <a class="mini-link" href="{faq_href}">Why local? See the FAQ</a>
                    </div>
                    <p class="meta-line">Quick start: clone the repository, install <a href="https://github.com/astral-sh/uv" rel="noopener">uv</a>, then run <code>uv run mamut-tools --help</code>. The local workbench GUI offers the same generation flows this tab used to host, plus everything that was too heavy for the public site.</p>
                </section>
                <section class="card note-card">
                    <h2>Notes</h2>
                    <p class="meta-line">Published benchmark instances and their BKS stay fully browsable in the Visualize tab and the public catalog. Generated data is workbench-scoped and never part of the published collection.</p>
                </section>
            </section>
        </aside>

        <section class="map-wrap card">
            <div id="map"></div>
            <button id="clearBtn" type="button" class="map-clear-btn">Clear Map</button>
            <div id="toast" class="toast"></div>
        </section>
    </main>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
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
    icon_source_dir = source_assets_dir / "icons"
    if icon_source_dir.exists():
        icon_target_dir = site_output / "webapp" / "icons"
        if icon_target_dir.exists():
            shutil.rmtree(icon_target_dir)
        shutil.copytree(icon_source_dir, icon_target_dir)
        asset_paths.extend(path for path in icon_target_dir.iterdir() if path.is_file())
    logo_source_dir = source_assets_dir / "logos"
    if logo_source_dir.exists():
        logo_target_dir = site_output / "webapp" / "logos"
        if logo_target_dir.exists():
            shutil.rmtree(logo_target_dir)
        shutil.copytree(logo_source_dir, logo_target_dir)
        asset_paths.extend(path for path in logo_target_dir.iterdir() if path.is_file())

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
