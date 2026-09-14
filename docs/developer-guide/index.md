# Developer guide

## Architecture

```
benchmarks/ (data)  ──►  mamut_routing_lib (contract: models, checkers, BKS, remote, export)
                              ▲                    ▲
                              │                    │
                 mamut_routing_tools          mamut_routing_publish
                 (OSM, road graphs,           (payload JSON + HTML shell, caches,
                  generation, solving,         docs, releases, static server)
                  geometry, workbench GUI)          │
                                                    ▼
                                             dist/ ──► site.js renders every page client-side
```

- The **lib** is a pure contract and runtime layer: no site logic, no solver besides the optional PyVRP wrapper.
- The **tools** are the only place with compute: Overpass/Nominatim access, the road-graph engine (a faithful
  port of the former Julia pipeline), generation, traffic models, converters, the loopback FastAPI workbench.
- The **publisher** turns the benchmark tree into `site-payloads/*.json` and thin HTML shells; `site.js` renders
  them (including a hand-written markdown mini-renderer for the project pages). Build-time caches (ATF, route
  geometry) are content-addressed and incremental.
- The **website** has no server-side compute: `serve` and nginx are static file servers.

## Development setup

```bash
git clone git@github.com:ANR-MAMUT/MAMUT-routing.git && cd MAMUT-routing
git submodule update --init MAMUT-routing-lib MAMUT-routing-tools     # tooling only
uv sync                                                              # dev + docs groups
uv run pytest                                                        # publisher + lib suites
uv run --project MAMUT-routing-tools pytest                          # tools suite
uv run mkdocs serve                                                  # this documentation, live reload
```

The JavaScript `.vrp` writer is tested under Node when available (`tests/test_site_assets_vrp_export.py`).
The tools ship two manual parity scripts under `tests/parity/` (road graph and route geometry against previously
published artifacts).

## Conventions

- **Determinism.** Every published byte is reproducible: sorted JSON keys, gzip `mtime=0`, fixed zip
  timestamps, sha256 pins, seeded generation.
- **The checker is the authority.** Costs stored anywhere are checker costs.
- **Module docstrings are the spec.** Formats, invariants and design rationale live in the docstring of the
  module that owns them and are rendered in the [API reference](../reference/api/index.md).
- **Reports as decision records.** Non-trivial decisions get a dated report in `docs/reports/`
  ([index](../reports/index.md)); reports are never rewritten, later ones supersede.
- **Satellites are optional.** Everything must work with empty satellite directories.

## Contributing

Issues and pull requests on the [GitHub repositories](https://github.com/ANR-MAMUT). New benchmark material,
problem classes and objective functions are welcome; contributors are listed in [Authors](../about/authors.md).
