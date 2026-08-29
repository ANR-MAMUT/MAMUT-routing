# Changelog — Mamut2026

All notable changes to the Mamut2026 collection are recorded here. The family
follows the MAMUT-routing benchmark-as-contract rules: an instance's numerical
content never changes silently, and a BKS is replaced only by a strictly better
validated solution.

## [Unreleased]

### Added

- The collection itself: 110 CVRP base instances generated from OpenStreetMap
  city road networks — 330 instances in all — each materialized under the three
  arc-cost metrics (`euclidean`, `shortest`, `fastest`) over identical customers,
  demands and vehicle capacity. A main tier of 100 sweeps `n` from 100 to 1000
  over 100 distinct cities; a POI tier of 10 runs from 1200 to 4000 customers,
  every one wholly amenity-sourced, with its distance matrices shipped as sha256
  pins rather than bytes (439 MB rebuilt locally by `materialize`).
- A designed rather than gridded instance set: one instance per city, with
  configurations chosen by a max-min criterion over measured instance
  descriptors under coverage quotas on every design axis, including the cities'
  own road-network distortion. See
  `docs/mamut2026-design.md`, in the `MAMUT-routing-generation` workbench kept
  alongside this repository.
- A **size ladder** in place of a size grid: 100 distinct values of `n` rising
  geometrically from 100 to 1000, one per instance, so instance size is a
  covariate that can be regressed against rather than an eight-level factor.
- **Curated POI categories.** Customers labelled `poi` are drawn from 35 amenity
  categories that are premises a vehicle serves, not from all 49 the platform
  knows. Street furniture is excluded: measured on these extracts, `bench`,
  `waste_basket` and `recycling` alone are 69.9 % of Lyon's amenities and 41.5 %
  of Quimper's, and `amenity=parking` usually marks an individual parking space
  rather than a car park.
- **Capacity-driven size assignment.** Each rung of the ladder is matched to a
  city whose measured curated-amenity capacity can supply it, with a factor-of-4
  headroom. A rung no city can supply is reported rather than downgraded — the
  generator's own fallback silently tops a short POI request up with sampled road
  points and relabels it `hybrid`, which reaches `n` and passes every other check.
  The headroom is 4 rather than the 1.25 that merely keeps the draw
  non-degenerate: matching is best-fit, so a tight bar lands every rung on a city
  that *just* clears it and makes instance size a proxy for city size. Measured
  on this pool, correlation between `log n` and `log`&nbsp;city&nbsp;capacity is
  −0.40 at ×1.25 and −0.07 at ×4.
- CVRPLIB `.vrp` exports up to `n = 200` (was 100). With one distinct `n` per
  instance, the old cutoff would have left a single instance in the family
  readable by a CVRPLIB-only solver.
- The geo sidecar's all-pairs road cache stays capped at `n = 100`, deliberately.
  Street-level route rendering does not come from it: the publisher builds route
  geometry from each BKS, resolving only the `n + K` arcs a solution actually
  traverses against the raw OSM extract. That is `n` work where the all-pairs
  cache is `n²` — measured across the 1 020 geometries cached for `Poryos2026`,
  a median of 82 arcs and 33 KB per solution with zero straight-line fallbacks.
  Every instance in this collection therefore renders on real streets once it has
  a solution, regardless of size.
- Per-instance metric-divergence figures (detour ratio, direction asymmetry,
  and Kendall rank correlation between each pair of metrics), published in the
  campaign's diversity report.

### Changed

