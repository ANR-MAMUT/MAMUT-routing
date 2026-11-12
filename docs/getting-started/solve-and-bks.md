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
computes in milli-units on collection instances), and GAP its distance to the BKS stored before the solve (`no BKS`
when there is none; under `HierarchicalVehicleCost` a different route count shows as `+1 veh`). A solution the
checker rejects is an `infeasible` row with the checker's reason; a failing instance becomes an `error` row and the batch goes on. Instances the solver cannot take
are skipped in scans and are error rows for explicit paths: time-dependent instances for static solvers, road-network
metrics for solvers that compute distances from coordinates, and collection instances whose pinned distances
sidecar is missing. Ctrl-C stops every running solve (external solvers and KAYROS run in processes of their own and are
killed; a stopped KAYROS solve keeps its last incumbent). The exit status is 0 when every solved instance is feasible
and checker-valid, 1 otherwise, 2 on a usage error. `mamut-tools solve` takes the same flags (`--time-limit-s`,
`--save-bks`; `--time-limit` and `--update-bks` work in both).

To keep the routes, add `--output-dir DIR` (`-o`): each solution is written to
`DIR/<instance-id>.<solver>-seed<seed>.json` with the checker's verdict and the run's provenance. `check` reads these
files, and `bks submit` stores one later with its provenance (solver, version, seed, budget):

```bash
uv run mamut-routing solve path/to/inst.vrp.json --time-limit-s 60 -o runs/
uv run mamut-routing bks submit path/to/inst.vrp.json runs/<instance-id>.pyvrp-seed42.json --authors "Your Name (handle)"
```

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

- **Say which objective.** Sintef2008 stores its BKS under `HierarchicalVehicleCost`; without
  `--objective` the solve uses `MonoCost` (with a warning) and `--save-bks` *creates* a second file,
  `C101.bks.MonoCost.json`, instead of comparing with the published one. CVRP families are always `MonoCost`,
  time-dependent ones `Duration`.
- **`--instance-name C101` matches every size** (n=25, 50, 100 in Sintef2008); `--instance-id` selects one instance,
  `--jobs` solves several side by side.

## External solvers

Executables are declared in `~/.config/mamut-routing/solvers.toml` (or the file named by
`$MAMUT_ROUTING_SOLVERS_CONFIG` or `--solvers-config`; never one in the working directory).
`uv run mamut-routing solvers init` writes a commented starter there, one table per built-in solver with its build
notes; uncomment the ones you have built and set their paths:

```toml
schema_version = 1

[solvers.lkh3]
executable = "/opt/LKH-3/LKH"

[solvers.filo2]
executable = "/opt/filo2/build/filo2"   # built with -DENABLE_TIMELIMIT=ON

[solvers.hgs-cvrp]
executable = "/opt/HGS-CVRP/build/hgs"  # vidalt/HGS-CVRP + the lib's full-matrix reader patch
```

Relative paths are read from the config file's folder; a bare executable name is looked up on PATH. Unknown keys and
mistyped values (`fleet_limit = "false"`, quoted) are errors, with a suggestion for a near-miss key. An error in one
`[solvers.<name>]` table disables that solver only: `solvers list` shows it as unavailable with the error, and the
other solvers keep working. `extends` may name a table defined anywhere in the file.

HGS-CVRP's search handles asymmetric distances, but its upstream CVRPLIB reader only computes Euclidean distances
from coordinates. The lib ships a small reader patch (`git apply` it to HGS-CVRP 1a92795 and rebuild; `mamut-routing
solvers list` prints its installed path) that reads an explicit full matrix and keeps the coordinates for SWAP*.

```bash
uv run mamut-routing solve path/to/inst.vrp.json --solver lkh3 --time-limit-s 60 --keep-artifacts runs/
```

