# 3. Load an instance and check a solution

Sintef2008 ranks solutions by fleet size first, then by total arc cost. This example checks a stored Best-Known Solution (BKS) against the family's static profile, `binary64-exact-v1`. Initialise the family checkout as described in the [installation guide](install.md).

```python
from pathlib import Path

from mamut_routing_lib import check_solution, discover_benchmark_instances, load_bks
from mamut_routing_lib.artifacts import get_bks_path_for_instance, hydrate_collection_instance
from mamut_routing_lib.enums import ObjectiveFunction, ProblemType

items = discover_benchmark_instances(
    Path("benchmarks"),
    problem_types=[ProblemType.VRPTW],
    benchmark_names=["Sintef2008"],
)
item = items[0]
instance = hydrate_collection_instance(item.load(), item.instance_path)
bks_path = get_bks_path_for_instance(item.instance_path, ObjectiveFunction.HIERARCHICAL_VEHICLE_COST)
bks = load_bks(bks_path)

report = check_solution(instance, bks, instance_path=item.instance_path)
print(report.status.value, report.num_routes)
```

The checker validates the routes and evaluates the binary64 arc costs and time bounds with exact rational arithmetic. A static vehicle with time windows starts at the opening of the depot. In a submitted `BenchmarkSolution`, leave `cost` unset to have the routes priced. A supplied `cost` asserts the binary64 display value.

For either a static or time-dependent instance, `evaluate_exact` returns the rational cost. Pass the stored objective to include any fixed fleet cost. The default backend uses C++. To repeat the calculation with the Python Fraction reference, select `backend="python"`.

```python
from mamut_routing_lib import evaluate_exact

evaluation = evaluate_exact(item.instance_path, bks.routes, objective_function=bks.objective_function)
print(evaluation.profile, evaluation.cost, evaluation.display_cost)
```

For a time-dependent BKS, use its descriptor and routes in the same call. The profile is `td-binary64-exact-v1`. Each entry in `evaluation.route_evaluations` gives the minimum duration and the earliest depot departure attaining it. The public `mamut_routing_lib.td.check_td_solution` also checks this profile. A solver claim of optimality on a TD BKS must target this profile. [Solutions, BKS and optimality](../benchmarks/formats/solutions.md)

Next, [solve with PyVRP and propose a BKS](solve-and-bks.md).
