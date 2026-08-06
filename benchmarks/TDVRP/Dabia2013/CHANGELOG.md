# Changelog — Dabia2013 TDVRP BKS

All notable changes to the curated `Dabia2013` TDVRP best-known solutions (BKS) are recorded here. Objective: **Duration** (duration minimization — the depot departure time of each route is a decision variable). Costs are the authoritative output of the canonical checker (`mamut_routing_lib.td.check_td_solution`): exact IEEE-754 double arithmetic, no epsilon thresholds, routes in canonical order (sorted by first customer), total summed in that order — so any strict improvement is real.

## 2026-08-06

**All 40 optimality certificates re-derived from scratch and re-stamped** under the four-solve agreement protocol (cold and warm starts crossed with the two labeling modes, an audited exact-pricing phase in every run, zero checker-infeasible priced columns) on Grid'5000, on the repaired kayros 1.5.1 build. The campaign was motivated by the 2026-08-05 withdrawal of one certificate in the Vu2020 TDVRPTW family and the subsequent finding that the certifying builds carried since-repaired pricing defects (documented in the kayros 1.5.1 release notes and CHANGELOG). Every re-issued stamp certifies bit-exactly the previously stored value; no solution data changed, and the stamps' provenance now cites this campaign and build.

## 2026-07-12

**8 stale optimality stamps retracted** (RC101 to RC108, n=50): the last stamps surviving from the superseded 2026-07-07 campaign carried pre-audit prover metadata, and the pricing-ladder audit voided their trust basis; the audited 2026-07-10/11 campaign and its 2026-07-11/12 weekend top-up leave all eight instances open at their time limits, so the values return to ordinary best-known status. Store-wide, every remaining optimality stamp now comes from the audited four-run protocol. This family carries 40 certified TDVRP BKS (n=25), unchanged.

## 2026-07-11

**40 BKS stamped proven optimal** (`metadata.optimality`) at n=25, under a full re-certification (stamps regenerated from scratch under a stronger protocol after a prover defect was found and fixed). Each stamp certifies four independent exact solves (cold and warm starts x two labeling modes) agreeing on the value, an audited exact-pricing phase in every run, zero checker-infeasible priced columns, and canonical-checker re-validation at stamping time. Instances whose runs disagreed, timed out, or priced a checker-infeasible column carry NO stamp.

## 2026-07-08

120 of 168 BKS improved (mean -1.04%, largest single improvement -2.77%) by a 20,808-run anytime-strategy head-to-head campaign on Grid'5000: kayros 0.4.0.dev0 (TD-ILS, TD-ACO+LS, and an ACO-then-ILS budget split, all over the granular time-dependent local search), per-size time limits (120 s for n<=30, 300 s for n<=60, 600 s for n<=100), seeds {42, 123, 456}, single-threaded runs. Improve-only fold: for each instance the campaign-best solution was re-priced by the canonical checker before writing (checker cost authoritative); stored BKS marked proven optimal were left untouched.

## 2026-07-07

19 BKS improved by exact solves — **proven optimal**: kayros 0.3.0 lera branch-price-and-cut (HiGHS backend, warm-started from the previous BKS, TL 600 s), from the certification campaign over all families n≤50. The R201–R211 n=25 and RC101–RC108 n=50 groups each collapse to a single TDVRP instance (identical customers, time windows ignored), so each group shares one proven optimum (4804.299826 and 9324.268643 respectively). Certificates: optimal under checker-exact route costs and standard LP/pricing tolerances, completeness modulo Lera epsilon dominance. The same campaign certified 40 of the other stored Dabia TDVRP n=25 BKS optimal as stored.

Structured optimality metadata: all 48 BKS of this family proven optimal by that campaign now carry a machine-readable `metadata.optimality` object — prover, certificate wording, proven optimum, dual bound, wall time (schema: `OptimalityMetadata`, mamut-routing-lib ≥ 0.4.0).

## 2026-07-06

All 168 BKS improved by the first sweep of kayros 0.2.0.dev0 TD-ACO with time-dependent local search (tree-evaluated VND, every accepted move repriced by the checker-identical fold), 10 seeds per instance on Grid'5000.

## 2026-07-05

Initial BKS population, 168/168: the TDVRP variant had no published or legacy solutions, so all BKS come from the initial large-scale seeding sweep across all four TD families (kayros 0.0.1 TD-ACO, Grid'5000, 10 seeds per instance, 13 520 runs total).

## 2026-07-02

Instances and ATF sidecars populated (no BKS yet — no historic TDVRP solutions exist for this material).
