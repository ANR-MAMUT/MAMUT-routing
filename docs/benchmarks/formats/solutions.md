# Solutions, BKS and optimality

## Solution (`BenchmarkSolution`)

```json
{"instance_name": "...", "routes": [[3, 1, 2], [5, 4]], "cost": null, "metadata": {}}
```

Routes list customer indices (1-based customers, the depot implicit at both ends); `cost` may be null (the checker
prices it) or the exact expected value (the checker then refuses any deviation). `metadata` is free-form.

## BKS (`BenchmarkBKS`)

The same plus `objective_function`, stored as `<base>.bks.<ObjectiveFunction>.json` next to the instance, one file
per objective. Written only through the store functions, which guarantee:

- `cost` is the checker's cost (`create_bks_from_solution` / `create_td_bks_from_solution`);
- `metadata.authors` is present and non-empty; `validated_cost`, `validated_num_routes` and `date` are filled;
- a stored BKS is replaced only by a strictly better one under the objective (`is_better_solution`), after the stored
  file was itself re-validated (`save_bks_if_improved`, `save_td_solution_as_bks_if_improved`).

Provenance fields are free but expected for campaigns: `method`, `seed`, `time_limit_s`, `solver_version`, `machine`,
`campaign`.

## Objectives

| Objective | Order | Families |
|---|---|---|
| `MonoCost` | total arc cost | CVRP, Dimacs2021, generated VRPTW |
| `HierarchicalVehicleCost` | fewer routes first, then cost | Sintef2008, Ortec2022 |
| `Duration` | total route duration (travel + waiting + service) | TD families |
| `FleetCostDuration` | duration + `fleet_fixed_cost` × used vehicles | Blauth2024 |

## Checker statuses (`SolutionCheckStatus`)

`valid`, `invalid_customer_index`, `customer_served_multiple_times`, `vehicle_capacity_exceeded`,
`time_window_violated`, `not_all_customers_served`, `too_many_vehicles_used`, `objective_value_mismatch`,
`route_timing_infeasible`. `check_solution` (static) and `check_td_solution` (time-dependent) return a result with
the status, the routing cost, the route count and an error message.

## Optimality (`OptimalityMetadata`)

A claim of optimality is `metadata.optimality`, validated:

| Field | |
|---|---|
| `proven` | literally `true` |
| `prover`, `certificate`, `date` | required: who proved it, what the certificate is (a file, a log, a bound argument), when |
| `arithmetic`, `proven_optimum`, `dual_bound`, `wall_time_s`, `time_limit_s`, `checker`, `campaign`, `note` | optional |

For TD stores, `annotate_td_bks_optimality` writes it after re-validating the stored BKS; a declared
`proven_optimum` must equal the stored cost (a dust-level difference needs a `note`). The website shows proven
optima distinctly.
