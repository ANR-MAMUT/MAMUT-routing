# 4. Solve and propose a BKS

The lib runs solvers by name, behind one protocol, and prices every solution with the reference checker before it
reports or stores it. PyVRP is built in (`pyvrp` extra); KAYROS solves the time-dependent families (`pip install
kayros`); literature solvers -- FILO2, HGS-CVRP, AILS-II, LKH-3, or your own -- run as external executables once you
point the solvers config at them. A BKS file is only ever created or replaced by a strictly better, freshly validated
solution, so running a solver against the tree is safe.

```bash
uv run mamut-routing solvers list      # what is available here, and how to enable the rest
```

## Solve

```bash
uv run mamut-routing --benchmarks-dir benchmarks solve \
    --instance-id vrptw-sintef2008-n25-C101 --objective hierarchicalvehiclecost \
    --time-limit-s 10 --seed 42
```

Nothing is written unless asked. The COST column is the checker's cost (not the solver's own objective, which PyVRP
computes in milli-units on collection instances). A solution the checker rejects is an `infeasible` row with the
checker's reason; a failing instance becomes an `error` row and the batch goes on. Instances the solver cannot take
are skipped in scans and are error rows for explicit paths: time-dependent instances for static solvers, road-network
metrics for solvers that compute distances from coordinates, and collection instances whose pinned distances
sidecar is missing. Ctrl-C stops every running solve. The exit status is 0 when every solved instance is feasible
and checker-valid, 1 otherwise, 2 on a usage error.

To store improvements, add `--save-bks` and say who is credited (`--authors`, or `$MAMUT_ROUTING_BKS_AUTHORS`):

```bash
uv run mamut-routing --benchmarks-dir benchmarks solve \
    --instance-id vrptw-sintef2008-n25-C101 --objective hierarchicalvehiclecost \
    --time-limit-s 10 --save-bks --authors "Your Name (handle)"
```

The BKS column then shows the store's action: `created`, `replaced` or `kept_existing` (with a 10 s budget the
published BKS is kept; `kept_existing (tie)` when the cost is exactly equal, even if the float sum differs by an ulp).
The stored BKS carries the solve's provenance: solver, version, seed, budget, wall time and the machine's CPU model.
Two details that matter:

- **Say which objective.** Sintef2008 and Ortec2022 store their BKS under `HierarchicalVehicleCost`; without
  `--objective` the solve uses `MonoCost` (with a warning) and `--save-bks` *creates* a second file,
  `C101.bks.MonoCost.json`, instead of comparing with the published one. CVRP families are always `MonoCost`,
  time-dependent ones `Duration`.
- **`--instance-name C101` matches every size** (n=25, 50, 100 in Sintef2008); `--instance-id` selects one instance,
  `--jobs` solves several side by side.

## External solvers

Executables are declared in `~/.config/mamut-routing/solvers.toml` (or the file named by
`$MAMUT_ROUTING_SOLVERS_CONFIG` or `--solvers-config`; never one in the working directory):

```toml
schema_version = 1

[solvers.lkh3]
executable = "/opt/LKH-3/LKH"

[solvers.filo2]
executable = "/opt/filo2/build/filo2"   # built with -DENABLE_TIMELIMIT=ON
```

```bash
uv run mamut-routing solve path/to/inst.vrp.json --solver lkh3 --time-limit-s 60 --keep-artifacts runs/
```

| Solver | Takes | Reads / writes |
|---|---|---|
| `lkh3` | CVRP and VRPTW, any metric (asymmetric matrices as `ACVRP`) | explicit integer matrix + parameter file / MTSP solution file |
| `filo2`, `hgs-cvrp`, `ails2` | CVRP on euclidean variants (they compute distances from coordinates) | X-format `.vrp` / CVRPLIB `.sol` |

Each run writes the solver's input into a scratch directory with the costs scaled to integers: exactly when the
data allow (x1000 for the 3-decimal Mamut2026 / Poryos2026 matrices, so the solver's cost unscales exactly and is
cross-checked), approximately otherwise -- conservatively for time windows, so a schedule the solver finds feasible
is feasible on the published data. Coordinate solvers get coordinates in a unit that fits their limits (FILO2
millimetres, HGS-CVRP metres, or decametres for cities wider than ~90 km). The solver runs in its own process group
with a hard timeout and is killed with its children on cancellation. Any other solver that reads and writes
CVRPLIB-style files can be added to the config; see the [solution formats](../benchmarks/formats/solutions.md) page.

## Solutions found elsewhere

```bash
uv run mamut-routing check path/to/inst.vrp.json found.sol          # exit 0 valid, 1 invalid, 2 unreadable
uv run mamut-routing bks submit path/to/inst.vrp.json found.sol \
    --authors "Your Name (handle)" --method "LKH-3" --seed 1 --dry-run
```

`check` and `bks submit` read CVRPLIB `.sol` files, JSON routes and LKH-3 MTSP solution files, static and
time-dependent instances alike. The objective defaults to the one the family publishes. `--dry-run` reports
`would_create`, `would_replace` or `would_keep` without writing.

## From Python, with any solver

```python
from mamut_routing_lib import run_solver, submit_bks

solved = run_solver("pyvrp", item.instance_path, time_limit_s=60, seed=42)
if solved.valid:
    update = submit_bks(item.instance_path, solved.result.routes,
                        authors="Your Name (handle)", metadata=solved.bks_metadata(campaign="my-campaign"))
    print(update.action, update.path, update.candidate_cost)
```

Routes found by your own code go through `submit_bks(instance_path, routes, authors=..., metadata=...)` directly
(or `save_solution_as_bks_if_improved`, as before). The helpers load the instance (hydrating collection instances),
validate the routes with the checker, and write `<base>.bks.<Objective>.json` next to the instance only if it beats
the stored one. The write is a plain read/compare/write: keep one writer per instance (see
[Run a BKS campaign](../maintainer-guide/bks-campaigns.md)).

To contribute an improvement, send the solution file or open a pull request on the family's repository; the
maintainers re-run the checker. Next: [Export to CVRPLIB `.vrp`](export-vrp.md).
