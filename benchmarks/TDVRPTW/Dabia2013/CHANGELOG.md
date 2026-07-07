# Changelog — Dabia2013 TDVRPTW BKS

All notable changes to the curated `Dabia2013` TDVRPTW best-known solutions (BKS) are recorded here. Objective: **Duration** (duration minimization — the depot departure time of each route is a decision variable). Costs are the authoritative output of the canonical checker (`mamut_routing_lib.td.check_td_solution`): exact IEEE-754 double arithmetic, no epsilon thresholds, routes in canonical order (sorted by first customer), total summed in that order — so any strict improvement is real.

## 2026-07-07

1 BKS improved by an exact solve — **proven optimal**: RC106 n=50 (11760.356005 → 11756.555984), kayros 0.3.0 lera branch-price-and-cut (HiGHS backend, warm-started from the previous BKS, TL 600 s), from the certification campaign over all families n≤50. The same campaign certified 87 of the other stored Dabia TDVRPTW n=25/50 BKS optimal as stored (54 of 56 at n=25).

Structured optimality metadata: all 88 BKS of this family proven optimal by that campaign now carry a machine-readable `metadata.optimality` object — prover, certificate wording, proven optimum, dual bound, wall time (schema: `OptimalityMetadata`, mamut-routing-lib ≥ 0.4.0).

## 2026-07-06

18 BKS improved by the first sweep of kayros 0.2.0.dev0 TD-ACO with time-dependent local search (tree-evaluated VND, every accepted move repriced by the checker-identical fold), 10 seeds per instance on Grid'5000.

## 2026-07-05

6 BKS improved during the initial large-scale seeding sweep across all four TD families (kayros 0.0.1 TD-ACO, Grid'5000, 10 seeds per instance, 13 520 runs total).

## 2026-07-02

Initial population, reaching full 168/168 BKS coverage:

- 146 BKS seeded from the solutions published with Lera-Romero et al. (2020), all re-validated and re-priced by the canonical checker.
- 22 BKS added and 16 improved from Onyr's re-validated legacy heuristic store (2024–2026 TDVRPTW-benchmarks pipeline).
