# Benchmarks

Reference material on the data: what the problem types and objectives are, what every family contains, and the
exact on-disk contract.

## Problem types

| Type | Arc costs | Time windows | Checker | Objectives |
|---|---|---|---|---|
| CVRP | static (euclidean or a distances sidecar) | no | `check_solution` | MonoCost |
| VRPTW | static | yes | `check_solution` | HierarchicalVehicleCost (vehicles first, then cost), MonoCost |
| TDVRP | time-dependent arrival-time functions (ATF) per arc | no | `check_td_solution` | Duration, FleetCostDuration |
| TDVRPTW | time-dependent | yes | `check_td_solution` | Duration, FleetCostDuration |

Static families use `binary64-exact-v1`. Time-dependent families use `td-binary64-exact-v1`. Both evaluate the materialized binary64 operands exactly and store a rational objective. The displayed binary64 cost rounds once, after evaluation.

The website's [objectives page](/objectives/) explains how each objective is priced. A solution is *valid* only when
the checker returns `valid`; the eight failure statuses (`invalid_customer_index`, `customer_served_multiple_times`,
`vehicle_capacity_exceeded`, `time_window_violated`, `not_all_customers_served`, `too_many_vehicles_used`,
`objective_value_mismatch`, `route_timing_infeasible`) are in the [checker reference](../reference/api/lib/checker.md).

## Families

11 families today, listed with their repositories and licenses on the [Families](families/index.md) pages:

- **Historical VRPTW**: Sintef2008 (float costs, hierarchical objective), Dimacs2021 (integerised, mono-cost),
  Ortec2022 (CC BY-NC 4.0).
- **Time-dependent conversions**: Dabia2013, Ari2018, Vu2020, Rifki2020, Lera2026 (`igp-profile` model, compact IGP specifications instead of ATF sidecars), Blauth2024 (real OSM networks, Uber speeds, millisecond time unit, `FleetCostDuration`).
- **Generated collections** (family-first repositories holding several problem-type trees and shared sidecars):
  Poryos2026 (5 cities × 6 sizes × 2 sampling methods, all four problem types) and Mamut2026 (100 designed CVRP bases
  under three arc-cost metrics).

## Layouts and naming

Every family is a collection at `benchmarks/<Family>/`, rooted by a `mamut-collection.json` marker (`format: mamut-collection`, version 1) whose `layout_version` gives the path shape. Both layouts are discovered by `mamut_routing_lib.artifacts.discover_benchmark_instances`:

- **Layout 2** (classic families): `benchmarks/<Family>/<ProblemType>/[<subset>/]n=<N>/<instance>.vrp.json` with the BKS next to it as `<base>.bks.<ObjectiveFunction>.json`, and the time-dependent sidecars under `benchmarks/<Family>/sidecars/`.
- **Layout 1** (generated collections): `benchmarks/<Family>/{CVRP,VRPTW,TDVRP,TDVRPTW}/...` plus `benchmarks/<Family>/sidecars/`.

Large sidecars (distance matrices, ATFs, road graphs, geo) are sha256-pinned from the instance: the checker never
reads geo data, and a sidecar that does not match its pin is rejected on load.

## Formats

The [Formats](formats/index.md) page maps every artifact to the module that defines it. The module docstrings are
normative; the [API reference](../reference/api/index.md) renders them.
