# CVRPLIB `.vrp` export

Classic solvers read the TSPLIB-derived CVRPLIB text, not `.vrp.json`. `mamut_routing_lib.cvrplib` renders any
**static** instance into it with one contract shared by three producers that must emit identical bytes: the
`mamut-routing export vrp` CLI, the tools' workbench ("Download .vrp") and the website's client-side writer
(`site.js`);
`tests/test_site_assets_vrp_export.py` runs the JavaScript writer against the Python one, and
`tests/test_vrp_export_regression.py` checks every committed `.vrp` byte for byte.

```text
NAME : <instance_name>
COMMENT : <comment>
TYPE : CVRP | CVRPTW
DIMENSION : <num_customers + 1>
[VEHICLES : <num_vehicles>]            only when the fleet is fixed
EDGE_WEIGHT_TYPE : EXPLICIT | EUC_2D
[EDGE_WEIGHT_FORMAT : FULL_MATRIX]     EXPLICIT only
CAPACITY : <vehicle_capacity>
[EDGE_WEIGHT_SECTION + rows]           EXPLICIT only
NODE_COORD_SECTION      "<i+1> <x> <y>"
DEMAND_SECTION          "<i+1> <demand>"
[TIME_WINDOW_SECTION    "<i+1> <ready> <due>"]   CVRPTW
[SERVICE_TIME_SECTION   "<i+1> <service>"]       CVRPTW
DEPOT_SECTION / <depot+1> / -1 / EOF
```

Rules:

- node ids are 1-based; the depot is `depot + 1`;
- **`EXPLICIT` with the full matrix is the default**: the solver sees exactly the published costs (3-decimal floats
  for the collections, integers for Dimacs/Ortec, full-precision floats for Sintef);
- number formatting is value-driven so the JavaScript mirror (no int/float distinction) matches: collection arc costs
  print with the source's `decimals`; other vectors print as integers when every entry is integral, else as shortest
  round-trip floats; coordinates with 6 decimals when not all integral;
- `EUC_2D` (and the Solomon `.txt` variant for VRPTW) is opt-in, and offered only where the published costs are the coordinates' Euclidean distances rounded at most to the nearest unit (`coordinates_define_arc_costs`: every arc between `floor` and `ceil` of `hypot`). Sintef2008 and the euclidean collections qualify; Dimacs2021 does not, because its costs are `trunc(10 × hypot)` on the unscaled coordinates, so a coordinates-only file would describe another instance. It drops the matrix and
  readers compute `nint(hypot)`, which is still **not** the published cost, so BKS values do not transfer;
- time-dependent instances are refused (`UnsupportedInstanceError`): they have no static matrix.

The committed `.vrp` files next to the collection CVRP instances (`n <= 200`) are the `EXPLICIT` output.
