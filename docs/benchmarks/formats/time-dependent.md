# Time-dependent instances (TDVRP, TDVRPTW)

Models in `mamut_routing_lib.td.models`; sidecars in `td.artifacts`, `td.igp`, `td.roadgraph`; the function algebra
in `td.pwlf`; the checker in `td.checker`.

## The instance

A TD instance has no `arc_costs`: travel is described by one **arrival-time function** per arc, an NDCPWLF
(non-decreasing continuous piecewise-linear function) mapping departure time to arrival time. Fields shared by
`BenchmarkInstanceTDVRPTW` and `BenchmarkInstanceTDVRP`:

| Field | Notes |
|---|---|
| `instance_name`, `instance_origin`, `benchmark_name`, `num_customers`, `num_vehicles`, `vehicle_capacity`, `coordinates`, `demands`, `depot`, `reference_lla` | as for static instances |
| `service_times` | int or float per node |
| `horizon` | `[start, end]` of the planning horizon; every ATF is defined on it |
| `fleet_fixed_cost` | per used vehicle, for the `FleetCostDuration` objective (Blauth2024: 36 000 000 ms) |
| `td` | the travel model reference, one of the three below |
| TDVRPTW only: `time_windows` | |

Time units are the family's (seconds for most, integer milliseconds for Blauth2024); the checker never converts.

## The three travel models (`td.model`)

| `model` | Reference | Where the ATFs come from |
|---|---|---|
| `atf-ndcpwlf` | `TDArrivalFunctionsRef`: `atf_path`, `atf_sha256` | shipped sidecar `<base>.atf.json[.gz]` (format `mamut-td-atf` v1): one ATF per arc of the complete graph |
| `igp-profile` | `TDIGPProfileRef`: `time_periods`, `speeds` (per category), `categories_path` + pin, `atf_sha256` | materialized on load: Euclidean distances × the Ichoua-style speed profile of each arc's category, consolidated exactly by `build_arc_atf`; the `<base>.igp.json[.gz]` sidecar (format `mamut-td-igp-categories` v1) is the symmetric category matrix. Lera2026 ships this way (50 MB instead of tens of GB) |
| `road-graph` | `TDRoadGraphRef`: `graph` pin, `traffic` pin, `sample_step`, `simplify_tolerance`, `atf_sha256` | materialized on load from two sidecars: the road graph `<base>.road.json[.gz]` (format `mamut-road-graph` v2: directed edges with length and free-flow `speed_limit`, `vertex_lonlat`, node → vertex map) and the traffic overlay `<base>.traffic-<model>-<intensity>.json[.gz]` (format `mamut-traffic-overlay` v1: per-edge piecewise-constant speeds over the horizon bins, clamped at free flow). Materialization is a pinned deterministic pipeline: tie-break-pinned Dijkstra fastest-path tree over free-flow times, exact per-edge ATFs from the overlay, exact grid sampling down the tree, collinear drop then Douglas–Peucker simplification; pure IEEE-754 doubles, so `atf_sha256` is reproducible on any machine |

`load_td_instance` returns a `LoadedTDInstance` with the materialized `InstanceATFs`, checked against `atf_sha256`.
The website materializes the two compact models at build time into `dist/atf-cache/` for instances up to
`--atf-max-n` customers.

## The NDCPWLF primitive (`td.pwlf`)

A function is two parallel non-decreasing arrays `xs` and `ys`; linear between breakpoints; duplicate `xs` encode a
step (evaluation returns the smallest value), duplicate `ys` a plateau (waiting). Composition is the two-pointer event
merge of Visser & Spliet (2020) without normalization, interpolating between enclosing breakpoints and clamping
monotone, so the invariant holds structurally under any rounding. `make_theta` and `make_service_theta` build the
ready-time functions of a time window and of a service. The module is the pure-Python reference: reimplementations
must be bit-identical.

## The checker (`td.checker`)

`check_td_solution` prices a solution exactly (no epsilon) under `Duration` or `FleetCostDuration`
(`TD_OBJECTIVES`): departure at the depot within the horizon, arrival by composing the arc ATFs, waiting at windows,
service, return. It returns the same status vocabulary as the static checker plus route-level evaluations
(`TDRouteEvaluation`: feasibility, duration, departure time). `create_td_bks_from_solution` and the TD store
(`td.bks`) use it; the static `check_solution` refuses TD instances. KAYROS is the reference solver built on this
checker.
