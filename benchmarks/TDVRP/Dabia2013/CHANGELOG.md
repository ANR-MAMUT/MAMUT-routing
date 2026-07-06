# Changelog — Dabia2013 TDVRP BKS

All notable changes to the curated `Dabia2013` TDVRP best-known solutions (BKS) are recorded here. Objective: **Duration** (duration minimization — the depot departure time of each route is a decision variable). Costs are the authoritative output of the canonical checker (`mamut_routing_lib.td.check_td_solution`): exact IEEE-754 double arithmetic, no epsilon thresholds, routes in canonical order (sorted by first customer), total summed in that order — so any strict improvement is real.

## 2026-07-06

All 168 BKS improved by the first sweep of kayros 0.2.0.dev0 TD-ACO with time-dependent local search (tree-evaluated VND, every accepted move repriced by the checker-identical fold), 10 seeds per instance on Grid'5000.

## 2026-07-05

Initial BKS population, 168/168: the TDVRP variant had no published or legacy solutions, so all BKS come from the initial large-scale seeding sweep across all four TD families (kayros 0.0.1 TD-ACO, Grid'5000, 10 seeds per instance, 13 520 runs total).

## 2026-07-02

Instances and ATF sidecars populated (no BKS yet — no historic TDVRP solutions exist for this material).
