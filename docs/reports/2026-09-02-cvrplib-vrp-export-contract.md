# CVRPLIB `.vrp` export contract

*2026-09-02.* Format decision record for the classic-format export added to
`mamut-routing-lib` (`mamut_routing_lib.cvrplib`, `mamut-routing export vrp`),
reused by the MAMUT-routing-tools workbench ("Download .vrp") and mirrored
client-side on the benchmark website (".vrp ↓" chips). The three producers must
emit the same bytes; the website test suite runs the JavaScript mirror under
node against the Python writer, and a parent-repo regression test checks the
Python writer against every `.vrp` committed next to the collection CVRP
instances.

## Why

Every instance is published as `.vrp.json`. Classic solvers (HGS-CVRP, FILO,
LKH-3 wrappers, VRPLIB/PyVRP loaders, Solomon-based VRPTW codes) read the
TSPLIB-derived CVRPLIB text instead. Until now `.vrp` files were a
generation-time side effect of the family builder (CVRP only, `n <= 200`).

## Layout

```
NAME : <instance_name>
COMMENT : <comment>
TYPE : CVRP | CVRPTW
DIMENSION : <num_customers + 1>
[VEHICLES : <num_vehicles>]            only when the fleet is fixed (num_vehicles not null)
EDGE_WEIGHT_TYPE : EXPLICIT | EUC_2D
[EDGE_WEIGHT_FORMAT : FULL_MATRIX]     EXPLICIT only
CAPACITY : <vehicle_capacity>
[EDGE_WEIGHT_SECTION + (n+1) rows]     EXPLICIT only
NODE_COORD_SECTION      "<i+1> <x> <y>"
DEMAND_SECTION          "<i+1> <demand>"
[TIME_WINDOW_SECTION    "<i+1> <ready> <due>"]   CVRPTW
[SERVICE_TIME_SECTION   "<i+1> <service>"]       CVRPTW
DEPOT_SECTION
<depot + 1>
-1
EOF
```

Lines end with `\n`, the file ends with `EOF\n`. Node ids are 1-based (JSON
index + 1); the JSON `depot` (0-based) becomes `<depot + 1>`. Coordinates are
the stored ENU metres (x east, y north), never lon/lat.

## Number formatting (value-driven, so JSON parsed without an int/float distinction gives the same bytes)

| Vector | Rule |
|---|---|
| Arc costs of a collection source (`distances-sidecar`, `euclidean`) | fixed `decimals` places (the source's `decimals`, 3): `0.000`, `2731.469` |
| Any other vector (embedded matrices, demands, time windows, service times) | integers when every entry is integral, else shortest round-trip floats with `.0` kept for integral entries (`0.0 89.89438247187641`) |
| Coordinates | integers when every entry is integral, else 6 decimals (`-500.874011`) |

Non-goal: exact decimal ties (dyadic values such as `x.0078125`) round
half-even in Python and half-up in JavaScript. They do not occur in the corpus.

## COMMENT

- Collection instances (Poryos2026, Mamut2026), reconstructed from the JSON and
  byte-identical to the committed files:
  `"{family} {metric} metric; city {city}; [No of trucks: {num_vehicles_lb} (lower bound, fleet not fixed); ]3-decimal seconds/meters; ENU ref in {instance_name}.vrp.json"`,
  the fleet clause only for families whose names carry `k` (Mamut2026).
  VRPTW collection instances append `; time windows set {tw_set.name}`.
- Historical instances: `"{family} {instance_name}; authors: {authors}; converted from MAMUT-routing .vrp.json"`.
- `EUC_2D` appends `; EUC_2D: costs are TSPLIB nint distances, not the published 3-decimal costs`.
- `--comment` / `VrpExportOptions.comment` overrides the whole line.

## Policies

- **EXPLICIT is the default everywhere.** The published objective is the
  3-decimal (or integer) matrix; `EUC_2D` is an opt-in for euclidean-metric
  instances only and changes the objective (`nint`), which the comment says.
- **Solomon `.txt`** (`--format solomon`) is VRPTW + euclidean only:
  `NUMBER` is the fixed fleet or the customer count; ids are 0-based with the
  depot first; columns right-aligned to width 10.
- **Time-dependent instances are refused** (no static matrix). The CLI errors
  on explicit TD paths and skips scanned ones with a warning; the site and the
  workbench do not offer the option.
- Existing outputs are never overwritten without `--force` / `overwrite=True`.
