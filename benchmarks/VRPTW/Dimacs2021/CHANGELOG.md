# Changelog — Dimacs2021 BKS

All notable changes to the curated `Dimacs2021` best-known solutions (BKS) are recorded here. Objective: **mono-cost** (minimize total cost only). Distances use the DIMACS-2021 metric: each arc cost is `floor(10 × d)` with `d` the Euclidean distance of the original Solomon / Gehring-Homberger coordinates (which the instance files store unscaled), and time windows and service times are ×10, so costs are exact integers and comparisons are exact. Because the stored coordinates do not define the costs, only the explicit-matrix `.vrp` export is faithful for this family.

## 2026-06-15

Re-scraped the [SINTEF TOP VRPTW website](https://www.sintef.no/projectweb/top/vrptw/) and **re-evaluated the SINTEF hierarchical solutions under the Dimacs2021 metric** (coordinates ×10, truncated integer distances). Although these solutions are optimized for SINTEF's hierarchical objective, several of them — once measured by the DIMACS integer cost — turn out to be cheaper than our pyvrp/HGS mono-cost BKS. They were adopted only where strictly better. All improvements are at `n=1000`, keep the same fleet size, and lower the integer cost:

| Instance | n | Vehicles | Cost (before → after) | Δ | Δ% |
|---|---:|---:|---|---:|---:|
| R1_10_2   | 1000 | 91 | 482616 → 481879 | −737 | −0.153% |
| R1_10_7   | 1000 | 91 | 439974 → 439315 | −659 | −0.150% |
| R1_10_6   | 1000 | 91 | 469282 → 468850 | −432 | −0.092% |
| R1_10_8   | 1000 | 91 | 422793 → 422462 | −331 | −0.078% |
| R1_10_3   | 1000 | 91 | 446733 → 446490 | −243 | −0.054% |
| RC1_10_10 | 1000 | 90 | 435337 → 435104 | −233 | −0.054% |
| R1_10_4   | 1000 | 91 | 424407 → 424199 | −208 | −0.049% |
| RC1_10_3  | 1000 | 90 | 421219 → 421058 | −161 | −0.038% |
| R1_10_9   | 1000 | 91 | 491628 → 491499 | −129 | −0.026% |
| R1_10_5   | 1000 | 91 | 504067 → 503989 | −78  | −0.015% |
| RC1_10_4  | 1000 | 90 | 413574 → 413503 | −71  | −0.017% |
| C1_10_9   | 1000 | 90 | 402884 → 402822 | −62  | −0.015% |
| R1_10_10  | 1000 | 91 | 473646 → 473616 | −30  | −0.006% |
| RC1_10_6  | 1000 | 90 | 448982 → 448962 | −20  | −0.004% |
| RC1_10_9  | 1000 | 90 | 438580 → 438562 | −18  | −0.004% |

Total cost reduction: **−3412** across 15 instances. Margins are small (all < 0.16 %) but exact: each is a strict integer improvement under the DIMACS metric. Solutions were validated with `mamut-routing-lib` (`check_solution`, including time-window feasibility under the integer metric) and adopted only when strictly better (`is_better_solution`).

### Metadata

- Removed the non-portable `source_path` field from every `Dimacs2021` BKS. It referenced a path inside the (not-yet-public) scraping repository and carried no value for downstream users. Provenance is still captured by `source`, `authors`, `date`, and `notes`.
