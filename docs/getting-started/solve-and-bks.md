# 4. Solve with PyVRP and propose a BKS

The lib wraps [PyVRP](https://github.com/PyVRP/PyVRP) (`pyvrp` extra). A BKS file is only ever created or replaced
by a strictly better, freshly validated solution, so running a solver against the tree is safe.

```bash
uv run mamut-routing --benchmarks-dir benchmarks solve \
    --problem-type VRPTW --benchmark-name Sintef2008 --instance-name C101 \
    --time-limit-s 10 --seed 42 --save-bks
```

The command prints the solver result and the store action: `created`, `replaced` or `kept_existing` (with a 10 s
budget on a 25-customer instance the published BKS is usually kept). `--jobs` solves several instances side by
side; `--objective` picks the objective when a family has several.

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
