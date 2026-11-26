# Formats

Edition `r1` uses `binary64-exact-v1` for static instances and `td-binary64-exact-v1` for TD instances. Both profiles evaluate the materialized binary64 operands exactly. The BKS stores the certified fraction in `metadata.standard.authoritative_cost` and its binary64 display in `cost`. [Solution records](solutions.md) · [TD evaluation and historical replay](time-dependent.md)

Every artifact is JSON validated by a pydantic model with `extra="forbid"`; the normative description of each
format is the docstring of the module that owns it, rendered in the [API reference](../../reference/api/index.md).
These pages are the guided tour.

| Page | Covers |
|---|---|
| [Layouts, naming and pins](layouts.md) | the 2 layout versions of the family collections, `mamut-collection.json`, file names, sha256-pinned sidecar references |
| [Static instances](instances.md) | CVRP and VRPTW `.vrp.json`, embedded versus slim (collection) instances, arc-cost sources, metadata |
| [Time-dependent instances](time-dependent.md) | the `td` block and its three travel models, ATF sidecars, IGP profiles, road graphs and traffic overlays, the piecewise-linear primitive |
| [Distances and geo sidecars](sidecars.md) | the distance matrix and the map-drawing sidecar |
| [Solutions, BKS and optimality](solutions.md) | solution files, BKS files, the checker statuses, optimality metadata |
| [CVRPLIB `.vrp` export](cvrplib-export.md) | the classic-format export contract shared by the CLI, the workbench and the website |
| [Edition r1 migration and replay](edition-r1.md) | migration counts, costs, witnesses and public replay examples |
| [Release archives](releases.md) | per-family zip archives and `snapshot-manifest.json` |

Common rules, everywhere:

- **Canonical JSON.** Sorted keys, deterministic serialization; gzip sidecars are written with `mtime=0`.
- **Sha256 pins hash the uncompressed canonical bytes**, so `.json` and `.json.gz` forms of a sidecar share one pin.
- **The checker's cost is the stored cost.** Solutions carry `cost: null` or the checker's value; nothing else.
- **Formats are tagged and versioned** (`format`, `format_version`) so readers can refuse what they do not know.
