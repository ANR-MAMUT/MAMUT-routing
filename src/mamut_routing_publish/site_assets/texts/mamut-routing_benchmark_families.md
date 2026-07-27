### `Sintef2008` (VRPTW)

`Sintef2008` is the MAMUT-routing curation of the most classical VRPTW benchmark convention. The instances themselves come from [Solomon 1987](https://pubsonline.informs.org/doi/10.1287/opre.35.2.254), for the original 100-customer instances (and their derived smaller 25 and 50-customer variants), and from [Gehring and Homberger 1999](http://www.mit.jyu.fi/eurogen99/papers/homberg.ps), for larger instances up to 1000 customers. These instances have been the reference workload for VRPTW research for decades. They define the usual `R`, `C`, and `RC` families, respectively random, clustered, and mixed customer distributions, with type-1 and type-2 variants reflecting tighter/shorter versus looser/longer TW scheduling structures.

The `Sintef2008` convention is not merely an instance collection: it is an evaluation contract. It uses Euclidean distances as arc costs, computed with double-precision floating point arithmetic, and a hierarchical objective: first minimize the number of vehicles (equivalently the number of non-empty routes), then break ties by minimizing total travel cost. This is the historical Solomon/SINTEF convention used by most metaheuristic papers reporting "best-known solutions" on the classical VRPTW.

In 2008, [SINTEF](https://en.wikipedia.org/wiki/SINTEF) proposed its [VRPTW benchmark website](https://www.sintef.no/projectweb/top/vrptw/) as a curated scoreboard for the Solomon and Gehring--Homberger instances. This was an important step towards standardization: researchers could retrieve instances, inspect BKS values, and submit improvements through a single institutional reference. SINTEF reports objective values rounded to two decimals, while explicitly specifying that the underlying distance evaluation uses `float64`, i.e., double-precision floating point arithmetic.

Though this benchmark became a cornerstone for VRPTW research, it remains perfectible. Issues include the still heavily manual-script work required to collect instances with their BKS from the website, several BKS values have historically been disputed because of rounding, scaling, or slightly different evaluation conventions. Some entries have objective values without machine-checkable route files, and improvements still rely on communication with a centrally maintained, non-open-source website. This creates a bottleneck: the community depends on a private institutional scoreboard for data that has become scientific infrastructure.

The MAMUT-routing `Sintef2008` family consolidates the SINTEF benchmark with alternative BKS sources such as [Combopt](http://combopt.org/tables/), [CVRPLib](https://galgos.inf.puc-rio.br/cvrplib/index.php/en/instances) BKS kindly provided by [Eduardo Queiroga](https://github.com/EduardoQueiroga) through personal communication and [Czech personal website](https://sun.aei.polsl.pl/~zjc/). The curated artifacts expose machine-readable instance files, BKS route files, objective-function metadata, and checker-compatible JSON. We also impose a deterministic route ordering, by sorting routes according to their first customer ID, so that route files and floating-point aggregation are reproducible across runs and formats.

Licensing note: MAMUT-routing-authored curation artifacts for this family are distributed under the [MIT License](https://mit-license.org/) where MAMUT-routing holds the relevant rights. The underlying historical benchmark definitions and some BKS sources remain third-party benchmark material and are not relicensed by this curation.

The family currently contains the 468 classical VRPTW instances over 8 different instance sizes, each with a `HierarchicalVehicleCost` BKS.

**May 2026 note.** The [CVRPlib](https://galgos.inf.puc-rio.br/cvrplib/index.php/en/instances) now also exposes its own VRPTW benchmark (previously unavailable through their website) built on the same Solomon and Gehring--Homberger instances, but under the DIMACS convention: a mono-cost objective over scaled, integerized arc costs (see `Dimacs2021` below). As such, their collection differs from our curated `Sintef2008` benchmark family since we respect the original hierarchical objective and floating-point costs, whereas cost-only integerized variants belong to a different benchmark contract.

### `Dimacs2021` (VRPTW)

`Dimacs2021` is the MAMUT-routing curation of the VRPTW convention introduced by the [DIMACS VRPTW competition](http://dimacs.rutgers.edu/index.php/programs/challenge/vrp/vrptw/) during the 12th DIMACS Implementation Challenge. It reuses the same Solomon and Gehring--Homberger instance universe as `Sintef2008`, but [changes the evaluation contract](https://dmac.rutgers.edu/files/8516/3848/0275/VRPTW_Competition_Rules.pdf) in two crucial ways: costs are integerized, and the objective is single-objective total-cost minimization, subject to the instance vehicle limit.

This change was motivated by long-standing difficulties with the classical SINTEF convention. Floating point arc costs make exact comparison delicate because of rounding errors and non-associativity. The hierarchical objective also complicates exact methods: minimizing fleet size first and distance second can require a two-stage optimization strategy, or at least solver-specific handling of lexicographic objectives. For many exact-method papers, a pure cost objective was therefore more natural, but for years the community lacked a widely accepted cost-only counterpart to SINTEF.

The DIMACS rules proposed such a counterpart. Euclidean distances are scaled by a factor 10 and truncated to integers. A DIMACS cost such as `8273` is therefore comparable, but not identical, to a SINTEF-style floating point distance around `827.3`. This integer contract makes objective values reproducible across languages and solvers, and it avoids many false improvements caused by reporting precision.

The DIMACS competition had a lasting impact because it gave heuristic and exact-method teams a shared, checker-oriented target. It also influenced modern solver tooling: for example, [PyVRP](https://github.com/PyVRP/PyVRP), built around Hybrid Genetic Search, naturally supports the DIMACS-style cost-minimization convention.

The original DIMACS benchmark material, however, was not distributed as a complete curated BKS repository. Public result tables were mainly provided through scoreboards and spreadsheets without route files. The MAMUT-routing `Dimacs2021` family fills this gap by collecting, validating, and normalizing route-level BKS files under the DIMACS objective. Several BKS sources were used, including CVRPLib-provided Solomon/Homberger solutions reevaluated under the DIMACS contract, PyVRP instance collections for larger cases, and additional personal experiments run on [Grid5000](https://www.grid5000.fr/w/Grid5000:Home).

Licensing note: MAMUT-routing-authored curation artifacts for this family are distributed under the [MIT License](https://mit-license.org/) where MAMUT-routing holds the relevant rights. The underlying historical benchmark definitions, competition material, and some BKS sources remain third-party material and are not relicensed by this curation.

The family currently mirrors the 468 classical instances over 8 different instance sizes, each with a `MonoCost` BKS.

**July 2026 note.** CVRPLib's newer VRPTW instances and BKS follow the DIMACS convention (scaled, integerized arc costs with mono-cost minimization), as [clarified by Leon Lan](https://github.com/PyVRP/PyVRP/discussions/1109), one of the PyVRP maintainers. Their BKS are therefore directly comparable with `Dimacs2021` whenever the remaining conventions (rounding/truncation and fleet limits) also match. An earlier note here incorrectly stated that CVRPLib's VRPTW material used `float64` arc costs.

### `Ortec2022` (VRPTW)

`Ortec2022` is the MAMUT-routing curation of the static VRPTW instances from the [EURO Meets NeurIPS 2022 Vehicle Routing Competition](https://euro-neurips-vrp-2022.challenges.ortec.com/), organized with direct support from [ORTEC](https://ortec.com/en-us). This competition followed the DIMACS VRPTW track by using a cost-minimization contract and integer travel costs, but it introduced a qualitatively different instance family.

Unlike Solomon and Gehring--Homberger, the ORTEC instances are not Euclidean synthetic benchmarks. They were derived from anonymized real grocery-delivery operations in the United States. Arc costs are explicit asymmetric travel-time matrices, service times and time windows come from operational data, and the coordinate fields are anonymized spatial references rather than the source of the objective. This makes the family one of the most visible modern VRPTW benchmarks based on realistic non-Euclidean travel data.

The competition included both static and dynamic VRPTW variants. MAMUT-routing currently curates the static VRPTW layer, because it matches the benchmark-as-contract goal of publishing fixed instances, machine-checkable solutions, and explicit objective metadata for the classic VRPTW. The original competition split the static instances into two subsets: a `public` set used during the first phase, and a `final` hidden set used to rank the 10 finalist teams.

The ORTEC contract differs from classical Solomon-style benchmarks in another important way: the number of vehicles is effectively unlimited such that constructing a feasible solution is always feasible and a trivial solution with one elementary route (`depot -> customer -> depot`) per customer is a valid Upper Bound. Like DIMACS, it uses a single-objective cost-minimization contract. In MAMUT-routing, ORTEC instances store `num_vehicles = null` to make this convention explicit.

The [quickstart repository](https://github.com/ortec/euro-neurips-vrp-2022-quickstart) provides the instances and final-round competition results. MAMUT-routing converts the original TSPLIB-like text files into checker-compatible JSON, preserves license metadata ([Creative Commons Attribution Non Commercial 4.0 International](https://creativecommons.org/licenses/by-nc/4.0/)), and writes one `MonoCost` BKS per instance. For the `final` subset, BKS files come from the published finalist results. For the `public` subset, BKS files were computed separately with a custom HGS-based solver over multiple seeds and long time limits on [Grid5000](https://www.grid5000.fr/w/Grid5000:Home).

Licensing note: ORTEC instances and related redistributed BKS files in MAMUT-routing retain the original [Creative Commons Attribution Non Commercial 4.0 International](https://creativecommons.org/licenses/by-nc/4.0/) terms. This is a non-commercial license and therefore differs from the [MIT License](https://mit-license.org/) used for MAMUT-routing source code.

One public instance required curation beyond direct format conversion: `ORTEC-VRPTW-ASYM-2e2ef021-d1-n210-k17` had one customer time window that made even the elementary route from the depot infeasible under the stored asymmetric matrix. The repaired MAMUT-routing instance records this explicitly in `metadata.repair_note`: customer 210 originally had `[8400, 11700]`, repaired to `[8400, 13378]`, where `13378` is the earliest depot-to-customer arrival time.

The family currently contains 350 static VRPTW instances: 250 `public` instances and 100 `final` instances, all with `MonoCost` BKS files. Note that for this family, size folders are buckets, not exact customer counts: for example, an instance under `n=200` may have 258 customers.

### `Poryos2026` (CVRP)

`Poryos2026` is the generated benchmark family introduced by MAMUT-routing. The goal is not to replace [CVRPLib](https://galgos.inf.puc-rio.br/cvrplib/index.php/en/instances), which remains the main historical repository for curated CVRP instances and BKS. Instead, `Poryos2026` proposes a reproducible generation workbench for creating routing instances from real-world [OpenStreetMap](https://www.openstreetmap.org/) (OSM) data, with enough metadata for users to understand where each instance comes from and how it was constructed and that allows direct plotting of routes on maps.

The CVRP layer is the base layer of the generated family. Instances are generated from OSM road networks and points of interest rather than from artificial Euclidean coordinates alone. The current pipeline selects customer candidates from selected Point of Interests (POI) categories such as restaurants, cafés or universities. These POIs are attached to nodes in an OSM-derived road graph, duplicate graph vertices are removed, and disconnected graph issues are handled by trimming to a connected component when needed.

Each source campaign can produce several metric variants over the same customer set. In the current MAMUT-routing layout, CVRP `Poryos2026` supports:

- `shortest`: road-network shortest-path distances, in meters;
- `fastest`: road-network travel times, using road-class speed estimates;
- `euclidean`: direct Euclidean distances between embedded customer coordinates, rounded to integers.

This makes the family useful for studying how solver behavior changes when the customer set is fixed but the travel model and arc-cost metrics changes. The `fastest` and `shortest` variants are asymmetric or road-network-derived when the underlying graph induces that behavior, while `euclidean` provides a classical geometric baseline.

Demands and capacity are generated synthetically but recorded in metadata. The `k` value visible in source names such as `brest_poi-n101-k14` is treated as a generation route-count signal or lower-bound indicator, not as a hard fleet cap. In the MAMUT-routing JSON metadata this is exposed as `num_vehicles_lb` when available.

The important design choice is that `Poryos2026` CVRP instances are not just raw generated files. They are benchmark artifacts with stable IDs, source-city metadata, generator version, source OSM file references, metric variant, sidecar manifests, route-rendering caches, and links to derived VRPTW artifacts. This is what makes the family compatible with the benchmark-as-contract perspective.

Licensing note: because this family is generated from OpenStreetMap data, the OSM-derived instances, sidecars, route-rendering artifacts, and related benchmark data are distributed under the [Open Data Commons Open Database License (ODbL) v1.0](https://opendatacommons.org/licenses/odbl/1-0/) where applicable, with attribution to OpenStreetMap and its contributors.

The seeded CVRP release currently contains several instances from real-world cities. Each currently has a `MonoCost` BKS produced by PyVRP/HGS. These BKS are heuristic reference solutions, not optimality certificates.

### `Poryos2026` (VRPTW)

`Poryos2026` is the generated benchmark family introduced by MAMUT-routing. It's VRPTW family is derived from the generated CVRP layer. This split is deliberate: first generate a real-world CVRP customer set and travel model from OSM data, then add service times and time windows under an explicit VRPTW generation contract. This avoids mixing geography, travel-time semantics, and temporal constraints into an opaque one-step generator.

The current VRPTW layer uses integer arc costs for reproducibility. The main metric variant is `fastest`, where arc costs are directly interpreted as travel times from the OSM road-network model. Earlier design notes also considered a `euclidean` VRPTW variant obtained by converting Euclidean meters to travel time using a fixed average speed of `14 m/s` (around 50 km/h). We also tested another conversion consisting in calculating the ratio between `fastest` and another non-time-based metric such as `shortest` or `euclidean` on the CVRP layer, then applying that ratio to the `euclidean` distances to get a time-based arc-cost matrix. Both those variants are highly synthetic and less directly connected to real-world travel times than the `fastest` variant. They also add another layer of complexity to the generation process, while being less useful for studying real-world VRPTW behavior. For these reasons, we decided to simplify the current VRPTW release by only including the meaningful `fastest` instances. 

Time windows are generated synthetically but with inspiration from Solomon's original benchmark logic. The workbench now supports two methods:

- `route_centered`: a Solomon `C`-class inspired method. A nearest-neighbour reference route is constructed, customer arrival times are simulated, and each time window is centered around the corresponding arrival time with randomized width. This is suited to clustered or route-structured temporal patterns.
- `reachable_interval`: a Solomon `R`/`RC`-class inspired method. Each customer receives a randomized window whose center is chosen inside an interval compatible with reaching that customer from the depot and returning before the depot horizon closes.

In both methods, service times are sampled deterministically from seeded random parameters, the depot horizon is explicit, and each customer time window is repaired if necessary so that the elementary route `depot -> customer -> depot` is always feasible. This elementary-route guarantee is weaker than providing a known full feasible solution, but it prevents trivially invalid customers and gives solvers a feasible upper-bound fallback when the fleet is unlimited or sufficiently loose.

The current generated time-window metadata records the method, horizon, service-time ratio, time-window ratio, and repair count. This is important for external users: a VRPTW instance is not fully described by coordinates, demands, service times, and time windows alone. Its benchmark meaning also depends on how those time windows were generated, whether they are route-centered or independently reachable, and how feasibility repairs were applied.

The VRPTW `Poryos2026` family is meant to complement, not replace, the historical `Sintef2008`, `Dimacs2021`, and `Ortec2022` families. `Sintef2008` and `Dimacs2021` provide continuity with decades of classical Solomon-style research. `Ortec2022` provides a realistic industry-derived benchmark. `Poryos2026` adds an open generation toolchain where geography, travel model, temporal policy, objective convention, and visualization are all explicit and reproducible.

Licensing note: because this family is derived from the OSM-based `Poryos2026` CVRP layer, the OSM-derived VRPTW instances, sidecars, route-rendering artifacts, and related benchmark data are distributed under the [Open Data Commons Open Database License (ODbL) v1.0](https://opendatacommons.org/licenses/odbl/1-0/) where applicable, with attribution to OpenStreetMap and its contributors.

The current family contains instances alongside heuristic BKS for both classical objectives: a `MonoCost` BKS and a `HierarchicalVehicleCost` BKS.

### `Dabia2013` (TDVRPTW)

`Dabia2013` is the MAMUT-routing curation of the classic Duration-Minimization time-dependent VRPTW benchmark introduced by [Dabia et al. 2013](https://doi.org/10.1287/trsc.1120.0445). It reuses the Solomon 1987 instances (25, 50, and 100 customers) and adds time dependency through the Ichoua--Gendreau--Potvin (IGP, 2003) travel-time model: piecewise-constant speeds per time zone and per arc speed profile, which yield FIFO piecewise-linear arrival-time functions. The raw JSON sources are those distributed with the open-source solver of [Lera-Romero et al. 2020](https://doi.org/10.1002/net.21937).

The MAMUT-routing curation replaces the historic textual formats with an explicit contract. Each instance ships the instance JSON (depot index 0, no duplicated end depot), a canonical arrival-time-function (ATF) sidecar giving one exact non-decreasing continuous piecewise-linear arrival-time function per arc of the complete graph, and a `Duration` BKS file. The ATFs are consolidated exactly from the raw IGP data: breakpoints are placed exactly where departure or arrival crosses a speed-zone boundary, each breakpoint is re-evaluated by the exact forward Ichoua loop, and the last zone's speed extends beyond the horizon so every ATF is total on the full time horizon.

The evaluation contract is defined by the canonical pure-Python checker (`mamut_routing_lib.td.check_td_solution`): route durations are computed by exact IEEE-754 double-precision composition of arrival-time and vertex ready-time functions, with no epsilon thresholds anywhere, each route dispatched at its optimal depot departure time, and the solution cost summed over routes in canonical order (sorted by first customer). BKS costs are always the checker's output.

Initial BKS were seeded from the solutions published with Lera-Romero et al. (2020) and re-validated by the checker. Several contain arrivals exactly on time-window deadlines, which fragile recomputation pipelines misreport as infeasible. Missing BKS were completed and existing ones have since been improved by [KAYROS](https://github.com/0nyr/kayros) heuristic runs on [Grid5000](https://www.grid5000.fr/w/Grid5000:Home); see the family changelog.

Licensing note: MAMUT-routing-authored curation artifacts for this family are distributed under the [MIT License](https://mit-license.org/) where MAMUT-routing holds the relevant rights. The underlying benchmark definitions (Solomon 1987; Dabia et al. 2013; the Lera-Romero et al. 2020 distribution) remain third-party material and are not relicensed by this curation.

The family currently contains 168 instances over 3 sizes (56 Solomon-derived instances each at 25, 50, and 100 customers), each with a `Duration` BKS.

### `Dabia2013` (TDVRP)

The TDVRP layer of `Dabia2013` is the same benchmark material with the time windows removed: same Solomon-derived customers, demands, capacities, service times, and the same canonical IGP arrival-time functions (the ATF sidecars are time-window-independent and therefore shared bit-for-bit with the TDVRPTW layer). The objective remains `Duration` minimization with per-route dispatch-time optimization under the canonical checker contract.

Dropping the time windows isolates the time-dependent routing core of the problem: solvers face the same time-varying travel times without the pruning power that tight Solomon time windows provide, which changes both heuristic and exact-method behavior (typically longer routes and much larger feasible neighborhoods). No historic solutions exist for this variant; all BKS were produced by [KAYROS](https://github.com/0nyr/kayros) heuristic runs on [Grid5000](https://www.grid5000.fr/w/Grid5000:Home) and are heuristic references, not optimality certificates.

Licensing note: as for the TDVRPTW layer, MAMUT-authored curation artifacts are under the [MIT License](https://mit-license.org/), while underlying third-party benchmark definitions are not relicensed.

The family currently contains 168 instances over 3 sizes, each with a `Duration` BKS.

### `Ari2018` (TDVRPTW)

`Ari2018` is a satellite family curated from the classic time-dependent TSPTW benchmark generator of the Arigliano et al. lineage: symmetric distance matrices, integer time windows, and IGP time-dependent travel speeds with 73 speed zones and 3 speed profiles shared by all arcs, parameterized by congestion depth (Delta in {70, 80, 90, 95, 98}), traffic pattern (A/B), time-window width and class, at sizes 15 to 40 customers.

The MAMUT-routing family is deliberately **not** the raw TD-TSPTW benchmark: it is a VRP variant curated for MAMUT-routing (2024--2026). Demands, vehicle capacities, fleet sizes, and gaussian service times were generated once during that curation and are pinned verbatim, with each instance recording the exact source of its attributes in its metadata; the raw Arigliano time windows are kept unchanged. Results on this family are therefore not comparable with published TD-TSPTW results on the underlying raw files.

The family ships a deterministic curated subset of 160 instances out of the 4800-instance full factorial: one per structural cell (size, Delta, pattern, TW width), preferring candidates that already carried a best-known solution, with remaining ties broken deterministically by a hash of the instance name. Since the raw data has no coordinates, display coordinates are a deterministic stress-layout embedding of the symmetric raw distance matrix (embedding quality recorded per instance). ATF sidecars are exact IGP consolidations cross-validated against direct Ichoua evaluation; the `Duration` checker contract is identical to the other TD families.

Licensing note: MAMUT-authored curation artifacts are distributed under the [MIT License](https://mit-license.org/); the underlying Arigliano-generator benchmark material remains third-party and is not relicensed.

The family currently contains 160 curated instances over 4 sizes (15, 20, 30, 40 customers), each with a `Duration` BKS.

### `Ari2018` (TDVRP)

The TDVRP layer of `Ari2018` is the same curated 160-instance subset with the time windows removed: same demands, capacities, fleet sizes, service times, and the same shared IGP arrival-time-function sidecars. The `Duration` objective and canonical checker contract are unchanged. No previously published solutions exist for this variant; all BKS come from [KAYROS](https://github.com/0nyr/kayros) heuristic runs on [Grid5000](https://www.grid5000.fr/w/Grid5000:Home).

Licensing note: as for the TDVRPTW layer, MAMUT-authored curation artifacts are under the [MIT License](https://mit-license.org/), while underlying third-party material is not relicensed.

The family currently contains 160 curated instances over 4 sizes, each with a `Duration` BKS.

### `Vu2020` (TDVRPTW)

`Vu2020` extends the same Arigliano-generator time-dependent model (identical IGP structure: 73 speed zones, 3 shared speed profiles) to the larger sizes used by [Vu et al. 2020](https://doi.org/10.1287/trsc.2019.0911): 59, 79, and 99 customers, with congestion depth Delta in {70, 80, 90, 98}, traffic patterns A/B, and absolute time-window widths from 40 to 180. Instance names keep the `Vu-` prefix while the recorded `instance_origin` is `Ari2018`, since both families share the same generator.

Like `Ari2018`, this family is a VRP variant curated for MAMUT-routing (2024--2026): demands, capacities, fleet sizes and gaussian service times were generated once during that curation and are pinned verbatim, with raw time windows kept unchanged. Two raw files have customer windows ending after the depot due date; they are retained because the evaluation contract naturally cuts off the unusable tail. It is not comparable with published TD-TSPTW results on the raw files. The family ships a deterministic curated subset of 168 instances out of the 840-instance full factorial, one per structural cell, with stress-layout display coordinates (near-exact for these sizes) and exact IGP-consolidated ATF sidecars under the canonical `Duration` checker contract.

Licensing note: MAMUT-authored curation artifacts are distributed under the [MIT License](https://mit-license.org/); the underlying Arigliano-generator benchmark material at Vu et al. (2020) sizes remains third-party and is not relicensed.

The family currently contains 168 curated instances over 3 sizes (59, 79, 99 customers), each with a `Duration` BKS.

### `Vu2020` (TDVRP)

The TDVRP layer of `Vu2020` is the same curated 168-instance subset with the time windows removed, sharing the arrival-time-function sidecars bit-for-bit with the TDVRPTW layer under the same `Duration` checker contract. At these sizes (59--99 customers) the variant provides the largest capacitated time-dependent instances of the current TD collection without time-window pruning. No previously published solutions exist for this variant; all BKS come from [KAYROS](https://github.com/0nyr/kayros) heuristic runs on [Grid5000](https://www.grid5000.fr/w/Grid5000:Home).

Licensing note: as for the TDVRPTW layer, MAMUT-authored curation artifacts are under the [MIT License](https://mit-license.org/), while underlying third-party material is not relicensed.

The family currently contains 168 curated instances over 3 sizes, each with a `Duration` BKS.

### `Rifki2020` (TDVRPTW)

`Rifki2020` is the real-world family of the TD collection, built from the time-dependent travel times of [Rifki, Chiabaut & Solnon 2020](https://doi.org/10.1016/j.trd.2020.102408): shortest travel times computed on the Lyon road network from a realistic traffic simulation built on real-world data. The family deliberately pins the 12-minute temporal granularity (K = 60 steps of 720 s over a 12 h horizon), as documented in the family README. This choice halves per-arc breakpoint weight versus the finest published granularity while remaining an equally authentic independent aggregation of the same simulation.

The defining preprocessing of this family is FIFO restoration. The raw data gives piecewise-constant travel times that violate FIFO at every boundary where travel time decreases; the canonical ATFs apply the arrival-time lower envelope (the exact form of the classic Malandraki & Daskin 1992 transformation), which keeps upward jumps as genuine vertical steps of the arrival-time functions. This makes `Rifki2020` the stress-test family for solver numerics: unlike the smooth IGP families, its ATFs contain exact vertical steps.

Vehicle attributes are deliberately not the original distribution's time-window files (degenerate for benchmarking: clustered near the horizon start, many identical, uniform service times, no demands or fleet data): time windows, gaussian service times, demands, capacities and fleet sizes were generated once during the 2024 curation, pinned verbatim and recorded in each instance's metadata. The real road network has no natural planar coordinates, so display coordinates are a deterministic stress-layout embedding of the time-averaged travel-time matrix (Kruskal stress about 0.05--0.12, recorded per instance); the checker never reads them. Results are not comparable with results on the original Rifki, Chiabaut & Solnon (2020) setting.

Licensing note: MAMUT-authored curation artifacts are distributed under the [MIT License](https://mit-license.org/); the underlying Lyon travel-time data of Rifki, Chiabaut & Solnon (2020) remains third-party and is not relicensed.

The family currently contains 180 instances over 6 sizes (10 to 60 customers, 30 instances each), each with a `Duration` BKS.

### `Rifki2020` (TDVRP)

The TDVRP layer of `Rifki2020` is the same 180-instance family with the time windows removed: same real Lyon envelope-FIFO arrival-time functions (shared bit-for-bit with the TDVRPTW layer), same curated demands, capacities, fleet sizes and service times, same `Duration` checker contract. It combines real-world time dependency, including genuine vertical steps in the arrival-time functions, with the unpruned search spaces of the no-time-window setting. No previously published solutions exist for this variant; all BKS come from [KAYROS](https://github.com/0nyr/kayros) heuristic runs on [Grid5000](https://www.grid5000.fr/w/Grid5000:Home).

Licensing note: as for the TDVRPTW layer, MAMUT-authored curation artifacts are under the [MIT License](https://mit-license.org/), while underlying third-party data is not relicensed.

The family currently contains 180 instances over 6 sizes, each with a `Duration` BKS.

### `Blauth2024` (TDVRPTW)

`Blauth2024` is the MAMUT-routing conversion of the delivery-only instances of the **vrptdt-benchmark** published by [Blauth, Held, Müller, Schlomberg, Traub, Tröbst & Vygen (2024)](https://doi.org/10.1016/j.disopt.2024.100848) ([upstream repository](https://gitlab.com/muelleratorunibonnde/vrptdt-benchmark), archived at [bonndata](https://doi.org/10.60507/FK2/X22BKR)). It is the major modern reference for realistic time-dependent routing: ten cities on four sub-continents (Berlin, Cincinnati, Kyiv, London, Madrid, Nairobi, New York, San Francisco, São Paulo, Seattle) at 10, 500, 1000 and 2000 customers, with travel times derived from real OpenStreetMap road networks and hourly Uber Movement speeds, shipped as dense per-arc piecewise-linear arrival-time functions. Uber Movement was shut down in 2023, so these published matrices can no longer be reproduced from public sources; redistributing them faithfully is also an act of preservation.

The instances are delivery-only TDVRPTW: an unlimited identical uncapacitated fleet (`num_vehicles = null`), depot departures at or after 15:00 with free return, three minutes of service per delivery, and hard time windows (half one-hour windows, half wide 15:30 to 21:00). The conversion is a value-exact integer relabeling of the upstream data with no numeric transformation; notably, this is the first family whose time unit is **integer milliseconds** rather than seconds (declared per instance, and 91% of the upstream breakpoints are not whole seconds, so any rescale would break bit-exactness). There is no TDVRP twin: upstream defines no time-window-free variant and the time windows are intrinsic to the instance generation. The upstream pickup-and-delivery variant is out of MAMUT-routing's node-routing scope and is not converted.

This family is also the first to use the `FleetCostDuration` objective: cost = sum of per-route optimal durations + 36000000 ms per route, which reproduces the upstream dollar objective ($200 per vehicle plus $20 per working hour) exactly as cost in $ = cost in ms / 180000. Best-known solutions at 500 to 2000 customers are imported from the upstream BonnTour high-effort reference solutions (credited to the seven authors; each was re-verified hard-feasible with the upstream evaluator's exact rational arithmetic, then repriced by the canonical checker with per-route departure re-optimization, so the stored costs sit just below the published dollar values, whose ceilings they match exactly). At 10 customers upstream publishes no solutions, so the [KAYROS](https://github.com/0nyr/kayros) entries are the first published results for that tier.

Hosting is hybrid because a single n=1000 arrival-time-function sidecar exceeds GitHub's file-size limit: the 10 and 500 customer tiers are hosted in full in the [satellite repository](https://github.com/ANR-MAMUT/MAMUT-routing-TDVRPTW-Blauth2024), while the 1000 and 2000 customer tiers ship best-known solutions plus SHA-256 pins, with instances regenerated locally by the deterministic converter in [MAMUT-routing-tools](https://github.com/ANR-MAMUT/MAMUT-routing-tools) and verified against the pins.

Licensing note: this family is distributed under [Creative Commons Attribution Non Commercial 4.0 International](https://creativecommons.org/licenses/by-nc/4.0/) because the underlying Uber Movement speed data is CC BY-NC 3.0. **Non-commercial use only**, with attribution to the original authors (full attribution block in the satellite repository's LICENSE: paper, upstream repository, bonndata DOI, OpenStreetMap ODbL, Uber Movement). This differs from the [MIT License](https://mit-license.org/) used for MAMUT-routing source code; the `Ortec2022` family sets the same precedent.

The family currently contains 20 hosted instances (n=10 and n=500, ten cities each) plus the converter-materialized n=1000/2000 tier, and 24 `FleetCostDuration` BKS files.

### `Lera2026` (TDVRPTW)

`Lera2026` does for time-dependent routing what Gehring & Homberger (1999) did for Solomon's testbed: it scales the classic IGP time-dependent travel-time model of [Ichoua, Gendreau & Potvin 2003](https://doi.org/10.1016/S0377-2217%2802%2900147-9) from 100 up to 1000 customers. The base data are the Gehring & Homberger VRPTW instances exactly as curated in the `Sintef2008` family (200 to 1000 customers, 60 instances per size). Travel speeds follow the IGP 2003 speed matrices, with three road categories whose speeds average about 1 and are assigned to the arcs by a seeded symmetric draw. The matrices are placed in the five-period day pattern of [Dabia et al. 2013](https://doi.org/10.1287/trsc.1120.0445), with morning and evening rush periods at 20–30% and 70–80% of the planning horizon. The family name honours Gonzalo Lera-Romero, whose open-source exact solver shaped modern work on this problem; the naming is purely honorific. The Solomon-based IGP testbed at 100 customers and below lives in the `Dabia2013` family.

The family has two tiers. The canonical `S2` core applies the medium-congestion scenario (rush-hour speeds halved) to all 300 base instances, so every Gehring & Homberger instance has exactly one canonical time-dependent counterpart. The `S1` and `S3` subsets form an intensity ladder: the mild (rush slowdown factor 1.5) and severe (factor 4) scenarios are applied to a fixed subset comprising instances 1, 5 and 10 of each of the six classes C1, C2, R1, R2, RC1 and RC2. The three scenarios of a base instance share the same road-category assignment, giving a controlled congestion ladder on identical geometry. There are 480 instances in total.

Two things distinguish the family technically. First, travel times are stored as a compact IGP specification rather than as explicit arrival-time-function files (a single such file would weigh roughly 80 MB compressed at 1000 customers): the arrival-time functions are rebuilt deterministically whenever an instance is loaded, and a recorded SHA-256 fingerprint guarantees that every rebuild reproduces the canonical functions bit for bit. Second, the instances carry a minimal time-window repair: the original deadlines assume unit travel speed, and under time-dependent speeds some customers would be unreachable by any route. Each such deadline is lifted exactly to the earliest possible time-dependent arrival (and the depot deadline to the worst single-customer round trip); the repair never changes travel times, and its magnitude is recorded in each instance's metadata. Results on this family are therefore not comparable with the static VRPTW literature.

Licensing note: the MAMUT-routing-authored artifacts of this family are distributed under the [MIT License](https://mit-license.org/); the underlying Gehring & Homberger instance definitions and the published methodologies of Ichoua et al. (2003) and Dabia et al. (2013) remain third-party material and are not relicensed.

The family currently contains 480 instances over 5 sizes (200 to 1000 customers) in three scenario subsets.

### `Lera2026` (TDVRP)

The TDVRP layer of `Lera2026` is the same 480-instance family with the time windows removed: same compact time-dependent travel-time specification (identical, bit for bit, to the TDVRPTW layer), same demands, capacities, fleet sizes, service times and horizon, same `Duration` evaluation contract. At 200–1000 customers with no time-window pruning, it is by far the largest-scale family of the time-dependent collection. All best-known solutions come from [KAYROS](https://github.com/0nyr/kayros) heuristic runs on [Grid5000](https://www.grid5000.fr/w/Grid5000:Home).

Licensing note: as for the TDVRPTW layer, MAMUT-routing-authored artifacts are under the [MIT License](https://mit-license.org/), while underlying third-party material is not relicensed.

The family currently contains 480 instances over 5 sizes in three scenario subsets.

### `Poryos2026` (TDVRPTW)

The time-dependent layer of the workbench-generated `Poryos2026` family consists of TDVRPTW instances whose congestion is derived from real city road networks rather than from the classic category-times-profile constructions of the literature (for that lineage see `Dabia2013` and `Lera2026`). Depot and customers are sampled by point-of-interest or hybrid sampling on the OpenStreetMap road graph of a real city: Lyon, Paris, San-Francisco, Hong-Kong, or Tokyo (central extracts). Every edge of the network carries an hourly speed profile over a 24-hour day. Two synthetic traffic models produce those profiles, and both ship as instances (the model tag is part of every instance name): `bpr` simulates a commuter population whose morning, lunch and evening trips load the network, converting hourly flows to speeds through the Bureau of Public Roads volume-delay function with road-class capacities; `wave` imposes a bimodal rush-hour speed dip scaled by road class, distance to the city center and a seeded per-edge jitter. Each model comes in three intensities (light, moderate, heavy), so rush-hour congestion emerges from the network structure. Under the heavy commuter scenario, the median arc takes about three times longer at 08:00 than at 03:00, while side streets mostly keep free flow and the best path between two customers can change with the departure time.

Per-arc travel times are the exact result of driving the fastest free-flow path through the time-varying edge speeds. They are stored as a compact road-graph specification rather than as explicit arrival-time-function files. The specification contains the trimmed subgraph of the city network that the instance actually uses, together with its speed profiles. The arrival-time functions are rebuilt deterministically whenever an instance is loaded (a pinned shortest-path rule fixes one canonical path per arc, exact per-edge arrival functions are sampled exactly along it, and the samples are decimated with a recorded tolerance), and a recorded SHA-256 fingerprint guarantees that every rebuild reproduces the canonical functions bit for bit. Time windows are synthesized by a time-dependent variant of the workbench's route-centered method and repaired to time-dependent feasibility, so every customer is individually serveable within the day. Sizes range from 10 to 1000 customers; the small sizes are exact-solver-friendly, the large ones stress heuristics on genuinely road-network-shaped time dependence.

Licensing note: the road networks derive from OpenStreetMap, and the benchmark data of this family is distributed under [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/) with attribution to [OpenStreetMap and its contributors](https://www.openstreetmap.org/copyright).

The family contains 360 instances over 6 sizes (10 to 1000 customers), 5 cities, 2 traffic models, 3 intensities and 2 sampling methods. Every instance carries a `Duration` BKS, seeded and re-seeded by [KAYROS](https://github.com/0nyr/kayros) anytime campaigns on [Grid5000](https://www.grid5000.fr/w/Grid5000:Home) through the standard improve-only, checker-authoritative pipeline.

### `Poryos2026` (TDVRP)

The TDVRP layer of the time-dependent `Poryos2026` family is the same instance set with the time windows removed: same road-graph travel-time specification (identical, bit for bit, to the TDVRPTW layer), same demands, capacities and service times, same `Duration` evaluation contract. Without time-window pruning, the large city instances expose the raw combinatorics of routing under road-network congestion.

Licensing note: as for the TDVRPTW layer, OpenStreetMap-derived benchmark data is under [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/) with attribution to OpenStreetMap and its contributors.

The family contains 360 instances over 6 sizes (10 to 1000 customers), 5 cities, 2 traffic models, 3 intensities and 2 sampling methods. Every instance carries a `Duration` BKS, seeded and re-seeded by [KAYROS](https://github.com/0nyr/kayros) anytime campaigns on [Grid5000](https://www.grid5000.fr/w/Grid5000:Home) through the standard improve-only, checker-authoritative pipeline.
