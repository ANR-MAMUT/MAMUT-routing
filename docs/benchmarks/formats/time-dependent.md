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
monotone, so the invariant holds structurally under any rounding. The module is the pure-Python reference:
reimplementations must be bit-identical.

## The checker (`td.checker`)

`check_td_solution` prices a solution exactly (no epsilon) under `Duration` or `FleetCostDuration`
(`TD_OBJECTIVES`): departure at the depot within the horizon, arrival by composing the arc ATFs, waiting at windows,
service, return. It returns the same status vocabulary as the static checker plus route-level evaluations
(`TDRouteEvaluation`: feasibility, duration, departure time). `create_td_bks_from_solution` and the TD store
(`td.bks`) use it; the static `check_solution` refuses TD instances. KAYROS is the reference solver built on this
checker.

### The checker contract: `td-fold/2`

Every stored TD cost is the value of one versioned algorithm, `TD_CHECKER_CONTRACT`. The current contract is
**`td-fold/2`** (mamut-routing-lib ≥ 0.12.0). Any reimplementation that writes BKS (KAYROS, a solver's own
evaluator) must reproduce it **bit for bit**; the store compares exact doubles.

A route `r = (v_1, …, v_m)` from depot `0` is folded left to right into its ready-time function `δ_r`, which maps
depot departure times to the time the vehicle is back:

1. **Departure window.** `lo = max(horizon.start, e_0)`, `hi = min(horizon.end, l_0)` (the depot window, when the
   instance has windows). Empty if `lo > hi`.
2. **First arc.** `acc = restrict_domain(α_{0,v_1}, lo, hi)`: every breakpoint of the arc inside `[lo, hi]` is kept
   verbatim, both points of a step at a window end included; a window end strictly inside a piece is evaluated
   there (slope-one rule below).
3. **Each vertex `v`.** `acc = apply_ready_time(acc, earliest=e_v, latest=l_v, service_time=s_v)`; on TDVRP
   vertices `earliest = latest = None`. Over the breakpoints `(x_k, y_k)` of `acc`, in order:
   - a kept breakpoint becomes `(x_k, max(y_k, e_v) + s_v)`, computed with one comparison and one add;
   - where a piece strictly crosses `e_v` (`y_{k-1} < e_v < y_k`) the point `(x*, e_v + s_v)` is inserted first,
     `x*` being the piece's inverse interpolation at `e_v`;
   - at the first `y_k > l_v` the fold stops after inserting `(x*, l_v + s_v)` if `y_{k-1} < l_v`; a piece that
     crosses both bounds emits the `e_v` crossing first. If already `y_0 > l_v`, the route is infeasible.
4. **Next arc.** `acc = α_{v, w}.compose(acc)` with the slope-one rule.
5. **Return.** `acc = α_{v_m, 0}.compose(acc)`, then the depot due-date cut
   `apply_ready_time(acc, earliest=None, latest=l_0, service_time=0)` (no waiting: the route ends on arrival).
6. **Duration.** `min_k (y_k − x_k)` over the breakpoints of `δ_r`, and the earliest `x_k` attaining it is the
   departure time. The solution cost sums route durations in canonical order (routes sorted by first customer),
   then adds `fleet_fixed_cost × routes` once for `FleetCostDuration`.

Interpolation, used inside `compose`, `restrict_domain` and the crossings above, on a piece
`(x_lo, y_lo)–(x_hi, y_hi)`:

| | general piece | slope-one piece (`y_hi − y_lo == x_hi − x_lo`) |
|---|---|---|
| value at `x` | `y_lo + ((x − x_lo) / (x_hi − x_lo)) × (y_hi − y_lo)` | `y_lo + (x − x_lo)` |
| abscissa of value `v` | `x_lo + ((v − y_lo) / (y_hi − y_lo)) × (x_hi − x_lo)` | `x_lo + (v − y_lo)` |

Every emitted point is clamped monotone against the previous one (`x = max(x, x_prev)`, `y = max(y, y_prev)`)
and exact duplicates are dropped. On integer data whose pieces have slope 0, 1 or are vertical (stepwise travel
times, as in Rifki2020) the fold is exact: waiting, service and slope-one travel never leave the integers.

**History.** `td-fold/1` (lib < 0.12.0) composed each vertex map `θ(t) = max(t, e) + s` as if it were an arc, so a
ready time came out of the ratio interpolation above and could be off by an ulp; on stepwise ATFs such an ulp
could land past a vertical step and read its upper branch. Rifki2020's Rifki-30 (n = 30) was priced 8292 instead
of 8267, and a feasible route could be declared infeasible. `td-fold/2` removes the interpolation from vertex maps
and from slope-one travel. The 2026-09-24 re-pricing moved 870 stored costs, all but three by a few ulps (see
[Solutions](solutions.md#re-pricing)). Test vectors for reimplementations are in
`MAMUT-routing-lib/tests/fixtures/td/fold-v2-vectors.json`.

A cost that differs from the checker's is refused as `OBJECTIVE_VALUE_MISMATCH`. After a contract change the stored
BKS are re-priced with `mamut-routing bks reprice-td` (runbook: *Re-pricing after a checker-contract change* in the
maintainer guide); a solver still on the old contract will see about a quarter of its TD submissions refused until
it is updated.
