# Update or submit a BKS

A best-known solution is a solution file the checker has validated, stored next to its instance as
`<base>.bks.<ObjectiveFunction>.json`. Two rules make BKS maintenance safe:

- **the stored cost is the checker's cost**, whatever the solver reported;
- **a BKS is replaced only by a strictly better, freshly validated solution**; the stored file is itself
  re-validated before comparison, so a corrupted BKS is caught rather than silently kept.

## Static families (CVRP, VRPTW)

From the CLI, solve and let the library decide:

```bash
uv run mamut-routing --benchmarks-dir benchmarks solve \
    --problem-type CVRP --benchmark-name Mamut2026 --instance-name mamut-lyon-n1000-k91-poi \
    --time-limit-s 600 --seed 7 --save-bks
```

From Python, with your own solution (any solver):

```python
from mamut_routing_lib import BenchmarkSolution, save_solution_as_bks_if_improved
from mamut_routing_lib.enums import ObjectiveFunction

candidate = BenchmarkSolution(instance_name="mamut-lyon-n1000-k91-poi", routes=routes)   # cost: the checker's
result = save_solution_as_bks_if_improved(
    instance_path, ObjectiveFunction.MONO_COST, candidate,
    authors="Your Name (handle)",
    metadata={"method": "my-solver-v2", "seed": 7, "time_limit_s": 600, "solver_version": "2.1", "machine": "..."},
)
print(result.action, result.path, result.candidate_cost)           # created | replaced | kept_existing
```

Under the hood: the instance is loaded and, for slim collection instances (Poryos2026, Mamut2026), hydrated from
its sidecars (`hydrate_collection_instance`); `create_bks_from_solution` builds the `BenchmarkBKS` (validation,
checker cost, metadata); `save_bks_if_improved(instance, bks, instance_path)` does the compare-and-replace.

!!! warning "One writer per instance"
    The store is an unlocked read/compare/write. Two processes storing candidates for the same instance at the same
    time can end with the worse one on disk. Serialize the stores (see [Run a BKS campaign](bks-campaigns.md)).
`create_bks_from_solution` raises on an invalid solution, requires a non-empty `authors`, and fills
`validated_cost`, `validated_num_routes` and `date` in the metadata. `is_better_solution` implements the objective's
order (HierarchicalVehicleCost compares route count first). With PyVRP, `solve_and_update_bks` in
`mamut_routing_lib.solvers.pyvrp` does the solve and the store in one call.

## Time-dependent families (TDVRP, TDVRPTW)

The static checker refuses TD instances; use the TD store, which prices with `check_td_solution` (exact doubles,
no epsilon):

```python
from mamut_routing_lib.td.bks import save_td_solution_as_bks_if_improved, annotate_td_bks_optimality
from mamut_routing_lib.enums import ObjectiveFunction

result = save_td_solution_as_bks_if_improved(instance_path, candidate, authors="...",
                                             objective_function=ObjectiveFunction.DURATION)
```

Each objective has its own store file (`.bks.Duration.json`, `.bks.FleetCostDuration.json`). With the tools,
`mamut-tools solve --solver kayros` solves the Duration objective; its `--update-bks` is wired for PyVRP only, so
TD results go through the library call above.

## Optimality proofs

A proven optimum is metadata, validated like everything else (`OptimalityMetadata`: `proven: true`, `prover`,
`certificate`, `date`, optional `proven_optimum`, `dual_bound`, `wall_time_s`, `time_limit_s`, `checker`,
`campaign`, `note`). For TD stores:

```python
annotate_td_bks_optimality(instance_path, {"proven": True, "prover": "kayros 1.1.2", "certificate": "...",
                                            "date": "2026-09-14"}, ObjectiveFunction.DURATION)
```

The stored BKS is re-validated before the stamp is written, and a declared `proven_optimum` must equal the stored
cost (a dust-level difference needs an explanatory `note`).

## After the file changed

1. **Route geometry.** The website draws BKS routes on the road network from a cache keyed by the BKS sha256. A
   replaced BKS of a road-network family (Poryos2026, Mamut2026 `shortest`/`fastest`) needs its geometry rebuilt:
   ```bash
   uv run mamut-routing-publish site materialize-route-geometry --jobs 1
   ```
   Do it locally, not on the site VM (a large city graph can exceed 15 GiB); the deploy reuses the cache by content.
2. **Changelog** of the family (satellite or in-repo), with the source of the improvement.
3. **Publish.** The history ledger counts the BKS as `improved`; regressions are impossible by construction but a
   removed file shows up as `removed`.

## Contributions from outside

Point contributors to the FAQ's contribution section: a pull request on the satellite (or an issue with the solution
file) is enough. Run the checker on their file yourself before merging; never trust a reported cost.
