# User guide

Task-oriented pages for people who use the benchmarks and the tools. The [Getting started](../getting-started/index.md)
page covers installation and the first commands.

## The website

The website is a static tree built from the benchmark repository; it has no compute endpoint.

| Route | What you find |
|---|---|
| `/benchmarks/` | Problem type → family → metric variant → place → size → subset → instance. Each level is a filterable catalog. |
| `/benchmarks/<type>/<family>/` | Family page: description, license, changelog link, instance counts, BKS coverage. |
| instance page | Instance descriptors, the BKS routes on a map (road-following geometry where cached), artifact downloads (`.vrp.json`, BKS, sidecars, `.vrp ↓`), objective and checker report. |
| `/objectives/` | The four objective functions and how the checker prices each. |
| `/history/` | Publication history: every snapshot with families/instances/BKS added, removed, improved or regressed. |
| `/workbench/` | Upload your own `.vrp.json` + solution and visualise it (straight lines); the generation tabs moved to the local tools. |
| `/project/` | Authors, funding, citing, glossary, FAQ, legal mentions (the same texts as the [About](../about/index.md) pages here). |

## The local workbench GUI

`mamut-tools gui start` launches a loopback server (token-protected URL, opened in your browser) with the
generation, solving and rendering flows the website used to host:

```bash
mamut-tools gui start [--port N] [--no-open] [--output-dir DIR]
mamut-tools gui status
mamut-tools gui stop
mamut-tools gui run          # foreground, for development (default port 8788)
```

The workspace directory (`--output-dir`, `MAMUT_TOOLS_WORKSPACE`, `<repo>/.cache/mamut-tools` or
`~/.cache/mamut-tools`, in that order) holds `osmdata/`, `instances/`, `solutions/<instance-id>/` and
`state/{gui.json,preferences.json,jobs/,logs/}`. Long operations are durable jobs with logs; solver runs are
checker-validated, kept across restarts and comparable. Set `MAMUT_BASEMAP_API_KEY` for the CARTO vector basemaps
(the key is visible to the browser by design).

## Generate instances

| Command | Purpose |
|---|---|
| `mamut-tools osm fetch-city` | Geocode a city (Nominatim) and download a purpose-filtered OSM extract (tiled Overpass queries, persistent tile cache). Profiles: `road_cache` (road classes only), `generation` (roads + POIs), `full`. |
| `mamut-tools osm validate` / `refresh-pois` | Reject incomplete extracts; backfill way/relation-mapped amenities (`--check` audits only). |
| `mamut-tools roadgraph info` | Build the drivable road graph of an extract and print its statistics. |
| `mamut-tools generate preview` | GeoJSON preview of a customer selection, nothing written. |
| `mamut-tools generate single` | One CVRP base instance under the three metrics (`euclidean`, `shortest`, `fastest`) with sidecars; `--vrptw` adds the time-window twin. |
| `mamut-tools generate derive-vrptw` | The fastest-metric VRPTW twin of an existing CVRP base. |
| `mamut-tools generate derive-td` | TDVRP + TDVRPTW twins: traffic overlay (`--model bpr|wave`, `--intensity light|moderate|heavy`, `--all` for the six) → arrival-time functions → time-window lift. |
| `mamut-tools generate materialize-distances` | Rebuild the sha256-pinned distance sidecars of large published instances. |
| `mamut-tools solve` | Solve a `.vrp.json` with PyVRP (or KAYROS for time-dependent Duration, `kayros` extra); `--update-bks` writes an improved BKS. |
| `mamut-tools convert blauth2024` | Convert the upstream vrptdt-benchmark into the canonical Blauth2024 family. |

Batch family generation (many cities × sizes) is deliberately not a CLI command: campaigns are scripts that call
the `mamut_routing_tools.family` and `mamut_routing_tools.campaign` library, see
[Generate or convert a family](../maintainer-guide/generate-a-family.md).

External services used: Nominatim and the Overpass mirrors for OSM data, CARTO for optional basemaps. Nothing
is sent anywhere else.

## Cite and reuse

[Citing](citing.md) gives the citation records and the Software Heritage identifiers. Code is MIT; data is under
family-specific licenses (ODbL 1.0 for the OSM-derived Poryos2026 and Mamut2026 artifacts, CC BY-NC 4.0 for
Ortec2022 and Blauth2024), listed on every family page and in the repository `NOTICE`.
