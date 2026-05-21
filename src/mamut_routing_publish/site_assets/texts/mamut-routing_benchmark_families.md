### `Sintef2008` (VRPTW)

`Sintef2008` is the MAMUT-routing curation of the most classical VRPTW benchmark convention. The instances themselves come from [Solomon 1987](https://pubsonline.informs.org/doi/10.1287/opre.35.2.254), for the original 100-customer instances (and their derived smaller 25 and 50-customer variants), and from [Gehring and Homberger 1999](http://www.mit.jyu.fi/eurogen99/papers/homberg.ps), for larger instances up to 1000 customers. These instances have been the reference workload for VRPTW research for decades. They define the usual `R`, `C`, and `RC` families, respectively random, clustered, and mixed customer distributions, with type-1 and type-2 variants reflecting tighter/shorter versus looser/longer TW scheduling structures.

The `Sintef2008` convention is not merely an instance collection: it is an evaluation contract. It uses Euclidean distances as arc costs, computed with double-precision floating point arithmetic, and a hierarchical objective: first minimize the number of vehicles (equivalently the number of non-empty routes), then break ties by minimizing total travel cost. This is the historical Solomon/SINTEF convention used by most metaheuristic papers reporting "best-known solutions" on the classical VRPTW.

In 2008, [SINTEF](https://en.wikipedia.org/wiki/SINTEF) proposed its [VRPTW benchmark website](https://www.sintef.no/projectweb/top/vrptw/) as a curated scoreboard for the Solomon and Gehring--Homberger instances. This was an important step towards standardization: researchers could retrieve instances, inspect BKS values, and submit improvements through a single institutional reference. SINTEF reports objective values rounded to two decimals, while explicitly specifying that the underlying distance evaluation uses `float64`, i.e., double-precision floating point arithmetic.

Though this benchmark became a cornerstone for VRPTW research, it remains perfectible. Issues include the still heavily manual-script work required to collect instances with their BKS from the website, several BKS values have historically been disputed because of rounding, scaling, or slightly different evaluation conventions. Some entries have objective values without machine-checkable route files, and improvements still rely on communication with a centrally maintained, non-open-source website. This creates a bottleneck: the community depends on a private institutional scoreboard for data that has become scientific infrastructure.

The MAMUT-routing `Sintef2008` family consolidates the SINTEF benchmark with alternative BKS sources such as [Combopt](http://combopt.org/tables/), [CVRPLib](https://galgos.inf.puc-rio.br/cvrplib/index.php/en/instances) BKS kindly provided by [Eduardo Queiroga](https://github.com/EduardoQueiroga) through personal communication and [Czech personal website](https://sun.aei.polsl.pl/~zjc/). The curated artifacts expose machine-readable instance files, BKS route files, objective-function metadata, and checker-compatible JSON. We also impose a deterministic route ordering, by sorting routes according to their first customer ID, so that route files and floating-point aggregation are reproducible across runs and formats.

Licensing note: MAMUT-routing-authored curation artifacts for this family are distributed under the [MIT License](https://mit-license.org/) where MAMUT-routing holds the relevant rights. The underlying historical benchmark definitions and some BKS sources remain third-party benchmark material and are not relicensed by this curation.

As of the current MAMUT-routing tree, this family contains the 468 classical VRPTW instances over 8 different instance sizes, each with a `HierarchicalVehicleCost` BKS.

**May 2026 note.** The [CVRPlib](https://galgos.inf.puc-rio.br/cvrplib/index.php/en/instances) now also exposes its own VRPTW benchmark (previously unavailable through their website) inspired by SINTEF, but with a different mono-cost objective. As such, their collection differs from our curated `Sintef2008` benchmark family since we respect the original hierarchical objective, whereas cost-only variants belong to a different benchmark contract.

### `Dimacs2021` (VRPTW)

`Dimacs2021` is the MAMUT-routing curation of the VRPTW convention introduced by the [DIMACS VRPTW competition](http://dimacs.rutgers.edu/index.php/programs/challenge/vrp/vrptw/) during the 12th DIMACS Implementation Challenge. It reuses the same Solomon and Gehring--Homberger instance universe as `Sintef2008`, but [changes the evaluation contract](https://dmac.rutgers.edu/files/8516/3848/0275/VRPTW_Competition_Rules.pdf) in two crucial ways: costs are integerized, and the objective is single-objective total-cost minimization, subject to the instance vehicle limit.

This change was motivated by long-standing difficulties with the classical SINTEF convention. Floating point arc costs make exact comparison delicate because of rounding errors and non-associativity. The hierarchical objective also complicates exact methods: minimizing fleet size first and distance second can require a two-stage optimization strategy, or at least solver-specific handling of lexicographic objectives. For many exact-method papers, a pure cost objective was therefore more natural, but for years the community lacked a widely accepted cost-only counterpart to SINTEF.

The DIMACS rules proposed such a counterpart. Euclidean distances are scaled by a factor 10 and truncated to integers. A DIMACS cost such as `8273` is therefore comparable, but not identical, to a SINTEF-style floating point distance around `827.3`. This integer contract makes objective values reproducible across languages and solvers, and it avoids many false improvements caused by reporting precision.

The DIMACS competition had a lasting impact because it gave heuristic and exact-method teams a shared, checker-oriented target. It also influenced modern solver tooling: for example, [PyVRP](https://github.com/PyVRP/PyVRP), built around Hybrid Genetic Search, naturally supports the DIMACS-style cost-minimization convention.

The original DIMACS benchmark material, however, was not distributed as a complete curated BKS repository. Public result tables were mainly provided through scoreboards and spreadsheets without route files. The MAMUT-routing `Dimacs2021` family fills this gap by collecting, validating, and normalizing route-level BKS files under the DIMACS objective. Several BKS sources were used, including CVRPLib-provided Solomon/Homberger solutions reevaluated under the DIMACS contract, PyVRP instance collections for larger cases, and additional personal experiments run on [Grid5000](https://www.grid5000.fr/w/Grid5000:Home).

Licensing note: MAMUT-routing-authored curation artifacts for this family are distributed under the [MIT License](https://mit-license.org/) where MAMUT-routing holds the relevant rights. The underlying historical benchmark definitions, competition material, and some BKS sources remain third-party material and are not relicensed by this curation.

As of the current MAMUT-routing tree, this family mirrors the 468 classical instances over 8 different instance sizes, each with a `MonoCost` BKS.

**May 2026 note.** CVRPLib's newer VRPTW material should be read carefully with respect to objective and cost-scaling conventions. Some BKS may overlap with `Dimacs2021` because both use cost-oriented evaluation on the classical instances, but a BKS is only comparable when the objective, cost scaling, rounding/truncation, and fleet-limit conventions match exactly, and CVRPLib's VRPTW instances use `float64` precision instead of scaled integers. 

### `Ortec2022` (VRPTW)

`Ortec2022` is the MAMUT-routing curation of the static VRPTW instances from the [EURO Meets NeurIPS 2022 Vehicle Routing Competition](https://euro-neurips-vrp-2022.challenges.ortec.com/), organized with direct support from [ORTEC](https://ortec.com/en-us). This competition followed the DIMACS VRPTW track by using a cost-minimization contract and integer travel costs, but it introduced a qualitatively different instance family.

Unlike Solomon and Gehring--Homberger, the ORTEC instances are not Euclidean synthetic benchmarks. They were derived from anonymized real grocery-delivery operations in the United States. Arc costs are explicit asymmetric travel-time matrices, service times and time windows come from operational data, and the coordinate fields are anonymized spatial references rather than the source of the objective. This makes the family one of the most visible modern VRPTW benchmarks based on realistic non-Euclidean travel data.

The competition included both static and dynamic VRPTW variants. MAMUT-routing currently curates the static VRPTW layer, because it matches the benchmark-as-contract goal of publishing fixed instances, machine-checkable solutions, and explicit objective metadata for the classic VRPTW. The original competition split the static instances into two subsets: a `public` set used during the first phase, and a `final` hidden set used to rank the 10 finalist teams.

The ORTEC contract differs from classical Solomon-style benchmarks in another important way: the number of vehicles is effectively unlimited such that constructing a feasible solution is always feasible and a trivial solution with one elementary route (`depot -> customer -> depot`) per customer is a valid Upper Bound. Like DIMACS, it uses a single-objective cost-minimization contract. In MAMUT-routing, ORTEC instances store `num_vehicles = null` to make this convention explicit.

The [quickstart repository](https://github.com/ortec/euro-neurips-vrp-2022-quickstart) provides the instances and final-round competition results. MAMUT-routing converts the original TSPLIB-like text files into checker-compatible JSON, preserves license metadata ([Creative Commons Attribution Non Commercial 4.0 International](https://creativecommons.org/licenses/by-nc/4.0/)), and writes one `MonoCost` BKS per instance. For the `final` subset, BKS files come from the published finalist results. For the `public` subset, BKS files were computed separately with a custom HGS-based solver over multiple seeds and long time limits on [Grid5000](https://www.grid5000.fr/w/Grid5000:Home).

Licensing note: ORTEC instances and related redistributed BKS files in MAMUT-routing retain the original [Creative Commons Attribution Non Commercial 4.0 International](https://creativecommons.org/licenses/by-nc/4.0/) terms. This is a non-commercial license and therefore differs from the [MIT License](https://mit-license.org/) used for MAMUT-routing source code.

One public instance required curation beyond direct format conversion: `ORTEC-VRPTW-ASYM-2e2ef021-d1-n210-k17` had one customer time window that made even the elementary route from the depot infeasible under the stored asymmetric matrix. The repaired MAMUT-routing instance records this explicitly in `metadata.repair_note`: customer 210 originally had `[8400, 11700]`, repaired to `[8400, 13378]`, where `13378` is the earliest depot-to-customer arrival time.

As of the current MAMUT-routing tree, this family contains 350 static VRPTW instances: 250 `public` instances and 100 `final` instances, all with `MonoCost` BKS files. Note that for this family, size folders are buckets, not exact customer counts: for example, an instance under `n=200` may have 258 customers.

### `Mamut2026` (CVRP)

`Mamut2026` is the generated benchmark family introduced by MAMUT-routing. The goal is not to replace [CVRPLib](https://galgos.inf.puc-rio.br/cvrplib/index.php/en/instances), which remains the main historical repository for curated CVRP instances and BKS. Instead, `Mamut2026` proposes a reproducible generation workbench for creating routing instances from real-world [OpenStreetMap](https://www.openstreetmap.org/) (OSM) data, with enough metadata for users to understand where each instance comes from and how it was constructed and that allows direct plotting of routes on maps.

The CVRP layer is the base layer of the generated family. Instances are generated from OSM road networks and points of interest rather than from artificial Euclidean coordinates alone. The current pipeline selects customer candidates from selected Point of Interests (POI) categories such as restaurants, cafés or universities. These POIs are attached to nodes in an OSM-derived road graph, duplicate graph vertices are removed, and disconnected graph issues are handled by trimming to a connected component when needed.

Each source campaign can produce several metric variants over the same customer set. In the current MAMUT-routing layout, CVRP `Mamut2026` supports:

- `shortest`: road-network shortest-path distances, in meters;
- `fastest`: road-network travel times, using road-class speed estimates;
- `euclidean`: direct Euclidean distances between embedded customer coordinates, rounded to integers.

This makes the family useful for studying how solver behavior changes when the customer set is fixed but the travel model and arc-cost metrics changes. The `fastest` and `shortest` variants are asymmetric or road-network-derived when the underlying graph induces that behavior, while `euclidean` provides a classical geometric baseline.

Demands and capacity are generated synthetically but recorded in metadata. The `k` value visible in source names such as `brest_poi-n101-k14` is treated as a generation route-count signal or lower-bound indicator, not as a hard fleet cap. In the MAMUT-routing JSON metadata this is exposed as `num_vehicles_lb` when available.

The important design choice is that `Mamut2026` CVRP instances are not just raw generated files. They are benchmark artifacts with stable IDs, source-city metadata, generator version, source OSM file references, metric variant, sidecar manifests, route-rendering caches, and links to derived VRPTW artifacts. This is what makes the family compatible with the benchmark-as-contract perspective.

Licensing note: because this family is generated from OpenStreetMap data, the OSM-derived instances, sidecars, route-rendering artifacts, and related benchmark data are distributed under the [Open Data Commons Open Database License (ODbL) v1.0](https://opendatacommons.org/licenses/odbl/1-0/) where applicable, with attribution to OpenStreetMap and its contributors.

As of the current MAMUT-routing tree, the seeded CVRP release contains several instances from real-world cities. Each currently has a `MonoCost` BKS produced by PyVRP/HGS. These BKS are heuristic reference solutions, not optimality certificates.

### `Mamut2026` (VRPTW)

`Mamut2026` is the generated benchmark family introduced by MAMUT-routing. It's VRPTW family is derived from the generated CVRP layer. This split is deliberate: first generate a real-world CVRP customer set and travel model from OSM data, then add service times and time windows under an explicit VRPTW generation contract. This avoids mixing geography, travel-time semantics, and temporal constraints into an opaque one-step generator.

The current VRPTW layer uses integer arc costs for reproducibility. The main metric variant is `fastest`, where arc costs are directly interpreted as travel times from the OSM road-network model. Earlier design notes also considered a `euclidean` VRPTW variant obtained by converting Euclidean meters to travel time using a fixed average speed of `14 m/s` (around 50 km/h). We also tested another conversion consisting in calculating the ratio between `fastest` and another non-time-based metric such as `shortest` or `euclidean` on the CVRP layer, then applying that ratio to the `euclidean` distances to get a time-based arc-cost matrix. Both those variants are highly synthetic and less directly connected to real-world travel times than the `fastest` variant. They also add another layer of complexity to the generation process, while being less useful for studying real-world VRPTW behavior. For these reasons, we decided to simplify the current VRPTW release by only including the meaningful `fastest` instances. 

Time windows are generated synthetically but with inspiration from Solomon's original benchmark logic. The workbench now supports two methods:

- `route_centered`: a Solomon `C`-class inspired method. A nearest-neighbour reference route is constructed, customer arrival times are simulated, and each time window is centered around the corresponding arrival time with randomized width. This is suited to clustered or route-structured temporal patterns.
- `reachable_interval`: a Solomon `R`/`RC`-class inspired method. Each customer receives a randomized window whose center is chosen inside an interval compatible with reaching that customer from the depot and returning before the depot horizon closes.

In both methods, service times are sampled deterministically from seeded random parameters, the depot horizon is explicit, and each customer time window is repaired if necessary so that the elementary route `depot -> customer -> depot` is always feasible. This elementary-route guarantee is weaker than providing a known full feasible solution, but it prevents trivially invalid customers and gives solvers a feasible upper-bound fallback when the fleet is unlimited or sufficiently loose.

The current generated time-window metadata records the method, horizon, service-time ratio, time-window ratio, and repair count. This is important for external users: a VRPTW instance is not fully described by coordinates, demands, service times, and time windows alone. Its benchmark meaning also depends on how those time windows were generated, whether they are route-centered or independently reachable, and how feasibility repairs were applied.

The VRPTW `Mamut2026` family is meant to complement, not replace, the historical `Sintef2008`, `Dimacs2021`, and `Ortec2022` families. `Sintef2008` and `Dimacs2021` provide continuity with decades of classical Solomon-style research. `Ortec2022` provides a realistic industry-derived benchmark. `Mamut2026` adds an open generation toolchain where geography, travel model, temporal policy, objective convention, and visualization are all explicit and reproducible.

Licensing note: because this family is derived from the OSM-based `Mamut2026` CVRP layer, the OSM-derived VRPTW instances, sidecars, route-rendering artifacts, and related benchmark data are distributed under the [Open Data Commons Open Database License (ODbL) v1.0](https://opendatacommons.org/licenses/odbl/1-0/) where applicable, with attribution to OpenStreetMap and its contributors.

The current family contains instances alongside heuristic BKS for both classical objectives: a `MonoCost` BKS and a `HierarchicalVehicleCost` BKS.
