# Environment variables

| Variable | Read by | Meaning |
|---|---|---|
| `MAMUT_ROUTING_ROOT` | lib, publisher | Repository root. The publisher CLI falls back to the working directory when it is unset; the **library** does not: `get_default_mamut_routing_root()` raises, so Python callers pass explicit paths (`discover_benchmark_instances(benchmarks_root=...)`) or set the variable. |
| `MAMUT_ROUTING_BENCHMARKS_ROOT` | lib, `mamut-routing` | Benchmarks root: the library's default before `MAMUT_ROUTING_ROOT/benchmarks`; the CLI's default for `--benchmarks-dir` (the CLI itself falls back to `./benchmarks`). |
| `MAMUT_ROUTING_RELEASE_REPO` | `mamut-routing remote` | GitHub repository whose releases carry the archives (`--repo`). |
| `MAMUT_ROUTING_GITHUB_TOKEN` | `mamut-routing remote` | Token for the GitHub API (`--token`), for rate limits or private releases. |
| `MAMUT_ROUTING_TEST_NETWORK` | lib tests | Set to `1` to run the opt-in network test. |
| `MAMUT_BASEMAP_API_KEY` | `site build`, `site webapp`, `mamut-tools gui` | CARTO basemaps key written into the workbench page (visible to browsers by design; never commit it). |
| `MAMUT_TOOLS_WORKSPACE` | `mamut-tools` | Workspace directory (after `--output-dir`, before `<repo>/.cache/mamut-tools` and `~/.cache/mamut-tools`). |
| `MAMUT_GUI_WORKSPACE`, `MAMUT_GUI_TOKEN` | `mamut-tools gui` (internal) | Set by `gui start` for the detached server process. |

Deployment scripts read their own set (`ENV_FILE`, `START_API_ONLY`, `SKIP_SOURCE_UPDATE`, `SITE_BUILD_*`,
`ROUTE_GEOMETRY_JOBS`, `KEEP_RELEASES`, ...); they are documented in the deploy repository.
