# Glossary & Acronyms

Short, effective definitions for the acronyms and technical terms used across the MAMUT-routing pages, tables, and plots. Each acronym is given with its full-length expansion in *italics*. The list grew notably with the addition of the time-dependent (TD) benchmark families, so this page gathers the routing vocabulary, the time-dependent modeling terms, the objective and solution labels, and the infrastructure names in one place.

## Problem classes

- **VRP** — *Vehicle Routing Problem*. The general family of problems of designing least-cost vehicle routes that serve a set of customers from one or more depots.
- **CVRP** — *Capacitated Vehicle Routing Problem*. VRP where each vehicle has a fixed capacity and the total demand on a route cannot exceed it.
- **VRPTW** — *Vehicle Routing Problem with Time Windows*. CVRP where each customer must be served within a given `[earliest, latest]` time window.
- **TD** — *Time-Dependent*. Qualifies problems and models in which travel time along an arc depends on the departure time (traffic-varying speeds), as opposed to a single static travel-time matrix.
- **TDVRPTW** — *Time-Dependent VRPTW*. VRPTW where arc travel times vary with departure time, and each route is dispatched at an optimally chosen depot departure time.
- **TDVRP** — *Time-Dependent VRP*. The same time-dependent setting as TDVRPTW but with the customer time windows removed (only capacity and time-dependency remain).
- **TSP** — *Traveling Salesman Problem*. The single-vehicle (equivalently, single-route) special case of the VRP: since every customer must be visited, a solution is simply a permutation of the customers.
- **TSPTW** — *Traveling Salesman Problem with Time Windows*. Single-route problem with time windows; several TD families originate from time-dependent TSPTW benchmark generators.

## Time-dependent modeling

- **ATF** — *Arrival-Time Function*. Per-arc function `α(t)` giving the arrival time at the head of an arc as a function of the departure time `t` from its tail. The canonical model of the TD families; shipped as a sidecar file next to each instance.
- **TTF** — *Travel-Time Function*. Per-arc function `τ(t) = α(t) − t`, the travel time as a function of departure time, derived directly from the ATF. Plotted alongside the ATF in the arc-click viewer on TD instance pages.
- **NDCPWLF** — *Non-Decreasing Continuous Piecewise-Linear Function*. The exact shape of a canonical ATF: continuous, piecewise-linear, and non-decreasing in departure time (the internal ATF model is named `atf-ndcpwlf`).
- **FIFO** — *First-In, First-Out* property (no passing). A time-dependent travel model is FIFO when departing later can never lead to arriving earlier. All canonical ATFs are FIFO; some raw sources violate it and are FIFO-restored via the arrival-time lower envelope.
- **IGP** — *Ichoua–Gendreau–Potvin* (2003) travel-time model. Piecewise-constant speeds per time zone and per arc speed profile, which integrate into FIFO piecewise-linear arrival-time functions. The generator behind the `Dabia2013`, `Ari2018`, and `Vu2020` families; `Lera2026` scales the same model to the Gehring & Homberger instances (200 to 1000 customers) in the five-period day pattern of Dabia et al. (2013). The time-dependent `Poryos2026` layers use a different construction: OSM city road graphs with hourly speed profiles under two synthetic traffic models.
- **EAT** — *Earliest Arrival Time*. On the per-route ready-time plot, the earliest possible arrival back at the depot for the route.
- **MDT** — *Minimum Duration Time*. The route's minimum achievable duration `Δ*` (the y-axis value of the duration function), attained at the optimal depot departure time `t*` (the x-axis value); the point `(t*, Δ*)` is marked on the route duration function.

## Objectives and solutions

- **BKS** — *Best-Known Solution*. The best objective value (and, when available, the route set) known for an instance; provided as a per-instance BKS file.
- **HVC** — *HierarchicalVehicleCost*. Lexicographic VRPTW objective: minimize the number of vehicles first, then minimize total cost.
- **MC** — *MonoCost*. Single-objective cost minimization where total routing cost is optimized directly.
- **DUR** — *Duration*. Time-dependent duration-minimization objective: minimize the sum of route durations, with each route's depot departure time a decision variable and travel times varying with departure time. Used by all TD families.
- **TW** — *Time Window*. The `[earliest, latest]` interval within which a customer must be served; family tables also record a historical **TW type** (structural class of the time-window layout).

## Benchmarks, sources, and infrastructure

- **MAMUT** — *Machine learning And Matheuristics algorithms for Urban Transportation*. The [ANR research project](https://anr.fr/Projet-ANR-22-CE22-0016) (grant ANR-22-CE22-0016) that frames this benchmark and instance-generation work.
- **ANR** — [*Agence Nationale de la Recherche*](https://anr.fr/), the French National Research Agency funding the MAMUT project.
- **OSM** — [*OpenStreetMap*](https://www.openstreetmap.org/). The open geographic data source used to generate realistic road-network-backed instances and route geometries.
- **SINTEF** — *Stiftelsen for industriell og teknisk forskning* (Foundation for Industrial and Technical Research), the [Norwegian research organization](https://www.sintef.no/en/) whose classic [VRPTW benchmark conventions](https://www.sintef.no/projectweb/top/vrptw/) back the `Sintef2008` family.
- **DIMACS** — [*Center for Discrete Mathematics and Theoretical Computer Science*](http://dimacs.rutgers.edu/), host of the [12th Implementation Challenge](http://dimacs.rutgers.edu/index.php/programs/challenge/vrp/vrptw/) behind the `Dimacs2021` family.
- **ORTEC** — [the logistics-optimization company ORTEC](https://ortec.com/en-us) (used as a proper name today); the `Ortec2022` family curates the instances of the [EURO Meets NeurIPS 2022](https://euro-neurips-vrp-2022.challenges.ortec.com/) vehicle-routing competition.
- **EURO** — the [*Association of European Operational Research Societies*](https://www.euro-online.org/), co-organizer of that 2022 competition.
- **NeurIPS** — [*Conference on Neural Information Processing Systems*](https://neurips.cc/), co-organizer of the same 2022 competition.
- **KAYROS** — *Kayros Anytime-Yielding Routing Optimization Solver*, a [recursive acronym](https://en.wikipedia.org/wiki/Recursive_acronym) that is also a nod to [*Kairos*](https://en.wikipedia.org/wiki/Kairos), the ancient-Greek notion of the *right, opportune moment*. This is fitting for a time-dependent solver where *when* each route departs is itself a decision. Onyr's exact and anytime TD solver ([source](https://github.com/0nyr/kayros), [PyPI](https://pypi.org/project/kayros/)); the source of the `Duration` BKS entries for TD families lacking legacy solutions (runs performed on [Grid5000](https://www.grid5000.fr/w/Grid5000:Home)).
- **CLI** — *Command-Line Interface*. The optional `mamut-routing` command shipped by the [`mamut-routing-lib` library](https://github.com/ANR-MAMUT/MAMUT-routing-lib) for listing, downloading, and verifying benchmark archives.
- **PyPI** — the [*Python Package Index*](https://pypi.org/), from which [`mamut-routing-lib`](https://pypi.org/project/mamut-routing-lib/) is installed.
- **SPDX** — [*Software Package Data Exchange*](https://spdx.org/licenses/). The standard license identifiers (SPDX IDs) shown as license badges on family pages.
- **SHA-256** — 256-bit *Secure Hash Algorithm*, used to break ties deterministically when curating instance subsets.
- **IEEE-754** — the *IEEE Standard for Floating-Point Arithmetic* (IEEE = *Institute of Electrical and Electronics Engineers*); the canonical TD checker computes costs in exact IEEE-754 double precision with no epsilon thresholds.
