# 4. Solve with PyVRP and propose a BKS

The lib wraps [PyVRP](https://github.com/PyVRP/PyVRP) (`pyvrp` extra). A BKS file is only ever created or replaced
by a strictly better, freshly validated solution, so running a solver against the tree is safe.

```bash
uv run mamut-routing --benchmarks-dir benchmarks solve \
    --instance-id vrptw-sintef2008-n25-C101 --objective hierarchicalvehiclecost \
    --time-limit-s 10 --seed 42 --save-bks
```

The command prints the solver result and the store action: `created`, `replaced` or `kept_existing` (with a 10 s
budget the published BKS is kept; a solution of exactly equal cost is kept out as a tie, even if its float sum
differs by an ulp). A failing instance becomes an `error` row and the batch goes on; scanned time-dependent
instances are skipped (`solve` is static-only). The exit status is 0 when every solved instance is feasible, 1 if
any row is infeasible or an error, 2 on a usage error. Two details that matter:

- **Say which objective.** Sintef2008 stores its BKS under `HierarchicalVehicleCost`; without `--objective` the
  solver runs `MonoCost` (with a warning) and *creates* a second file, `C101.bks.MonoCost.json`, instead of comparing
  with the published one. CVRP families are always `MonoCost`.
- **`--instance-name C101` matches every size** (n=25, 50, 100 in Sintef2008); `--instance-id` selects one instance,
  `--jobs` solves several side by side.

From Python, with any solver:

```python
from mamut_routing_lib import BenchmarkSolution, save_solution_as_bks_if_improved
from mamut_routing_lib.enums import ObjectiveFunction

result = save_solution_as_bks_if_improved(
    item.instance_path, ObjectiveFunction.HIERARCHICAL_VEHICLE_COST,
    BenchmarkSolution(instance_name=item.instance_name, routes=my_routes),
    authors="Your Name (handle)",
    metadata={"method": "my-solver", "seed": 42, "time_limit_s": 600},
)
print(result.action, result.path, result.candidate_cost)
```

The helper loads the instance (hydrating collection instances), validates the routes with the checker, and writes
`<base>.bks.<Objective>.json` next to the instance only if it beats the stored one. The write is a plain
read/compare/write: keep one writer per instance (see [Run a BKS campaign](../maintainer-guide/bks-campaigns.md)).

To contribute an improvement, send the solution file or open a pull request on the family's repository; the
maintainers re-run the checker. Next: [Export to CVRPLIB `.vrp`](export-vrp.md).
