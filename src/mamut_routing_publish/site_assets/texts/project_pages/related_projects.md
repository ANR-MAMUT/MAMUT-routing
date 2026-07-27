# Related Projects

Several related projects are useful context for MAMUT-routing, even when they are not benchmark families shipped directly in the current tree.

MAMUT-routing is, first and foremost, a curated benchmark vendor: a benchmark is not only a set of instance files, it is a contract made of data provenance, objective semantics, numerical conventions, solution format, validation code, and maintenance policy. It also ships its own workbench for generating realistic routing instances from real-world data (the pipeline behind the `Poryos2026` family) as a second, complementary role. The two sections below group related projects accordingly.

## Companion software and solvers

### mamut-routing-lib

[`mamut-routing-lib`](https://github.com/ANR-MAMUT/MAMUT-routing-lib) is the companion Python library and command-line interface for consuming MAMUT-routing artifacts. It provides benchmark discovery, typed loading, objective-aware BKS handling, validation and checker interfaces, and utilities for integrating the repository into reproducible experiment pipelines. Use it when an application needs programmatic access to the benchmark contracts rather than direct JSON or VRPLIB file handling.

### PyVRP

[`PyVRP`](https://github.com/PyVRP/PyVRP) is a high-performance vehicle-routing solver with Python interfaces. It is a natural tool for producing or improving quality BKS candidates for the static CVRP and VRPTW families distributed by MAMUT-routing. Candidate solutions must still be checked under the exact objective, numerical, fleet, and feasibility contract published with each MAMUT-routing instance.

### KAYROS

[`KAYROS`](https://github.com/0nyr/kayros) is the solver used for time-dependent routing experiments around the TDVRP and TDVRPTW families. It consumes arrival-time functions and the corresponding duration-oriented contracts, making it the companion solver for obtaining or improving BKS candidates when static CVRP/VRPTW solvers are not applicable.

## Related benchmark & curation projects

### Combopt

[Combopt](http://combopt.org/tables/) and its [open repository](https://github.com/rogalski-wmii-uni-lodz-pl/vrp-benchmarks) provide one of the most useful community-maintained mirrors of classical VRP/VRPTW benchmark information. Its history section, GitHub repository, and overall design are direct inspiration for MAMUT-routing's benchmark-as-contract approach. Maintained by [Marek Rogalski](https://github.com/rogalski-wmii-uni-lodz-pl), it builds heavily on SINTEF's BKS culture and adds scripts and a checker-oriented workflow. It does not fully solve the reproducibility problem: many historical BKS files are missing or empty, the update policy is not always explicit, and the website itself is not open-source. Still, it is a useful community resource and a strong proof of concept for a curated benchmark repository.

### CVRPLib

[CVRPLib](https://galgos.inf.puc-rio.br/cvrplib/index.php/en/instances) is the reference infrastructure for CVRP benchmarks and BKS. It is important for MAMUT-routing in two ways. First, it shows how useful a centralized curated benchmark library can be when it is widely trusted. Second, its newer VRPTW material overlaps with the classical Solomon and Homberger universe and follows the DIMACS convention (mono-cost minimization over scaled, integerized arc costs), so CVRPLib-derived VRPTW BKS align with `Dimacs2021` rather than `Sintef2008`, and the remaining conventions must still be checked before any comparison.

### VRP-REP

[VRP-REP](http://www.vrp-rep.org/) was an ambitious attempt to provide a broader repository, checker, and specification platform for multiple VRP variants, including VRPTW. Its goal is close in spirit to MAMUT-routing: make benchmark data more structured and reusable. The project appears inactive today, which is a useful warning that benchmark infrastructure needs not only a schema, but also maintainable tooling, clear ownership, and an update process that survives beyond the initial publication.

### vrptdt-benchmark (Blauth et al., University of Bonn)

The [vrptdt-benchmark](https://gitlab.com/muelleratorunibonnde/vrptdt-benchmark) of [Blauth, Held, Müller, Schlomberg, Traub, Tröbst & Vygen (2024)](https://doi.org/10.1016/j.disopt.2024.100848) is the major modern benchmark for vehicle routing with time-dependent travel times: ten real cities, OpenStreetMap road networks, hourly Uber Movement speeds, exact piecewise-linear arrival-time functions, published together with an exact-rational solution evaluator and BonnTour reference solutions (archived at [bonndata](https://doi.org/10.60507/FK2/X22BKR)). Beyond the data, the paper's algorithmic contributions (notably their balanced route-tree structure for constant-time move evaluation under time-dependent travel times) anchor modern heuristic work on the problem. MAMUT-routing redistributes the delivery-only instances as the `Blauth2024` family (value-exact conversion, CC BY-NC 4.0 with full attribution); the pickup-and-delivery variant remains upstream-only.

### Dietmar Wolz's VRPTW Repository

Dietmar Wolz's [VRPTW repository](https://github.com/dietmarwo/VRPTW) is a smaller but relevant reproducibility-oriented project. It discusses precisely the ambiguities that motivate MAMUT-routing: cost-only versus hierarchical objectives, rounding policies, validation, and the difficulty of comparing solver results when route files and checkers are not shared consistently.

## Related instance-generation projects

### Timefold quickstarts (vehicle-routing example)

[Timefold](https://timefold.ai) ships a vehicle-routing example (`timefold-quickstarts`, `java/vehicle-routing/`) as a demo application for its constraint-solving engine. Historically, `timefold-solver` (through v1.9.0, inherited from its OptaPlanner ancestry) vendored unmodified copies of classical benchmark sets (the full Uchoa et al. CVRPLIB X-set, the Augerat A-set, and a subset of Gehring & Homberger VRPTW instances) as import fixtures for that example app; the whole `examples/` module, vendored data included, was removed in v1.10.0. The current quickstarts example instead ships a small, fully parameterized, seeded synthetic generator (a handful of named city profiles, arbitrary sizes and seeds reachable) for demo purposes: no best-known-solution tracking, no fixed objective contract, no maintenance as a benchmark.

Timefold has therefore never defined a benchmark of its own. What it vendored was always someone else's (already available from CVRPLIB and SINTEF directly), and what it generates today is a demo-data tool. Architecturally, that generator is closer to MAMUT-routing's own workbench (the pipeline behind `Poryos2026`) than to a curated benchmark family, which is why it is listed here rather than among the curated benchmark families.
