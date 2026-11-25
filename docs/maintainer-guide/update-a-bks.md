# Update or submit a BKS

A best-known solution is a validated solution stored next to its instance as `<base>.bks.<ObjectiveFunction>.json`. In v0.13 the store evaluates both the candidate and the incumbent's routes under the same exact profile. A strict improvement replaces the incumbent, and a tie keeps it (`BKSUpdateResult.tie`). The stored `cost` displays the checker's exact rational cost as a binary64 value, or null on display overflow. The store preserves a solver's reported cost separately when supplied.

The store writes routes in lexicographic order. A permutation of the route list has the same objective value. Reversing stops within a route can change its cost or feasibility.

Records of earlier library versions are re-priced with `mamut-routing-lib` 0.12.0. [Historical TD repricing](../benchmarks/formats/solutions.md#historical-td-repricing)

## Static families (CVRP, VRPTW)

From the CLI, solve and let the library decide (`--save-bks` is opt-in and needs `--authors`):

```bash
uv run mamut-routing --benchmarks-dir benchmarks solve \
    --problem-type CVRP --benchmark-name Mamut2026 --instance-name mamut-lyon-n1000-k91-poi \
    --time-limit-s 600 --seed 7 --save-bks --authors "Your Name (handle)"
```

`--solver` picks any registered solver (`mamut-routing solvers list`), including external executables such as
LKH-3 or FILO2 declared in the solvers config. A solution file found elsewhere is checked and proposed with:

```bash
uv run mamut-routing check   path/to/instance.vrp.json found.sol
uv run mamut-routing bks submit path/to/instance.vrp.json found.sol --authors "Your Name (handle)" \
    --method "LKH-3" --solver-version 3.0.13 --seed 1 --time-limit-s 600 [--dry-run]
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

For a slim collection instance (Poryos2026, Mamut2026), `hydrate_collection_instance` loads the required sidecars. Then `create_bks_from_solution` validates the routes, computes the cost and builds the `BenchmarkBKS`. The call `save_bks_if_improved(instance, candidate_bks=bks, instance_path=instance_path)` compares it with the incumbent.

!!! warning "One writer per instance"
    The store is an unlocked read/compare/write. Two processes storing candidates for the same instance at the same
    time can end with the worse one on disk. Serialize the stores (see [Run a BKS campaign](bks-campaigns.md)).

`create_bks_from_solution` raises on an invalid solution, requires non-empty `authors` and fills `validated_cost`, `validated_num_routes` and `date`. With PyVRP, `solve_and_update_bks` in `mamut_routing_lib.solvers.pyvrp` solves the instance and submits the candidate in one call.

## Time-dependent families (TDVRP, TDVRPTW)

For TD instances, `save_td_solution_as_bks_if_improved` evaluates the routes under `td-binary64-exact-v1`.

```python
from mamut_routing_lib.td.bks import save_td_solution_as_bks_if_improved, annotate_td_bks_optimality
from mamut_routing_lib.enums import ObjectiveFunction

result = save_td_solution_as_bks_if_improved(instance_path, candidate, authors="...",
                                             objective_function=ObjectiveFunction.DURATION)
```

Each objective has its own store file (`.bks.Duration.json`, `.bks.FleetCostDuration.json`). KAYROS solves the
Duration objective through the same registry: `mamut-routing solve --solver kayros ... --save-bks --authors ...` and
`mamut-tools solve --solver kayros --save-bks --authors ...` re-check its routes with the TD checker and store them
through the TD store; `mamut-routing bks submit` does the same for a TD solution file found elsewhere.

## Recording a solver's optimality claim

For a TD result evaluated under the exact profile, identify the solver and the profile under which it reported optimality.

```python
annotate_td_bks_optimality(
    instance_path,
    {
        "status": "solver-reported-optimal",
        "solver": solver_name,
        "target_profile": "td-binary64-exact-v1",
    },
    ObjectiveFunction.DURATION,
)
```

The store re-evaluates the routes and verifies their stored exact result before recording the claim. The claim's `target_profile` must be `td-binary64-exact-v1`, and the legacy `proven: true` stamp is refused.

## After the file changed

1. **Route geometry.** The website draws BKS routes on the road network from a cache keyed by the BKS sha256. A
   replaced BKS of a road-network family (Poryos2026, Mamut2026 `shortest`/`fastest`) needs its geometry rebuilt:
   ```bash
   uv run mamut-routing-publish site materialize-route-geometry --jobs 1
   ```
   Do it locally, not on the site VM (a large city graph can exceed 15 GiB); the deploy reuses the cache by content.
2. **Changelog** of the family (at the root of its repository), with the source of the improvement.
3. **Publish.** The history ledger counts the BKS as `improved`; regressions are impossible by construction but a
   removed file shows up as `removed`.

## Contributions from outside

Point contributors to the FAQ's contribution section: a pull request on the family repository (or an issue with the solution file) is enough. Run the checker on their file yourself before merging; never trust a reported cost.
