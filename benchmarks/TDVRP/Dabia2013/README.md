# Dabia2013 TDVRP benchmark family (TW-free variant)

Duration-Minimization TDVRP variant of the [TDVRPTW Dabia2013 family](../../TDVRPTW/Dabia2013/README.md): the exact same instances with time windows removed (service times, demands, capacity, fleet size and time-dependent travel times unchanged; the depot departure time remains a decision variable).

Artifacts are deliberately duplicated from the TDVRPTW family so each problem-family release stays self-contained: `.vrp.json` files simply omit `time_windows`, and the `.atf.json[.gz]` sidecars are byte-identical to their TDVRPTW counterparts (same sha256). See the TDVRPTW family README for format, conventions, provenance and licensing.

No BKS are seeded yet: the published Dabia2013 solutions are TDVRPTW solutions; TW-free best known solutions will be added once solvers have run on this variant.