| Solver | Takes | Reads / writes |
|---|---|---|
| `lkh3` | CVRP and VRPTW, any metric (asymmetric matrices as `ACVRP`) | explicit integer matrix + parameter file / MTSP solution file |
| `hgs-cvrp` | CVRP, any metric (asymmetric included), with the lib's full-matrix reader patch applied to HGS-CVRP | decimal full matrix + coordinates (for SWAP*) / CVRPLIB `.sol` |
| `filo2`, `ails2` | CVRP on euclidean variants (they compute distances from coordinates) | X-format `.vrp` / CVRPLIB `.sol` |

Each run writes the solver's input into a scratch directory with the costs scaled to integers: exactly when the
data allow (x1000 for the 3-decimal Mamut2026 / Poryos2026 matrices, so the solver's cost unscales exactly and is
cross-checked), approximately otherwise -- conservatively for time windows, so a schedule the solver finds feasible
is feasible on the published data. HGS-CVRP computes in doubles and reads the published matrix as is (divided by
10, exactly, when a distance exceeds its 1e5 limit, e.g. Bogotá `shortest`). Coordinate solvers get coordinates in a
unit that fits their limits (FILO2 millimetres). The solver runs in its own process group
with a hard timeout and is killed with its children on cancellation. A run that ends without a solution file reports
the last lines the solver printed (an unpatched HGS-CVRP rejecting the matrix, a missing library), since the scratch
directory is gone by then. For LKH-3, `extra_args = ["RUNS = 10"]` adds lines to its parameter file, also when the
command is wrapped (`argv = ["taskset", "-c", "0", "{executable}", "{params}"]`). Any other solver that reads and writes
CVRPLIB-style files can be added to the config; see the [solution formats](../benchmarks/formats/solutions.md) page.
Such a solver is assumed to need symmetric costs: the asymmetric `fastest` and `shortest` variants are refused for
it, with the reason, unless its entry says `symmetric_only = false` (only declare that if it really reads an
asymmetric `FULL_MATRIX`; the generic input file says `TYPE : CVRP` whatever the matrix). A solver that
`extends` a built-in inherits the built-in's setting.

## Solutions found elsewhere

```bash
uv run mamut-routing check path/to/inst.vrp.json found.sol          # exit 0 valid, 1 invalid, 2 unreadable
uv run mamut-routing bks submit path/to/inst.vrp.json found.sol \
    --authors "Your Name (handle)" --method "LKH-3" --seed 1 --dry-run
```

`check` and `bks submit` read CVRPLIB `.sol` files, JSON routes and LKH-3 MTSP solution files, static and
time-dependent instances alike. The objective defaults to the one the family publishes. `--dry-run` reports
`would_create`, `would_replace` or `would_keep` without writing (`stored_invalid` when the stored BKS itself fails
the checker). `--meta KEY=VALUE` adds provenance, but not the fields the store writes (`authors`, `date`,
`validated_cost`, ...). When a declared cost is the checker's times a power of ten, `check` says it is probably in the
solver's scaled integer units.

## From Python, with any solver

```python
from mamut_routing_lib import run_solver, submit_bks

solved = run_solver("pyvrp", item.instance_path, time_limit_s=60, seed=42)
if solved.valid:
    update = submit_bks(item.instance_path, solved.result.routes,
                        authors="Your Name (handle)", metadata=solved.bks_metadata(campaign="my-campaign"),
                        checkable=solved.checkable)   # optional: the instance the check already loaded
    print(update.action, update.path, update.candidate_cost)
```

A solve reads a large distance matrix once, for the solver's input and the check; `checkable=` spares the store its
own read. `load_checkable(instance, path)` returns the same object for solutions found elsewhere.

Routes found by your own code go through `submit_bks(instance_path, routes, authors=..., metadata=...)` directly
(or `save_solution_as_bks_if_improved`, as before). The helpers load the instance (hydrating collection instances),
validate the routes with the checker, and write `<base>.bks.<Objective>.json` next to the instance only if it beats
the stored one. The write is a plain read/compare/write: keep one writer per instance (see
[Run a BKS campaign](../maintainer-guide/bks-campaigns.md)).

To contribute an improvement, send the solution file or open a pull request on the family's repository; the
maintainers re-run the checker. Next: [Export to CVRPLIB `.vrp`](export-vrp.md).
