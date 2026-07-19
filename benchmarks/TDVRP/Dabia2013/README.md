# Dabia2013 TDVRP benchmark family (TW-free variant)

Duration-Minimization TDVRP variant of the [TDVRPTW Dabia2013 family](../../TDVRPTW/Dabia2013/README.md): the exact same instances with time windows removed (service times, demands, capacity, fleet size and time-dependent travel times unchanged; the depot departure time remains a decision variable).

Artifacts are deliberately duplicated from the TDVRPTW family so each problem-family release stays self-contained: `.vrp.json` files simply omit `time_windows`, and the `.atf.json[.gz]` sidecars are byte-identical to their TDVRPTW counterparts (same sha256). See the TDVRPTW family README for format, conventions, provenance and licensing.

Every instance carries a `Duration` BKS. The published Dabia2013 solutions are TDVRPTW solutions, so no historic TW-free solutions existed for this variant; all BKS come from [KAYROS](https://github.com/0nyr/kayros) heuristic runs on [Grid5000](https://www.grid5000.fr/w/Grid5000:Home) (see the [CHANGELOG](CHANGELOG.md)) and are heuristic references, not optimality certificates.
