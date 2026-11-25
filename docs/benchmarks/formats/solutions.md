# Solutions, BKS and optimality

## Solution (`BenchmarkSolution`)

```json
{"instance_name": "...", "routes": [[3, 1, 2], [5, 4]], "cost": null, "metadata": {}}
```

Each route lists customer indices from 1 to `num_customers`, with the depot implicit at both ends. For a `BenchmarkSolution` passed to the v0.13 exact store, `cost` is optional. A non-null value asserts that the exact rational objective rounds to this binary64 value (round to nearest, ties to even). Leave `cost` null to submit just the routes. `metadata` carries additional information.

## BKS (`BenchmarkBKS`)

A `BenchmarkBKS` adds `objective_function` and is stored next to the instance as `<base>.bks.<ObjectiveFunction>.json`, one file per objective. In v0.13, `save_bks_if_improved` and `save_td_solution_as_bks_if_improved` apply the following rules.

- The candidate must be a feasible solution of the named instance. The store writes its routes in lexicographic order, with customer order preserved within each route.
- The store evaluates static routes under `binary64-exact-v1` and time-dependent routes under `td-binary64-exact-v1`. It stores the rational cost in `metadata.standard.authoritative_cost` for a certified edition, or `metadata.exact_evaluation.authoritative_cost` before certification, and its binary64 display value in `cost` (null on display overflow). For TD routes it also records each exact minimum duration and the earliest departure attaining it.
- `metadata.authors` is required. The store fills `validated_cost`, `validated_num_routes` and `date`.
- The store re-evaluates the incumbent's routes before comparing them with the candidate. It compares exact costs, with route count taking precedence for `HierarchicalVehicleCost`. A strict improvement replaces the incumbent. A tie keeps it and returns `BKSUpdateResult(action="kept_existing", tie=True)`.

In v0.12, the static store instead summed the shortest round-trip decimal representations of the materialized arc costs.

A BKS created from a solver run can carry the solver and method, version, seed, time budget, wall time, campaign and CPU model. External runs can also identify the input file and executable by SHA-256.

### The solver's reported cost

The optional `metadata.solver_report` names the reported objective and preserves its numerical value. An `integer` or `decimal-text` value is the original token as a string. A `binary64` value from an API is a finite JSON number. The optional `family_units_per_solver_unit` is a positive reduced fraction. Multiplying by this fraction converts one solver unit to the instance's cost unit.

```json
{
  "solver_report": {
    "objective": "total-arc-cost",
    "encoding": "integer",
    "value": "65617528",
    "family_units_per_solver_unit": {"numerator": "1", "denominator": "100"}
  },
  "solver_cost": 656175.28
}
```

This LKH-3 report gives the cost of its routes on the exported Toronto matrix. The family checker priced the same routes at `46174228443702207525/70368744177664`. A certified BKS compares the rational in `metadata.standard.authoritative_cost`. With no verified manifest yet, the evaluation is recorded under `metadata.exact_evaluation`.

For a comparable `total-arc-cost` or `total-route-duration`, calculate `solver_cost` by multiplying the reported value by the unit exactly and rounding once to the nearest binary64, ties to even. For a composite objective such as PyVRP's `vehicle-penalized-cost`, the optional `routing_cost_component` supplies the separately reported comparable quantity with its own `objective`, `encoding` and `value`, in the same unit. Omit `solver_cost` if that conversion is unknown or its binary64 projection overflows. Legacy records can lack the original value or unit.

In an external run's provenance, `reported_cost_matches_exported_model` answers whether the solver's reported number equals the sum of the integer matrix weights on its returned routes, including both depot legs. Either result can accompany a route set that the family checker verifies. The adapter omits the diagnostic when it cannot perform the comparison.

## Solution files from other solvers

`mamut-routing check`, `mamut-routing bks submit` and the tools workbench's import read:

