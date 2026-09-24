# 3. Load an instance and check a solution

The library is the contract: pydantic models for instances, solutions and BKS, and the checkers that define what a
valid solution costs. This tutorial uses Sintef2008, an in-repo VRPTW family whose BKS are stored under the
`HierarchicalVehicleCost` objective.

```python
from pathlib import Path

from mamut_routing_lib import check_solution, discover_benchmark_instances, load_bks
from mamut_routing_lib.artifacts import get_bks_path_for_instance, hydrate_collection_instance
from mamut_routing_lib.enums import ObjectiveFunction, ProblemType

items = discover_benchmark_instances(
    Path("benchmarks"),                     # explicit: the library never falls back to the working directory
    problem_types=[ProblemType.VRPTW], benchmark_names=["Sintef2008"],
)
item = items[0]                             # problem type, family, size, instance_path, ...
print(item.instance_id, item.num_customers)

instance = hydrate_collection_instance(item.load(), item.instance_path)   # no-op here; needed for Poryos2026/Mamut2026
bks = load_bks(get_bks_path_for_instance(item.instance_path, ObjectiveFunction.HIERARCHICAL_VEHICLE_COST))
report = check_solution(instance, bks)
print(report.status.value, report.routing_cost, report.num_routes)       # valid <cost> <routes>
```

What happened:

- `discover_benchmark_instances` walks the tree and returns one record per `.vrp.json` (both layouts); the filters
  are exact matches.
- `item.load()` picks the model from the file: embedded CVRP/VRPTW, slim collection instance, or time-dependent.
- `hydrate_collection_instance` turns a slim collection instance (arc costs by sidecar or euclidean rule) into an
  embedded one; embedded instances pass through.
- `check_solution` validates (indices, single service, capacity, time windows, fleet) and prices the routes. Its
  cost is the cost stored in every BKS.

Your own solution is a `BenchmarkSolution(instance_name=..., routes=[[...], ...])`; leave `cost` unset to have it
priced, or set it to assert the exact value.

Time-dependent instances (TDVRP, TDVRPTW) use the exact checker in `mamut_routing_lib.td`:

```python
from mamut_routing_lib.td import load_td_instance, check_td_solution
loaded = load_td_instance(path_to_td_instance)          # materializes the arrival-time functions, checks their pin
result = check_td_solution(loaded, solution)            # Duration objective by default
```

TD costs are defined by the checker contract `td-fold/2` (mamut-routing-lib ≥ 0.12.0); published TD BKS were
re-priced under it on 2026-09-24, so an older lib reports some of them as `objective_value_mismatch`. Upgrade the
lib rather than comparing with a tolerance.

Next: [Solve with PyVRP and propose a BKS](solve-and-bks.md).
