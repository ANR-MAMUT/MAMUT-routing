# Mamut2026 — the MAMUT-routing designed-diversity CVRP collection

Mamut2026 is a CVRP benchmark generated from real OpenStreetMap city road
networks, built for one experiment: **does changing the metric between customers
change how state-of-the-art solvers perform?**

Every base instance is materialized under all three arc-cost metrics —
`euclidean`, `shortest` (road distance, metres) and `fastest` (free-flow road
time, seconds) — over identical customers, demands and vehicle capacity. Within
a triple the metric is the only thing that varies, so a solver comparison across
the three is a controlled comparison.

## Why it is designed rather than gridded

Its sibling [`Poryos2026`](../Poryos2026/README.md) is a full cartesian grid: 5
cities × 6 sizes × 2 sampling methods. That is the right shape for the paired
CVRP↔TDVRP comparisons it was built for, and the wrong shape here. Demand
regime, depot placement and capacity tightness are effectively fixed across such
a grid, and five cities are a small, non-random sample of road networks — so a
difference between metric slices could not be separated from "these particular
instances".

Mamut2026 is the opposite: **one instance per city, one city per instance**, over
the 100+ fetched extracts, with configurations chosen so the set spans the space
of instance characteristics. This follows the design of the Uchoa et al. (2017)
CVRP `X` set — the seven demand distributions, seven average-route-size bands,
three depot placements and three customer placements are the same vocabulary —
moved onto real road networks and materialized under three metrics.

**Size is a covariate, not a factor.** Like the `X` set, `n` moves smoothly
across the collection: 100 distinct values rising geometrically from 100 to
1000, one per instance. A benchmark that piles a dozen instances on each of
eight round sizes can only compare buckets; this one can be regressed against.
Spacing is geometric because the step from 100 to 110 changes a CVRP far more
than the step from 900 to 910.

