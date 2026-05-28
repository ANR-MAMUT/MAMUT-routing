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
        "home": "Open VRPTW benchmark catalog, provenance, and routing workbench.",
        "benchmarks": "Lists of problems and benchmark families with instance and BKS data.",
        "project": "Research context for the MAMUT ANR project and its participants.",
        "objectives": "Reference of objective functions used to compare VRPTW solutions.",
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
                <p class="brand-tagline">Original-style workbench for benchmark preload, upload visualization, single and batch instance generation, and OSM-backed preview flows.</p>
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
                    <label class="field">
                        <span>Problem + family</span>
                        <select id="benchmarkCatalogSelect">
                            <option value="">Loading published families...</option>
                        </select>
                    </label>
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
                    <label class="field">
                        <span>Route API endpoint</span>
                        <input id="apiUrlInput" type="text" value="/api/workbench/render-routes" />
                    </label>
                    <label class="field">
                        <span>Route metric</span>
                        <select id="metricSelect">
                            <option value="shortest">Shortest</option>
                            <option value="fastest">Fastest</option>
                            <option value="euclidean">Euclidean</option>
                        </select>
                    </label>
                    <label class="field">
                        <span>HGS time limit (seconds)</span>
                        <input id="solveTimeLimitInput" type="number" min="1" value="30" />
                    </label>
                    <div class="btn-row">
                        <button id="roadBtn" type="button">Render Road Geometry</button>
                        <button id="solveBtn" type="button">Solve with HGS</button>
                        <button id="saveHgsBtn" type="button" hidden>Save HGS Solution</button>
                    </div>
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
                    <h2>Fetch OSM Data</h2>
                    <p class="workbench-card-intro">Download an OSM extract by city/locality name into <code>MAMUT-routing/osmdata/</code>. The new city becomes available for instance generation immediately.</p>
                    <label class="field">
                        <span>City to fetch</span>
                        <input id="genFetchCityInput" type="text" placeholder="e.g. Berlin" />
                    </label>
                    <label class="field">
                        <span>Country (optional)</span>
                        <input id="genFetchCountryInput" type="text" placeholder="e.g. Germany" />
                    </label>
                    <label class="field">
                        <span>Padding (km)</span>
                        <input id="genFetchPaddingInput" type="number" min="0" step="0.5" value="0" />
                    </label>
                    <button id="genFetchBtn" type="button">Fetch OSM And Add City</button>
                </section>

                <section class="card">
                    <h2>Generation Setup</h2>
                    <label class="field">
                        <span>Problem type</span>
                        <select id="genProblemTypeSelect">
                            <option value="CVRP" selected>CVRP — capacity only</option>
                            <option value="VRPTW">VRPTW — capacity + time windows</option>
                        </select>
                    </label>
                    <label class="field">
                        <span>City</span>
                        <select id="genCitySelect"></select>
                    </label>
                    <label class="field">
                        <span>Method</span>
                        <select id="genMethodSelect">
                            <option value="poi_categories">POI Categories</option>
                            <option value="parametric_attach">Parametric Attach</option>
                            <option value="hybrid">Hybrid</option>
                        </select>
                    </label>
                    <label class="field gen-field-common">
                        <span>Customers</span>
                        <input id="genCustomersInput" type="number" min="2" value="50" />
                    </label>
                    <label class="field gen-field-common">
                        <span>Demand distribution</span>
                        <select id="genDemandTypeSelect">
                            <option value="1">1 — Unitary</option>
                            <option value="2">2 — Small, large var</option>
                            <option value="3">3 — Small, small var</option>
                            <option value="4">4 — Large, large var</option>
                            <option value="5">5 — Large, small var</option>
                            <option value="6">6 — Large, depending on quadrant</option>
                            <option value="7" selected>7 — Few large, many small</option>
                        </select>
                    </label>
                    <label class="field gen-field-common">
                        <span>Average route size</span>
                        <select id="genAvgRouteSizeSelect">
                            <option value="1">1 — Ultra short</option>
                            <option value="2">2 — Very short</option>
                            <option value="3">3 — Short</option>
                            <option value="4" selected>4 — Medium</option>
                            <option value="5">5 — Long</option>
                            <option value="6">6 — Very long</option>
                            <option value="7">7 — Ultra long</option>
                        </select>
                    </label>
                    <label class="field gen-field-common">
                        <span>Seed</span>
                        <input id="genSeedInput" type="number" min="0" value="0" />
                    </label>
                    <label class="field checkbox-field gen-field-common">
                        <span>Only intersections</span>
                        <input id="genOnlyIntersectionsInput" type="checkbox" checked />
                    </label>
                    <label class="field gen-field-poi gen-field-parametric gen-field-hybrid">
                        <span>Depot mode</span>
                        <select id="genDepotModeSelect">
                            <option value="center">Center</option>
                            <option value="random">Random</option>
                            <option value="corner">Corner</option>
                        </select>
                    </label>
                    <label class="field gen-field-parametric gen-field-hybrid">
                        <span>Customer mode</span>
                        <select id="genCustomerModeSelect">
                            <option value="random_clustered">Random-clustered</option>
                            <option value="clustered">Clustered</option>
                            <option value="random">Random</option>
                        </select>
                    </label>
                    <label class="field gen-field-cluster gen-field-parametric gen-field-hybrid">
                        <span>Cluster seeds</span>
                        <input id="genClusterSeedsInput" type="number" min="1" value="4" />
                    </label>
                    <label class="field gen-field-cluster gen-field-parametric gen-field-hybrid">
                        <span>Cluster decay (meters)</span>
                        <input id="genClusterDecayInput" type="number" min="50" value="800" />
                    </label>
                    <div class="field gen-field-poi gen-field-hybrid">
                        <span>POI categories</span>
                        <div class="poi-toolbar">
                            <button id="genPoiSelectAllBtn" type="button" class="mini-btn">Select all</button>
                            <button id="genPoiClearBtn" type="button" class="mini-btn">Clear</button>
                            <span id="genPoiCount" class="poi-count">0 selected</span>
                        </div>
                        <details id="genPoiMenu" class="poi-menu" open>
                            <summary>Choose POI types</summary>
                            <div id="genPoiList" class="poi-list"></div>
                        </details>
                    </div>
                    <label class="field gen-field-hybrid">
                        <span>Hybrid POI share: <output id="genHybridShareValue">0.50</output></span>
                        <input id="genHybridShareInput" type="range" min="0" max="1" step="0.05" value="0.5" />
                    </label>
                    <fieldset class="field gen-field-vrptw" id="genVrptwFieldset">
                        <legend>Time-window generation</legend>
                        <label class="field">
                            <span>TW method</span>
                            <select id="genTwMethodSelect">
                                <option value="route_centered" selected>Route-centered (Solomon C-class)</option>
                                <option value="reachable_interval">Reachable-interval (Solomon R/RC)</option>
                            </select>
                        </label>
                        <label class="field">
                            <span>Horizon start (s)</span>
                            <input id="genTwHorizonStartInput" type="number" min="0" value="0" />
                        </label>
                        <label class="field">
                            <span>Horizon end (s)</span>
                            <input id="genTwHorizonEndInput" type="number" min="60" value="86400" />
                        </label>
                        <p class="meta-line">Service times and arrival-time targets are sampled per the chosen TW method, then each window is repaired so depot→customer→depot is feasible.</p>
                    </fieldset>
                    <label class="field gen-field-common">
                        <span>Output root</span>
                        <input id="genOutputRootInput" type="text" value="instances_v2" />
                    </label>
                    <div class="btn-row">
                        <button id="genGenerateBtn" type="button">Generate Data</button>
                        <button id="genDisplayBtn" type="button">Display on Map</button>
                        <button id="genFilesBtn" type="button">Download Files</button>
                    </div>
                </section>

                <section class="card">
                    <h2>Bulk Generation</h2>
                    <button id="openBulkModalBtn" type="button">Open Bulk Configuration</button>
                    <span id="bulkCountBadge" class="poi-count" style="margin-left:0.5rem">0 instances</span>
                </section>

                <section class="card">
                    <h2>Generation Output</h2>
                    <pre id="genResult" class="mono-block">No generation call yet.</pre>
                </section>

                <section class="card note-card">
                    <h2>Notes</h2>
                    <p id="generationNote">Display on Map uses the Paper7 workbench preview endpoint. File generation and HGS solving will be bridged in a later backend slice.</p>
                </section>
            </section>
        </aside>

        <section class="map-wrap card">
            <div id="map"></div>
            <button id="clearBtn" type="button" class="map-clear-btn">Clear Map</button>
            <div id="toast" class="toast"></div>
        </section>
    </main>

    <div id="bulkModal" class="bulk-modal-overlay" hidden>
        <div class="bulk-modal">
            <div class="bulk-modal-header">
                <h2>Bulk Generation</h2>
                <button id="closeBulkModalBtn" type="button" class="bulk-modal-close">&times;</button>
            </div>
            <div class="bulk-modal-body">
                <div class="bulk-modal-columns">
                    <div class="bulk-modal-left">
                        <h3>Combination Builder</h3>
                        <div class="field">
                            <span>Cities</span>
                            <div class="bulk-city-toolbar">
                                <button id="bulkCitySelectAllBtn" type="button" class="mini-btn">All</button>
                                <button id="bulkCityClearBtn" type="button" class="mini-btn">None</button>
                                <span id="bulkCityCount" class="poi-count">0 selected</span>
                            </div>
                            <div id="genBulkCitiesSelect" class="bulk-city-list"></div>
                        </div>
                        <label class="field">
                            <span>Customer sizes (comma-separated)</span>
                            <input id="genBulkCustomersInput" type="text" value="20,50,100" />
                        </label>
                        <div class="field">
                            <span>Demand distributions</span>
                            <div class="bulk-checkbox-row" id="bulkDemandChecks">
                                <label><input type="checkbox" value="1" /> 1 — Unitary</label>
                                <label><input type="checkbox" value="2" /> 2 — Small, large var</label>
                                <label><input type="checkbox" value="3" /> 3 — Small, small var</label>
                                <label><input type="checkbox" value="4" checked /> 4 — Large, large var</label>
                                <label><input type="checkbox" value="5" /> 5 — Large, small var</label>
                                <label><input type="checkbox" value="6" /> 6 — Quadrant-dep.</label>
                                <label><input type="checkbox" value="7" checked /> 7 — Few large, many small</label>
                            </div>
                        </div>
                        <div class="field">
                            <span>Average route sizes</span>
                            <div class="bulk-checkbox-row" id="bulkRouteSizeChecks">
                                <label><input type="checkbox" value="1" /> 1 — Ultra short</label>
                                <label><input type="checkbox" value="2" /> 2 — Very short</label>
                                <label><input type="checkbox" value="3" checked /> 3 — Short</label>
                                <label><input type="checkbox" value="4" checked /> 4 — Medium</label>
                                <label><input type="checkbox" value="5" checked /> 5 — Long</label>
                                <label><input type="checkbox" value="6" /> 6 — Very long</label>
                                <label><input type="checkbox" value="7" /> 7 — Ultra long</label>
                            </div>
                        </div>
                        <label class="field">
                            <span>Problem type for new rows</span>
                            <select id="bulkProblemTypeSelect">
                                <option value="CVRP" selected>CVRP</option>
                                <option value="VRPTW">VRPTW</option>
                            </select>
                        </label>
                        <label class="field">
                            <span>TW method for new VRPTW rows</span>
                            <select id="bulkTwMethodSelect">
                                <option value="route_centered" selected>Route-centered</option>
                                <option value="reachable_interval">Reachable-interval</option>
                            </select>
                        </label>
                        <button id="bulkExpandBtn" type="button">Expand to Table</button>
                    </div>

                    <div class="bulk-modal-right">
                        <div class="bulk-toolbar">
                            <button id="bulkAddRowBtn" type="button" class="mini-btn">Add Row</button>
                            <button id="bulkDeleteSelBtn" type="button" class="mini-btn">Delete Selected</button>
                            <button id="bulkClearBtn" type="button" class="mini-btn">Clear All</button>
                            <button id="bulkImportCsvBtn" type="button" class="mini-btn">Import CSV</button>
                            <button id="bulkExportCsvBtn" type="button" class="mini-btn">Export CSV</button>
                            <input id="bulkCsvFileInput" type="file" accept=".csv,.txt" style="display:none" />
                            <span id="bulkModalCount" class="poi-count">0 instances</span>
                        </div>
                        <div class="bulk-table-wrap">
                            <table class="bulk-table" id="bulkTable">
                                <thead>
                                    <tr>
                                        <th><input type="checkbox" id="bulkSelectAll" /></th>
                                        <th>Type</th>
                                        <th>City</th>
                                        <th>n</th>
                                        <th>Demand</th>
                                        <th>Route Size</th>
                                        <th>Method</th>
                                        <th>Seed</th>
                                        <th>Depot</th>
                                        <th>Customer</th>
                                        <th>TW Method</th>
                                        <th>Intersections</th>
                                        <th>Clusters</th>
                                        <th>Decay</th>
                                        <th>Hybrid</th>
                                        <th>Categories</th>
                                        <th></th>
                                    </tr>
                                </thead>
                                <tbody id="bulkTableBody"></tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
            <div class="bulk-modal-footer">
                <button id="genBulkBtn" type="button">Generate &amp; Download All</button>
                <button id="closeBulkModalBtn2" type="button" class="bulk-modal-cancel-btn">Close</button>
            </div>
        </div>
    </div>

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