- **Every instance now requires at least six vehicles.** The v2 draft of this
  collection was regenerated because a third of it was not a set of vehicle
  routing problems. Measured against the new floor, **34 of its 110 bases needed
  fewer than six routes**; 22 needed three or fewer, 19 had best known solutions
  using exactly two, and five of those had a second route holding a single
  customer — solutions of shape `[99, 1]`, `[125, 1]`, `[147, 1]`. Three things
  combined to produce them.

  *An XL-scale route-size band drawn at main-tier sizes.* The generator offers
  seven average-route-size bands. Bands 1–6 (3 to 50 customers per route) are
  CVRPLIB's XML100 vocabulary; band 7 (50–200) comes from the XL set, which
  introduced it alongside `n ≥ 1000` because delivery operators really do run
  routes that long. This collection drew it at any size. A 50–200 customer route
  target is an ordinary instance at n = 4000 and a two-route degenerate at
  n = 272. Split by band, the v2 set is unambiguous: of the 42 bases in bands 1–5
  none were degenerate; of the 58 in bands 6–7, 22 were.

  *A capacity clamp that manufactured the second route.* The capacity formula
  ended by clamping to `total demand − 1`, meant as a guarantee of "at least two
  routes". When the route-size target is large it is instead the binding
  constraint, and what it guarantees is a TSP with a second route carrying the
  overflow. The clamp is not in the CVRPLIB generator this code ports.

  *A selector that was paid to sit on the edge of the axis.* Realized route size
  is a selection feature and selection maximises spread. On a linear scale the
  step from 50 to 200 customers per route is worth eleven times the step from 3
  to 16, so the longest band took 39 of 100 places against a quota floor of 7.

  The fix is in the design, not in a filter. A route-size band is admissible at a
  rung only if its whole range fits in `[3, n/6]`, and the band is now *assigned*
  per rung alongside `n` and the sourcing method rather than drawn and repaired
  afterwards. Band 7 is consequently unreachable below n = 1200, which
  independently reproduces XL's own convention. Ratio-valued selection features
  are z-scored in logs, and the published set's route-size bands come out even —
  16/17/17/17/16/17 across bands 1–6 — with `corr(log n, band) = −0.00`.

- **`k` in an instance name is now the exact bin-packing minimum.** Names read
  `mamut-lyon-n1000-k24-poi`, following CVRPLIB's `X-n101-k25`. As there, it is a
  **lower bound** on a solution's route count and not a fleet cap: `num_vehicles`
  stays unset and a solution may use more routes. The previous value,
  `ceil(sum(q) / Q)`, is only the continuous relaxation and understates the fleet
  when the demands do not divide the capacity — `mamut-metz-n135-poi` published
  33 where the true minimum is at least 37. Computed exactly for 104 of 110
  bases by matching lower and upper bounds with no search; the remainder record
  `kmin_proven: false` and publish the proven bound, which is never an overclaim.
  `Poryos2026` names are unaffected.

- **A POI request now yields `n` POI customers even when the depot sits on an
  amenity.** The selector returned `n` vertices and the caller then discarded any
  equal to the depot vertex, leaving `n − 1` to be topped up parametrically — so
  an instance asking for 1000 amenity customers could be published as `hybrid`
  while its diagnostics reported "100 % amenities" (999/1000, rounded). The
  excluded vertex is now seeded into the selector instead of filtered afterwards,
  so the walk simply moves on to the next amenity. This changes generated output
  for any POI instance whose depot collided with an amenity, `Poryos2026`
  included: published bytes are untouched, but regenerating an affected instance
  from its descriptor will not reproduce them.

### Notes

- `Mamut2026` was previously the name of the family now published as
  `Poryos2026`; that rename happened in mamut-routing-lib 0.8.0 and the retired
  name was carried as a read-time alias in the publisher. The alias has been
  removed and pre-rename publication state migrated on disk
  (`scripts/migrate_legacy_mamut2026_state.py`, now in the
  `MAMUT-routing-generation` workbench), so the name is free and this
  collection is unrelated to the retired one. No artifact is shared between them.
- Best-known solutions are produced by a separate solving campaign. The first
  pass covered all 330 instances (PyVRP/HGS, `MonoCost`, 120 s each, seed 42);
  every solution is feasible and validated. They are reference solutions, not
  optimality certificates, and are expected to improve under longer runs.

  Every solution uses at least as many routes as its instance name claims, which
  is the check that the published `k` is a sound lower bound. Route counts run 7
  to 510 with a median of 35, and **no solution puts more than 24 % of its
  customers in one route** — against the previous draft, where 19 bases had a
  single route holding over half of them and one held 99.3 %.

  Median cost ratio `shortest`/`euclidean` is 1.358 (range 1.094–2.072): road
  distance costs about 36 % more than the Euclidean idealisation of the same
  customers, while the fleet is unchanged at a median of 35 routes under all
  three metrics.
- The OSM extracts behind the collection were audited before generation
  (`mamut-tools osm refresh-pois --check`). A third of them held only
  node-mapped amenities, missing the roughly one third of a real city's
  amenities that are drawn as building outlines, and a few held almost none at
  all. Extracts are repaired where a size rung actually depends on them; the
  design document records which and why.
