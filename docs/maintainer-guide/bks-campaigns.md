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

## With `mamut-tools bks-campaign`

The tools run the whole pattern from a TOML spec (the format is documented in
`mamut_routing_tools.bks_campaign.spec`):

```toml
[campaign]
name = "mamut2026-bks-4"
out = "runs/mamut2026-bks-4"          # relative to the spec; refused inside a benchmark tree
authors = "Your Name (handle)"        # credited in every BKS the harvest writes

[select]
benchmarks_dir = "../benchmarks"
problem_types = ["CVRP"]
families = ["Mamut2026"]
metrics = ["euclidean"]
min_n = 700

[budget]                              # T(n) = clamp(per_customer_s * n, min_s, max_s) * time_scale
per_customer_s = 21.6
min_s = 7200
max_s = 86400

[[runs]]
solver = "filo2"                      # external solvers come from the solvers config
seeds = "1-5"

[[runs]]
solver = "lkh3"
seeds = "1-5"

[[runs]]
solver = "pyvrp"
kind = "pyvrp-polish"
seeds = "3000-3003"
budget_factor = 1.5
warm_start = "best"                   # from the best archived run or the stored BKS

[resources]
workers = 90
memory_gb = "auto"                    # 80 % of MemAvailable
```

```bash
mamut-tools bks-campaign plan     campaign.toml --only toronto    # dry run: runs, core-hours, memory, refusals
mamut-tools bks-campaign baseline campaign.toml                   # freeze the stored BKS (refuses to overwrite)
mamut-tools bks-campaign run      campaign.toml                   # resumable; Ctrl-C once = drain, twice = abort
mamut-tools bks-campaign harvest  campaign.toml --dry-run         # then without --dry-run: the only BKS writer
mamut-tools bks-campaign report   campaign.toml                   # ledger.csv, cross-solver.csv
```

- **Runs** are checked by the reference checker and archived as `runs/<key>.json` (schema version 1: instance and
  its sha256, kind, solver, version, seed, budget, status, the checker's verdict and cost, routes, trajectory, the
  solver's own cost and scale, warm start, provenance, host and CPU), winner or not. The key
  `<instance_id>__<objective>__<kind>__seed<S>__t<T>` includes the budget; a run is done when its record exists, so
  a killed run is simply redone. Solver logs and solution files stay in `raw/<key>/`.
- **Workers never write BKS.** One task per spawned worker, admitted while the memory estimates fit the budget;
  external solvers run in their own process group and are killed with their children on abort.
- **Harvest** takes each instance's best valid run, skips runs whose instance file changed since and runs below
  the published fleet lower bound, and offers the rest (those that beat the baseline, or all with `--offer-all`) to
  the BKS store, one process per instance, with the spec's authors and the run's provenance. The store keeps the
  incumbent on a tie.
- Launch long campaigns as a user unit on shared machines
  (`systemd-run --user --unit=<name> --collect mamut-tools bks-campaign run campaign.toml`): a resumable driver only
  loses the runs in flight when the session goes.

## Driver pattern (library)

For a custom driver, call the library, not the CLI. Workers **solve and return**; one coordinator **stores**: the
BKS store is an unlocked read/compare/write, so two processes writing the same file can let a worse candidate win
the race (measured, not hypothetical). Consume every future so worker exceptions surface.

```python
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from mamut_routing_lib import discover_benchmark_instances, run_solver, submit_bks

BENCHMARKS = Path("benchmarks").resolve()     # the library never falls back to the working directory

def run(item, solver, seed, time_limit_s):
    """Worker: solve, check and return; never writes a BKS."""
    return item, run_solver(solver, item.instance_path, time_limit_s=time_limit_s, seed=seed)

items = discover_benchmark_instances(BENCHMARKS, problem_types=["CVRP"], benchmark_names=["Mamut2026"])
with ProcessPoolExecutor(max_workers=10) as pool:                       # one core per run
    futures = [pool.submit(run, item, solver, seed, 300)
               for item in items for solver in ("pyvrp", "lkh3") for seed in (1, 2, 3)]
    for future in as_completed(futures):
        item, solved = future.result()                                  # re-raises a worker's exception
        archive_run(item, solved.to_json())                             # every run, winner or not
        if not solved.valid:
            continue
        update = submit_bks(                                            # coordinator: the only writer
            item.instance_path, solved.result.routes, authors="...",
            metadata=solved.bks_metadata(campaign="2026-11-bks-4"),     # solver, version, seed, budget, machine
        )
        print(item.instance_id, update.action, update.candidate_cost)
```

`submit_bks` (or `save_solution_as_bks_if_improved`) hydrates slim collection instances (Mamut2026, Poryos2026)
from their sidecars before checking, and dispatches TD instances to the TD store. Make a custom driver resumable
(skip runs whose archive exists) and keep a ledger with one row per run. Memory per PyVRP worker is roughly 100 MB
at n≈500 and 1.6 GB at n=4000.

## After the campaign

1. Rebuild route geometry for every replaced road-network BKS (locally).
2. Update the family changelog and README (the README of a generated collection states how its BKS were produced).
3. Record the achieved gaps, seed spread and the campaign ledger location in the family README and changelog.
4. Publish with a `--history-summary` naming the campaign; the ledger records every `improved` BKS.