**Half the instances are drawn entirely from real amenities.** That is what this
platform can offer that a coordinate generator cannot, so it is the collection's
centre of gravity rather than a third of it: 50 % `poi`, 25 % `hybrid`, 25 %
`parametric`. Which city serves which size is decided *before* generation from
each city's measured amenity capacity, so a POI instance is never quietly
completed with sampled road points — see [POI sourcing](#poi-sourcing-which-amenities-count).

Selection is **measured, not assumed**. For each size a pool of candidates is
enumerated that differ in demand regime, capacity tightness, depot placement and
clustering; each is described by features computed from its coordinates and
demands alone; the published set maximizes the minimum distance between
instances in that standardized feature space, under coverage quotas on every
axis the size assignment left free. The full rationale, the descriptor formulas,
and the reproduction commands are in `docs/mamut2026-design.md`, in the
`MAMUT-routing-generation` workbench kept alongside the MAMUT-routing repository.

## Naming

Base name: `mamut-<city>-n<N>-<method>`, e.g. `mamut-tallinn-n1000-poi`.
`<method>` is `poi` (customers are real OSM amenities), `par` (synthetic points
sampled on the road graph) or `hyb` (a mix). The metric is not in the name — it
is the path, because the three variants are the same instance.

Since the design allows at most one instance per city — and, independently, one
instance per size — the base name is unique without a seed suffix.

`<method>` is the **realized** sourcing, never the requested one. A `poi` file's
customers are all real amenities; if a request could not be served from amenities
alone it would be named `hyb`, and this collection fails generation rather than
publishing one.

## Layout

```text
mamut-collection.json                 collection marker (family, layout version)
sidecars/<city>/n=<N>/<base>/
    <base>.geo.json.gz                WGS84 nodes, reference frame, road cache for plotting (complete node-pair cache for n <= 100)
    <base>.road.json.gz               trimmed road graph: edges with length and free-flow speed limit, vertex coordinates
    <base>.distances-fastest.json.gz  free-flow fastest travel-time matrix (seconds)
    <base>.distances-shortest.json.gz shortest-path distance matrix (meters)
CVRP/<metric>/<city>/n=<N>/<base>/    metric in {euclidean, shortest, fastest}
    <base>.vrp.json                   canonical instance (arc costs by sidecar reference, or by the euclidean rule)
    <base>.vrp                        CVRPLIB explicit-matrix export, written for n <= 200 only
    <base>.bks.MonoCost.json          best-known solution, when one exists
```

Instances reference their shared sidecars by collection-root-relative path with
a pinned sha256; the marker file makes the root discoverable by walking up from
any instance. A standalone clone of this directory is self-contained.

## Conventions

Identical to Poryos2026, deliberately, so results on the two families are
directly comparable:

The collection is **330 instances — 110 bases × 3 metrics** — in two tiers:

| tier | bases | `n` | sourcing |
|---|---:|---|---|
| main | 100 | 100 → 1000, one distinct value per instance | 50 `poi` / 25 `hybrid` / 25 `parametric` |
| poi | 10 | 1200 → 4000 | `poi` throughout |

Committed weight is **296 MB across 1 175 files**: the 330 `.vrp.json` instances,
90 CVRPLIB `.vrp` exports (the 30 bases at n ≤ 200), and 440 sidecars — one
geometry and one road sidecar per base, plus a distance matrix for `shortest` and
`fastest` (`euclidean` needs none; it is computed from the coordinates). Every
sidecar is recorded in its instance by sha256.

The POI tier's 20 distance matrices are **not** committed. They are 563 MB —
nearly twice the rest of the collection put together — so they ship as sha256
pins and are rebuilt locally with `materialize`, the pattern `Blauth2024` already
uses here. Materialized in full the collection is 860 MB; as published it is
296 MB. `materialize` re-derives all 20 from the committed road graphs and checks
each against its pin, so the reproducibility is verified rather than asserted.

- **Arc costs are 3-decimal floats** — seconds for travel times, meters for
  distances. Solvers that require integers can scale by 1000: 3-decimal values
  are exact in binary64, so the scaling is lossless. Demands and capacities are
  integers.
- **Capacity policy.** Every published base needs **at least six vehicles**, and
  the guarantee is structural rather than a filter: a route-size band is offered
  to a ladder rung only if its whole range fits in `[3, n/6]`, so the bound holds
  for every draw inside the band and not just the lucky ones. Publication
  re-checks it.

  Six rather than two. "Not a TSP" is too weak a bar — an instance with two
  routes has essentially nothing to decide about assignment, and the first draft
  of this collection shipped 34 bases below six routes and 19 whose best known
  solution used exactly two. CVRPLIB gets this for free by pairing each
  route-size vocabulary with a size range; the bands here span both XML100's and
  XL's, so the pairing has to be made explicit.

  Route size is still a design axis in its own right rather than a function of
  `n`: within what admissibility allows it is assigned evenly and independently,
  and the published set sits at `corr(log n, band) = -0.00`.
- **Fleet.** `num_vehicles` is deliberately **unset**. Following the CVRPLIB X
  and XL sets, the `k` in a base name — `mamut-lyon-n1000-k24-poi` — is the
  minimum number of vehicles the demands can be packed into, published as a
  *lower bound* on a solution's route count and **not** as a cap. A solution may
  use more routes; `metadata.num_vehicles_lb` repeats the value.

  It is the exact bin-packing optimum for **90 of the 110 bases**, where a
  lower bound and a constructed packing meet with no search. For the other 20 the
  published value is the best *proven* bound — flagged by
  `metadata.num_vehicles_lb_proven: false`, with a median shortfall of one
  vehicle and 23 at the worst (`mamut-bordeaux-n756-k250-hyb`, where the true
  minimum lies in [250, 273]). It is never an overclaim: a solution can always
  use at least as many routes as the name says. Closing the remaining twenty
  needs a branch-and-price bin-packing solver rather than more search — a 20×
  larger node budget closes none of them.
- **Objective**: `MonoCost` (total arc cost). BKS files are named
  `<instance>.bks.MonoCost.json` and are replaced only by a strictly better
  validated solution.
- **BKS coverage is complete**: all 330 instances carry a validated `MonoCost`
  solution from a first-pass campaign (PyVRP/HGS, 120 s per instance, seed 42).
  Every one is feasible and visits every customer exactly once. These are
  reference solutions, not optimality certificates, and the first pass was
  deliberately short — `save_bks_if_improved` re-validates the stored solution
  and only ever replaces it with a strictly better one, so longer runs can only
  improve them.

  A first result from the experiment the family exists for: **solving on true
  road distances costs 36 % more than solving the same customers under the
  Euclidean metric** (median cost ratio `shortest`/`euclidean` = 1.358 over the
  110 bases, range 1.094–2.072), while the fleet does not move at all — median
  35 routes under all three metrics. The penalty is in distance, not vehicles.

  Every solution uses at least as many routes as its name's `k`, which is what
  that number claims. Route counts run 7 to 510, and **no solution concentrates
  more than 24 % of its customers in a single route** — the measure that
  separates a fleet problem from a disguised TSP.
- **Every solution is drawn on real streets.** Each BKS under `shortest` and
  `fastest` carries a route geometry built from the `n + K` arcs it actually
  traverses — 220 geometries, 139 474 arcs, a median of 387 arcs and 602 KB per
  solution. 0.294 % of arcs fall back to a straight line where the trimmed road
  sidecar cannot reconstruct the polyline; those are recorded explicitly in the
  payload as `straight_fallback_paths`, so the fallback is countable rather than
  invisible.

  `euclidean` instances deliberately have no such geometry: their cost model
  *is* the straight line, and tracing them along streets would misrepresent the
  instance.

## Design axes and coverage

| Axis | Levels |
|---|---|
| City | one instance per city, over the fetched extracts |
| `n` | a **ladder**: 100 distinct sizes rising geometrically from 100 to 1000, one per instance |
| Demand distribution | 7 (unit; 1–10; 5–10; 1–100; 50–100; spatially correlated; bimodal small/bulky) |
| Average route size band | 7 (3–5, 5–8, 8–12, 12–16, 16–25, 25–50, 50–200), each offered only where it leaves ≥ 6 routes |
| Depot placement | `random`, `center`, `corner` |
| Customer placement | `random`, `clustered`, `random_clustered` |
| Customer sourcing | `poi_categories` 50 %, `hybrid` 25 %, `parametric_attach` 25 % |
| City road distortion | `low` / `mid` / `high` terciles, measured per city before generation |

### Achieved coverage

100 base instances over 100 distinct cities and 100 distinct sizes, chosen from
a pool of 600 evaluated candidates (6 per size). Every quota minimum is met and
no ceiling is exceeded. The POI tier adds 10 more, selected from 204 candidates.

**Every base needs at least 7 vehicles.** Fleet sizes run 7 to 508 with a median
of 34; customers per route run 3.0 to 153.8 with a median of 11.5.

| Axis | Achieved |
|---|---|
| `n` | 100 distinct values, 100 → 1000, one instance each |
| Customer sourcing | **poi 50, hybrid 25, parametric 25** — exact, by design |
| Demand distribution | 1:12  2:10  3:10  4:14  5:10  6:22  7:22 |
| Average route size band | **1:16  2:17  3:17  4:17  5:16  6:17  7:0** — exact, by design |
| Depot placement | center 36, corner 28, random 36 |
| Customer placement | clustered 35, random 26, random_clustered 39 |
| City distortion stratum | low 32, mid 34, high 34 |

Sourcing, size and route-size band are *exact* because they are assigned before
selection, not drawn. The rest are floors met rather than targets hit — and now
carry a ceiling as well as a floor, because a floor alone does not constrain a
max-min selector: once every minimum is met it spends the remainder wherever
feature space is emptiest, which is at its edges. Demand types 6 and 7 sit
exactly on that ceiling.

Band 7 (50–200 customers per route) is absent from this tier by construction: it
is admissible only from n = 1200 and the main tier stops at 1000. It appears
twice in the POI tier, where the same route length is a genuine 12-vehicle
problem rather than a two-route one.

All 50 `poi` instances are **100 % amenity-sourced** — not a single customer in
any of them is a sampled road point.

**Descriptor spread.** The selected 100 retain 93–100 % of the candidate pool's
range on every selection feature:

| Feature | min | median | max |
|---|---:|---:|---:|
| `clark_evans_r` | 0.192 | 0.656 | 1.052 |
| `nnd_cv` | 0.640 | 1.409 | 3.858 |
| `radial_dispersion` | 0.275 | 0.707 | 1.136 |
| `depot_centrality` | 0.014 | 1.251 | 12.184 |
| `depot_eccentricity` | 0.000 | 0.730 | 1.000 |
| `demand_cv` | 0.000 | 0.544 | 1.912 |
| `demand_gini` | 0.000 | 0.314 | 0.648 |
| `demand_max_over_mean` | 1.000 | 1.901 | 13.440 |
| `demand_moran_i` | −0.060 | 0.001 | 0.677 |
| `route_size` | **3.0** | **11.5** | **48.1** |
| `capacity_slack` | 0.000 | 0.015 | 0.126 |

**Known confound.** The three demand-spread descriptors are mutually correlated
across the published set — `demand_cv`/`demand_gini` at +0.93 and
`demand_cv`/`demand_max_over_mean` at +0.91. All three measure the same thing, so
this is expected rather than a defect, but the set cannot separate their effects:
**treat them as one axis**, not three. No other pair exceeds |r| = 0.72, and the
next strongest is `depot_centrality`/`depot_eccentricity`, which are also
definitionally related.

This confound is wider than the previous draft's, where only the first pair
exceeded 0.9. It follows from assigning route-size bands per rung: the shorter
routes that admissibility now requires narrow which demand distributions survive
selection. It was checked against the alternative explanation — re-selecting from
the same candidate pool with the feature scaling reverted still gives +0.89, so
it comes from the pool, not from how the selector weighs it.

Instance size is deliberately *not* correlated with city size: the size-to-city
assignment is checked for it, and the published set sits at r = −0.07 between
log `n` and log city road-graph size. Without that check a best-fit assignment
reaches −0.40, which would entangle the study's covariate with the cities it is
measured over.

### Why the set stops at n = 1000

A large tier was scoped but is not published. The obstacle is not compute time —
measured end to end on a small city, an n = 5000 instance builds in about four
minutes — it is bytes. Its `distances-*` sidecars are 201 MB, so a handful of
such instances would outweigh the entire 290 MB collection, and gzip blobs are
stored whole in git and do not delta-compress across regenerations. Generating
one also writes ~2 GB of intermediate files that the published artifacts do not
need.

Instances above n = 1000 additionally lose the CVRPLIB `.vrp` export, which is
capped at n = 200.

They do **not** lose street-level map rendering. The geo sidecar's node-pair road
cache is capped at n = 100, but that cache is not what the website draws routes
from — it is an all-pairs fallback, and all-pairs is the wrong shape for the job.
A solution visits each customer once, so its route geometry needs only the
`n + K` arcs the routes actually traverse, not the `n²` arcs that exist. The
publisher builds exactly those from the BKS and the raw OSM extract
(`route_geometry.py`), keyed and invalidated by the BKS sha256. Measured on the
1 020 geometries already cached for `Poryos2026`: a median of 82 arcs and 33 KB
per solution, 262 KB at the largest, and **not one arc of the whole corpus fell
back to a straight line**. The all-pairs cache at n = 100 is 2.23 MB by
comparison — larger than the BKS geometry of an instance ten times its size.

If a large tier is added later, n = 2000 is committable in full at ~33 MB per
instance; n = 5000 would need the descriptor-plus-pinned-hash treatment that
`Blauth2024` already uses in this repository. See `docs/mamut2026-design.md` in
the `MAMUT-routing-generation` workbench for the measurements.

## Metric divergence

Each base instance carries its own measured departure from the Euclidean plane,
computed over its actual node set after generation:

- `detour_mean`, `detour_p90` — road distance ÷ straight-line distance;
- `asymmetry_shortest`, `asymmetry_fastest` — mean relative gap between the two
  directions of a node pair. Exactly zero for the euclidean variant by
  construction; positive wherever one-way streets bite. Classical Euclidean
  benchmarks have no analogue of this;
- `rank_tau_eucl_fast`, `rank_tau_eucl_short`, `rank_tau_short_fast` — Kendall
  rank correlation between the metrics' orderings of node pairs, i.e. how often
  a Euclidean intuition about "which customer is nearer" is wrong here.

These make the experiment a dose-response question rather than a yes/no one, and
the published set spans a wide dose range:

| | min | median | max |
|---|---:|---:|---:|
| `detour_mean` | 1.152 | 1.317 | 1.810 |
| `detour_p90` | 1.271 | 1.527 | 2.626 |
| `asymmetry_shortest` | 0.008 | 0.050 | 0.114 |
| `asymmetry_fastest` | 0.012 | 0.066 | 0.146 |
| `rank_tau_eucl_short` | 0.733 | 0.914 | 0.954 |
| `rank_tau_eucl_fast` | 0.571 | 0.822 | 0.921 |
| `rank_tau_short_fast` | 0.737 | 0.873 | 0.962 |

At one end of the τ range a Euclidean guess about which customer is nearer is
right most of the time; at the other (`mamut-bastia-n486-k22-par`, τ = 0.571,
detour 1.81) it is barely better than a coin flip on a third of the pairs. Up to 15 % of an arc's cost depends on the
direction of travel — a quantity that is identically zero, by construction, in
every classical Euclidean benchmark.

## POI sourcing: which amenities count

Half the instances draw **every** customer from a real OSM amenity, snapped to
the nearest routable point within 50 m. Which amenities is the point, and it is
not all of them.

OSM tags a great deal as `amenity` that no vehicle ever delivers to. Measured on
these extracts:

| city | amenities in the extract | `bench` + `waste_basket` + `recycling` |
|---|---:|---:|
| Lyon | 32 949 | **69.9 %** |
| Quimper | 1 091 | **41.5 %** |

Adding `parking`, `drinking_water`, `toilets`, `atm`, `charging_station`,
`bicycle_rental`, `taxi` and `shelter` takes Lyon to roughly **78 %**. Sampling
from that pool produces instances whose customers are park benches and litter
bins, which makes "the customers are real places on a real map" a claim rather
than a fact.

The collection therefore draws from a curated **35 of the platform's 49**
categories — premises a vehicle serves:

| group | categories |
|---|---|
| food and drink | `restaurant` `cafe` `bar` `fast_food` `pub` `biergarten` `ice_cream` `food_court` `nightclub` |
| health | `pharmacy` `hospital` `clinic` `doctors` `dentist` `veterinary` |
| education | `school` `university` `college` `kindergarten` |
| civic | `post_office` `police` `fire_station` `townhall` `courthouse` `library` |
| culture | `theatre` `cinema` `arts_centre` `community_centre` `museum` `place_of_worship` |
| commerce and vehicle services | `bank` `marketplace` `fuel` `car_wash` |

Excluded: `bench` `waste_basket` `recycling` `drinking_water` `toilets` `shower`
`shelter` (street furniture) and `parking` `atm` `charging_station`
`bicycle_rental` `taxi` `bus_station` `ferry_terminal` (real objects, but not
premises with a delivery address — an `amenity=parking` node is usually one
individual space, not a car park).

Binding is `nearest_vertex` rather than the generator's default
`nearest_node`, which demands that a POI's closest road *node* be a graph vertex
in its own right and so discards most of a city's amenities.

### Size follows the amenities, not the other way round

A POI instance of `n` customers needs `n + 1` **distinct road vertices reachable
from curated amenities** — two cafés on one corner collapse into a single
customer, and an amenity beyond the 50 m radius is not a customer at all. That
ceiling is measured per city before generation, and each rung of the size ladder
is then given to a city that can demonstrably supply it, with a factor-of-4
headroom so the selection stays a sample rather than the whole pool — and so
that instance size does not become a proxy for city size (see *Achieved
coverage*).

A rung no city can supply is reported, not quietly downgraded. This matters
because the generator's own fallback is silent: a POI request the amenities
cannot fill is completed with sampled road points and relabelled `hybrid`, which
reaches `n` and so passes every other check. Nothing in this collection is
labelled `poi` unless all of its customers are amenities.

## Loading

The reference loader is
[mamut-routing-lib](https://github.com/ANR-MAMUT/MAMUT-routing-lib):

```python
from pathlib import Path
from mamut_routing_lib.artifacts import (
    discover_benchmark_instances, load_benchmark_instance, resolve_arc_costs,
)

items = discover_benchmark_instances(Path("path/to/benchmarks"), benchmark_names=["Mamut2026"])
instance = load_benchmark_instance(items[0].instance_path)
matrix = resolve_arc_costs(instance, items[0].instance_path)   # sha256-verified
```

## Reproduction

Generation is `scripts/generate_mamut2026.py` in the `MAMUT-routing-generation`
workbench kept alongside the MAMUT-routing repository, built on
`mamut_routing_tools.campaign`. It is deliberately not part of this repository:
regenerating the collection is not something a consumer of it needs to do. The whole campaign is reproducible from
one `--base-seed`; every phase writes a JSON artifact recording exactly what it
decided.

## License

OSM-derived artifacts are distributed under
[ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/), with attribution to
OpenStreetMap and its contributors. See [LICENSE](LICENSE) and the repository
[NOTICE](../../NOTICE).
