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

- `cost` is the checker's cost (`create_bks_from_solution` / `create_td_bks_from_solution`), for routes stored in
  **canonical order** (sorted by first customer) and priced in that order, so the float total is reproducible;
- `metadata.authors` is present and non-empty; `validated_cost`, `validated_num_routes` and `date` are filled;
- the candidate is itself a valid solution of the instance it is named after;
- a stored BKS is replaced only by a strictly better one under the objective, after the stored file was itself
  re-validated (`save_bks_if_improved`, `save_td_solution_as_bks_if_improved`). Static stores (lib ≥ 0.12.0) compare
  **exact decimal costs** (`is_better_exact`: every arc cost is read as the decimal its JSON text denotes and summed
  as a fraction), so reordering, reversing or re-summing an incumbent can no longer pass for an improvement by one
  float ulp. A tie keeps the incumbent and is reported as `BKSUpdateResult(action="kept_existing", tie=True)`.

Provenance fields are free but expected for campaigns: `method`, `seed`, `time_limit_s`, `solver_version`, `machine`,
`campaign`. A BKS stored from a registry solve (`mamut-routing solve --save-bks`, `submit_bks(...,
metadata=solved.bks_metadata())`, `mamut-tools bks-campaign harvest`) carries `solver`, `method`, `solver_version`,
`seed`, `time_limit_s`, `wall_time`, `solver_cost` (the solver's own objective in instance units, informational),
`cost_exact` (whether the solver worked on exactly the published costs or on rounded ones), `machine` (the CPU model)
and, for external executables, `executable_sha256` and `input_sha256`. BKS files are published: they never record a
hostname.

## Solution files from other solvers

`mamut-routing check`, `mamut-routing bks submit` and the tools workbench's import read:

| Format | Shape |
|---|---|
| CVRPLIB `.sol` | `Route #1: 3 1 2` lines (`Route 1:` also accepted) and an optional `Cost <value>` line; costs in exponent form (`1.2345E7`, `1.23457e+06`) are read |
| JSON | `{"routes": [[...]], "cost": ...}` (a solution or BKS file) or a bare array of routes |
| LKH-3 `MTSP_SOLUTION_FILE` | a `<name>, Cost: <penalty>_<cost>` header and one `1 a b c 1 (#3)  Cost: x` line per vehicle; node 1 is the depot, a non-zero penalty is refused |

Stop ids are mapped onto the library's (depot 0, customers 1..n): customers numbered 1..n with an optional 0 as a
depot marker (CVRPLIB), or 0..n-1 when the file covers exactly those ids (`--ids one-based|zero-based` forces a
reading; `check` says when it read a file as 0-based). Under 1..n a 0 inside a route is a return to the depot: the
route is split there into two trips, as written. A file whose ids fit neither, visits a customer twice or misses one
is refused, never reinterpreted. An objective that does not apply to the instance (`Duration` on CVRP, `MonoCost`
on a TD instance) is a usage error. The
declared cost is never trusted: the checker prices the routes, and a disagreeing declaration is reported (it usually
means another metric variant or a rounded matrix).

## Objectives

| Objective | Order | Families |
|---|---|---|
| `MonoCost` | total arc cost | CVRP, Dimacs2021, Ortec2022, generated VRPTW |
| `HierarchicalVehicleCost` | fewer routes first, then cost | Sintef2008 |
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

## Re-pricing

A TD cost is the value of the checker contract in force when it was priced (see
[Time-dependent instances](time-dependent.md#the-checker-contract-td-fold2)). When the contract changes, every stored
TD BKS is re-priced with `mamut-routing bks reprice-td <tree> --write`, which never changes a route. It rewrites
the checker outputs that moved (`cost`, `metadata.validated_cost`, `metadata.route_durations`,
`metadata.route_departure_times`) and, when the cost moved, records:

```json
"repriced": {"previous_cost": 8292.0, "checker": "mamut-routing-lib td checker, contract td-fold/2 (lib >= 0.12.0)",
             "contract": "td-fold/2", "date": "2026-09-24"}
```

An optimality stamp follows a move of at most 1e-6: `proven_optimum` becomes the new cost and a `note` records that
the proof was obtained under the previous contract (its `dual_bound` is the prover's value in that arithmetic) and
that re-certification is pending. A larger move on a stamped BKS is refused (`stamp-conflict`). The website's
publication history lists re-priced BKS in their own bucket, not as improvements.