| Format | Shape |
|---|---|
| CVRPLIB `.sol` | `Route #1: 3 1 2` lines (`Route 1:` also accepted) and an optional `Cost <value>` line; costs in exponent form (`1.2345E7`, `1.23457e+06`) are read |
| JSON | `{"routes": [[...]], "cost": ...}` (a solution or BKS file) or a bare array of routes |
| LKH-3 `MTSP_SOLUTION_FILE` | a `<name>, Cost: <penalty>_<cost>` header and one `1 a b c 1 (#3)  Cost: x` line per vehicle; node 1 is the depot, a non-zero penalty is refused |

When submitting a standalone CVRPLIB or LKH solution, the CLI retains the printed cost token. A generic CVRPLIB `Cost` line leaves the objective `unspecified` until the submitter supplies its meaning. A standalone LKH solution identifies total arc cost. Both formats can omit the export unit, in which case the BKS retains the report and omits its family-unit display. An ordinary solution JSON can provide its report directly in `metadata.solver_report`.

Stop ids are mapped onto the library's (depot 0, customers 1..n): customers numbered 1..n with an optional 0 as a
depot marker (CVRPLIB), or 0..n-1 when the file covers exactly those ids (`--ids one-based|zero-based` forces a
reading; `check` says when it read a file as 0-based). Under 1..n a 0 inside a route is a return to the depot: the
route is split there into two trips, as written. A file whose ids fit neither, visits a customer twice or misses one
is refused, never reinterpreted. An objective that does not apply to the instance (`Duration` on CVRP, `MonoCost`
on a TD instance) is a usage error. The
declared cost is never trusted: the checker prices the routes, and a disagreeing declaration is reported (it usually
means another metric variant, a rounded matrix, or a solver's scaled integer units, which `check` names when the
ratio is a power of ten).

`mamut-routing solve --output-dir DIR` writes solutions in the JSON form above, with `cost` left to the checker and
`metadata` holding `instance_id`, `instance_path`, `objective_function`, `validation`, `checker_cost`, `status` and
`bks_metadata` (the provenance a BKS stored from the run would carry). `bks submit` copies that provenance into the
BKS it stores; its own flags (`--method`, `--seed`, `--time-limit-s`, `--solver-version`) override it. The JSON
printed by `mamut-tools solve` is also a valid solution file.

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

## Optimality claims

For a v0.13 exact result, `metadata.optimality` records the solver's claim with `status: "solver-reported-optimal"`, the solver's name in `solver` and the profile on which the solver reported optimality in `target_profile`. The store evaluates the submitted routes. Establishing global optimality requires the solver's proof.

The claim's `target_profile` must equal the profile under which the stored routes were evaluated, and the store refuses any other target. Optional `campaign`, `reported_primal`, `reported_dual` and `evidence` fields describe the run, the solver's own bounds and a hash-pinned evidence file. The website displays a green label for a BKS with an attached solver claim. A BKS without `metadata.optimality` has no attached claim.

Library versions before 0.13 wrote a `proven: true` stamp under the same key. The published store holds no such stamp. The library neither reads nor writes one. Loading a file that carries it raises `LegacyOptimalityClaimError`. Read such historical files with `mamut-routing-lib` 0.12.0.

## Historical TD repricing

The v0.12 `td-fold/2` migration used `mamut-routing bks reprice-td <tree> --write` to replay unmarked TD routes. Version 0.13 removes this command. Records of earlier library versions are re-priced with `mamut-routing-lib` 0.12.0. For a legacy cost that moved, the migration updated `cost`, `metadata.validated_cost`, `metadata.route_durations` and `metadata.route_departure_times`, and added this record. [Time-dependent instances](time-dependent.md#historical-td-fold-in-v012)

```json
"repriced": {"previous_cost": 8292.0, "checker": "mamut-routing-lib td checker, contract td-fold/2 (lib >= 0.12.0)",
             "contract": "td-fold/2", "date": "2026-09-24"}
```
