# Mamut2026 BKS campaign 2 — plan

*2026-09-06. Status: proposed, not started.*

## Why a second campaign

Every one of the 330 Mamut2026 best-known solutions comes from **one** run of
PyVRP's iterated local search: `method = pyvrp-ils-v1`, `seed = 42`,
`time_limit_s = 120`, on 2026-08-27. The README says so and calls them
"reference solutions, not optimality certificates". That was the right call
for a first release, but the family exists to measure how solver behaviour
changes with the arc-cost metric, and a single short run per instance is a
noisy ruler for that:

- **The budget is not converged.** Two probes run today on this machine
  (PyVRP 0.13.4, one core each):

  | instance | metric | 60 s | stored 120 s | gap |
  |---|---|---:|---:|---:|
  | `mamut-bogota-n4000-k508-poi` | euclidean | 98 633 760 | 96 358 989 | 2.4 % |
  | `mamut-cairo-n546-k26-poi` | shortest | 2 047 698 | 2 046 627 | 0.05 % |

  If doubling the budget still buys 2.4 % at n = 4000, 120 s is nowhere near
  the plateau there, and the published `shortest / euclidean` cost ratio
  (median 1.358) partly measures how far each slice was from convergence rather
  than the metric.
- **The seed is a single draw.** With one seed, a solver's run-to-run spread
  cannot be told apart from a metric effect. The spread itself is a quantity the
  experiment needs.
- **Provenance is thin.** The BKS metadata records the method label, seed and
  budget but not the PyVRP version or the machine. The next campaign should
  leave a record that can be re-run.

The write path already protects us: `save_bks_if_improved` re-validates the
stored solution and only replaces it with a strictly better one, so nothing in
this plan can make a BKS worse.

## What we are working with

| fact | value | where it matters |
|---|---|---|
| Solver | PyVRP 0.13.4 ILS, pinned `>=0.13.4,<0.14` in the lib; single-threaded per solve | one core per run; parallelism comes from running instances side by side |
| Entry point | `mamut-routing solve` (lib CLI) with `--time-limit-s`, `--seed`, `--jobs`, `--save-bks`; the library call is `solve_cvrp` / `solve_and_update_bks` | the campaign driver calls the library, not the CLI, to pass extra metadata |
| Costs | 3-decimal floats, scaled ×1000 to integers for PyVRP (lossless) | solver costs in the BKS are milli-units |
| Instances | 110 bases × 3 metrics; Σn = 62 942 per metric; 30 bases at n ≤ 200, 10 POI-tier bases at 1200–4000 | budgets must scale with n |
| POI-tier matrices | the 20 `shortest`/`fastest` distance sidecars above n = 1000 are sha256 pins, **not materialized in this clone** (0 of 20 present) | must be rebuilt before the campaign can touch those 20 instances |
| Memory per worker | 112 MB at n = 546; 1.57 GB at n = 4000 (measured RSS) | 10 concurrent workers fit in the local 30 GB even if all are POI-tier |
| Local compute | 12 cores, 30 GB RAM | 10 solver workers, 2 cores left for the desktop |
| Site VM | 6 vCPU, 16 GB, serves the public site | not a compute node; it only receives the result |
| Route geometry | content-addressed by BKS sha256; rebuilt for every replaced `shortest`/`fastest` BKS | up to 220 geometry rebuilds after the campaign, to be done locally |
| Existing driver | `paper7/src/paper7_experiments/compute_bks_experiments.py`: seeds × instances, per-run JSON, resumable, multiprocessing | the starting point for the campaign driver |

Reproducibility note: PyVRP runs stop on wall-clock time, so a `(seed,
time_limit)` pair is **not** bit-reproducible across machines or loads. The
reproducible artifact is the solution file itself, which the checker
re-validates on every load. The campaign records seeds and budgets for
provenance, not for replay.

## Design

Three phases of compute, bracketed by a tooling step before and a publication
step after. Every solver run, winner or not, is archived: the losers are the
seed-spread data the experiment needs.

### Phase 0 — tooling (half a day, no solver time)

1. **Materialize the POI-tier matrices.** 10 bases × 2 metrics, 563 MB, each
   checked against its pin:

   ```bash
   uv run --project MAMUT-routing-tools mamut-tools generate materialize-distances \
       benchmarks/Mamut2026/CVRP/shortest benchmarks/Mamut2026/CVRP/fastest
   ```

   Verify afterwards that `mamut-routing list --benchmark-name Mamut2026` resolves
   all 330 instances with no missing-sidecar error.

