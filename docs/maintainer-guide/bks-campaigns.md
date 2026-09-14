# Run a BKS campaign

A campaign is many solver runs whose winners become BKS and whose losers are data. This page is the pattern; the
maintainers' campaign plans are internal working notes.

## Design checklist

- **Budget scales with n.** A fixed time limit converges at n=100 and not at n=4000; either scale it or state that
  the BKS of the largest tier are reference solutions, not near-optima.
- **Several seeds.** One seed cannot separate solver variance from the effect you measure.
- **Provenance in the BKS metadata**: method label, seed, budget, solver version, machine. PyVRP stops on wall
  clock, so a `(seed, time_limit)` pair is not replayable; the solution file is the reproducible artifact.
- **Archive every run**, winner or not, as JSON (instance id, seed, budget, cost, routes, wall time, host).
- **Materialize the pins first.** Distance sidecars above the collection's size threshold are not committed; run
  `mamut-tools generate materialize-distances` on the metric directories and check
  `mamut-routing list --benchmark-name <Family>` resolves everything.
- **Not on the site VM.** It serves the site; solving there starves the server and its memory is small.

## Driver pattern

Call the library, not the CLI, so extra metadata reaches the BKS. Workers **solve and return**; one
coordinator **stores**: the BKS store is an unlocked read/compare/write, so two processes writing the same file can
let a worse candidate win the race (measured, not hypothetical). Consume every future so worker exceptions surface.

```python
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from mamut_routing_lib import BenchmarkSolution, discover_benchmark_instances, save_solution_as_bks_if_improved
from mamut_routing_lib.enums import ObjectiveFunction
from mamut_routing_lib.solvers.pyvrp import solve_instance

BENCHMARKS = Path("benchmarks").resolve()     # the library never falls back to the working directory

def run(item, seed, time_limit_s):
    """Worker: solve and return; never writes a BKS."""
    result = solve_instance(item.load(), time_limit_s=time_limit_s, seed=seed, instance_path=item.instance_path)
    return item, seed, result

items = discover_benchmark_instances(BENCHMARKS, problem_types=["CVRP"], benchmark_names=["Mamut2026"])
with ProcessPoolExecutor(max_workers=10) as pool:                       # one core per PyVRP run
    futures = [pool.submit(run, item, seed, 300) for item in items for seed in (1, 2, 3)]
    for future in as_completed(futures):
        item, seed, result = future.result()                            # re-raises a worker's exception
        archive_run(item, seed, result)                                 # every run, winner or not
        if not result.solver_is_feasible:
            continue
        update = save_solution_as_bks_if_improved(                      # coordinator: the only writer
            item.instance_path, ObjectiveFunction.MONO_COST,
            BenchmarkSolution(instance_name=item.instance_name, routes=result.routes),
            authors="...", metadata={"method": "pyvrp-ils-v2", "seed": seed, "time_limit_s": 300,
                                     "solver_version": "0.13.4", "machine": "...", "campaign": "2026-09-bks-2"},
        )
        print(item.instance_id, seed, update.action, update.candidate_cost)
```

`save_solution_as_bks_if_improved` hydrates slim collection instances (Mamut2026, Poryos2026) from their sidecars
before checking (lib ≥ commit `74b8a54`); `solve_and_update_bks` does solve and store in one call but carries no
extra metadata and would run the store inside each worker, which is exactly the race to avoid.

Make the driver resumable (skip runs whose archive exists) and keep a ledger (`campaigns/<id>/ledger.csv`) with one
row per run. Memory per worker is roughly 100 MB at n≈500 and 1.6 GB at n=4000.

## After the campaign

1. Rebuild route geometry for every replaced road-network BKS (locally).
2. Update the family changelog and README (the README of a generated collection states how its BKS were produced).
3. Record the achieved gaps, seed spread and the campaign ledger location in the family README and changelog.
4. Publish with a `--history-summary` naming the campaign; the ledger records every `improved` BKS.