2. **Library changes in `MAMUT-routing-lib` (one small PR):**
   - `solve_cvrp` gains `initial_routes: list[list[int]] | None` (mapped to
     PyVRP's `initial_solution`, which `pyvrp.solve` already accepts) so the
     polish phase can warm-start from the best incumbent.
   - `solve_cvrp` gains `collect_stats: bool` and returns `result.stats` on the
     `MethodResult` when asked, so the pilot gets the full cost-versus-time
     curve from one long run instead of many short ones.
   - `MethodResult.metadata` carries `pyvrp_version` (from
     `importlib.metadata`) and `arc_cost_scale` always. Tests for both.

3. **Campaign driver** in the workbench, evolved from
   `compute_bks_experiments.py`, kept out of the library: it is experiment code.
   Requirements:
   - per-instance budget `T(n)` (formula below), seeds from the command line;
   - one JSON per run under `outputs/<campaign>/runs/`, resumable by run key
     (already there), so a crash or a reboot loses at most the runs in flight;
   - a `--phase` switch: `pilot` (long run with stats), `main` (S seeds at
     `T(n)`), `polish` (warm start from the best archived run at `2·T(n)`);
   - **largest instances first** (longest-processing-time scheduling), 10
     workers; no cap on POI-tier concurrency is needed at 1.6 GB each;
   - BKS metadata written on improvement: `method`, `seed`, `time_limit_s`,
     `wall_time`, `solver_cost`, `pyvrp_version`, `campaign: "mamut2026-bks-2"`,
     `phase`, `host` (CPU model), and for polish runs `warm_start_sha256` of the
     archived solution it started from;
   - a ledger `ledger.csv` with one row per run (instance, metric, n, seed,
     phase, budget, wall time, cost, routes, validated, bks action).

4. **Baseline snapshot.** The current 330 BKS are commit `e7ca957` of the
   satellite; tag it `bks-campaign-1` there so the before/after comparison has
   a fixed reference, and export a `baseline.csv` of the 330 costs.

### Phase 1 — calibration pilot (about 14 wall-hours, overnight)

Purpose: choose `T(n)` and the seed count from measurement rather than
convention. Working assumption going in, to be confirmed or replaced:

```
T(n) = clamp(2.4 · n seconds, 300 s, 7 200 s)
```

That is the HGS-CVRP family's "budget proportional to n" practice with a floor
for the small rungs and a two-hour cap for the three n = 4000 bases.

Sample: 10 bases spanning the ladder and the POI tier
(n ≈ 100, 150, 230, 350, 500, 700, 1000, 1500, 2500, 4000; take the base at
the closest rung, preferring one per sourcing method), × 3 metrics = 30
instances. For each:

- one run at **4·T(n)** with `collect_stats=True`, giving the whole
  best-cost-versus-time curve in a single run;
- **3 seeds** at `T(n)` to measure the seed spread at the candidate budget.

Cost: about 7·T(n) per instance, 140 core-hours in total, 14 wall-hours on
10 workers.

Decision rules, applied per size band from the curves:

- if the median remaining improvement from `T(n)` to `4·T(n)` is below
  **0.1 %**, keep `T(n)`; between 0.1 % and 0.5 %, double it for that band;
  above 0.5 %, quadruple it and re-examine the cap (the n = 4000 bases are the
  likely case);
- seed count `S = 5` if the spread (max − min over the 3 seeds, as a fraction
  of the min) is below 0.3 % in median; `S = 8` otherwise;
- record the iteration rate per second as a function of n; it tells us whether
  the POI tier is limited by the budget or by the search itself.

Write the outcome into this report before phase 2 starts.

### Phase 2 — main campaign (about 2.5 wall-days at the working assumption)

All 330 instances × `S` seeds at `T(n)`, seeds `1..S` (not 42: the seed-42 run
already exists and stays in the comparison as the first-campaign point).

Compute at `S = 5` and the working `T(n)`:

| slice | instances | Σ budget per seed |
|---|---:|---:|
| main tier, n ≤ 1000 | 300 | ≈ 79 core-hours |
| POI tier, 1200–4000 | 30 | ≈ 41 core-hours |
| total per seed | 330 | ≈ 120 core-hours |
| × 5 seeds | 1 650 runs | ≈ 600 core-hours |
| on 10 workers | | **≈ 60 wall-hours** |

Every feasible run is validated and offered to `save_bks_if_improved`; the BKS
on disk therefore tracks the best run seen so far, and the ledger keeps all of
them.

Optional cross-check, cheap and worth doing: solve the 110 **euclidean**
instances once more with an independent solver (HGS-CVRP through PyHygese,
which takes an explicit symmetric matrix) at the same `T(n)`. It cannot serve
the asymmetric `shortest`/`fastest` slices, but where it beats PyVRP on the
symmetric slice we learn that the ILS has a systematic weakness the seed count
does not fix. Any improvement it finds is a valid BKS after the checker
validates it.

### Phase 3 — polish (about 1 wall-day)

One warm-started run per instance at `2·T(n)`, initial solution = the best
archived run for that instance, seed 1000 + instance index. ILS restarts from
its incumbent, so this is a deep local exploration around the best basin rather
than a new draw. About 240 core-hours, 24 wall-hours.

Stop here. A third round of the same solver at the same budget has
diminishing returns; if the pilot's curves show the POI tier still moving at
`4·T(n)`, the right follow-up is a longer cap for those 30 instances alone, not
another pass over everything.

### Phase 4 — validation and acceptance

Before anything is committed:

1. **Independent recomputation.** A script that reads each BKS and the resolved
   arc-cost matrix and recomputes the cost with plain Python floats, compared to
   the `cost` field at 1e-6. This is a second implementation, separate from the
   checker the writer used.
2. **Invariants re-checked over all 330:** feasible, every customer exactly
   once, route count ≥ the `k` in the name (`num_vehicles_lb`), cost ≤ the
   baseline cost (equality allowed, never greater).
3. **The README's numbers regenerated, not edited:** the median and range of
   `shortest / euclidean`, the median route count per metric, the maximum
   single-route share of customers (currently 24 %), and the geometry totals.
   Put the script in the workbench so the numbers stay reproducible.
4. **Campaign summary** for the changelog and the paper: how many BKS were
   replaced (expected: nearly all), the improvement distribution over the
   baseline per metric and per size band, the seed spread per metric. The
   per-metric spread is the first real measurement of the family's question.

### Phase 5 — publication

In order:

1. Commit the BKS files in the satellite (`MAMUT-routing-Mamut2026`) with the
   ledger at `campaigns/2026-09-bks-campaign-2/ledger.csv` (a few hundred KB;
   the full run solutions stay in the workbench `outputs/` and a tarball, they
   are not needed to reproduce the BKS since each BKS is self-contained). Add a
   CHANGELOG entry under `[Unreleased]` → *Changed*, replace the README's
   "first-pass campaign (PyVRP/HGS, 120 s per instance, seed 42)" paragraph
   with the campaign-2 description and the regenerated numbers, tag
   `bks-campaign-2`.
2. Bump the submodule pointer in MAMUT-routing (`benchmarks/Mamut2026`).
3. **Rebuild route geometry locally** for every replaced `shortest`/`fastest`
   BKS (`site build`; the cache is keyed by BKS sha256 so unchanged BKS reuse
   their entries). The VM could not finish the n = 4000 Bogotá geometry in 90
   minutes at 16 GB, so this must not be left to the deploy: copy
   `dist/route-geometry-cache` to the VM first, then deploy per the runbook and
   confirm `generated=0 reused=N` in the log.
4. Site FAQ and the family text (`mamut-routing_benchmark_families.md`) if
   they mention the 120 s pass.

## Risks and open points

- **Wall time on one machine.** Phases 1–3 total roughly 4.5 days of the local
  box at 10 workers. If a lab cluster or a second machine is available, the
  driver's per-run files make it trivial to split by seed across hosts; raise
  `S` to 10 in that case rather than shortening budgets.
- **PyVRP 0.13 is new ILS code.** Version 0.13 replaced HGS with ILS upstream
  and the wrapper was ported to it. The euclidean cross-check with HGS-CVRP is
  the safeguard against a solver-specific blind spot; if it wins broadly, the
  plan should add HGS-CVRP as a second primary solver on the symmetric slice
  before publishing.
- **Asymmetry.** `shortest`/`fastest` matrices are asymmetric (up to 15 %
  between directions). PyVRP handles this natively; any alternative solver
  must be checked for a symmetry assumption before its results are trusted.
- **Do not run on the VM.** It serves the site and has no spare memory for a
  1.6 GB worker.
- **The first-campaign figures in the README become stale** the moment a BKS is
  replaced; the regeneration script in phase 4 is what keeps the README honest,
  so it is part of the deliverable rather than a nicety.
- **Poryos2026** carries the same kind of single-run BKS (HGS, 480 s, seed
  123, 1 080 instances). The driver and the acceptance scripts are written so
  a later campaign there is a parameter change, not new code.

## Checklist

- [ ] Phase 0: matrices materialized (20/20 pins verified), lib PR merged,
      driver in the workbench, `bks-campaign-1` tag and `baseline.csv`
- [ ] Phase 1: pilot run, `T(n)` and `S` fixed and recorded in this report
- [ ] Phase 2: 330 × S runs archived, ledger complete
- [ ] Phase 2b (optional): HGS-CVRP cross-check on the euclidean slice
- [ ] Phase 3: polish runs archived
- [ ] Phase 4: independent recomputation clean, invariants clean, README
      numbers regenerated, campaign summary written
- [ ] Phase 5: satellite committed and tagged, submodule bumped, geometry
      cache rebuilt locally and copied, site deployed
