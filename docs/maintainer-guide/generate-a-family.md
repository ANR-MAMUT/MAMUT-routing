# Generate or convert a family

Generation lives in `MAMUT-routing-tools`, deliberately as a **library**: the CLI is per-instance
(`generate single` → `derive-vrptw` → `derive-td`), and a family is a per-campaign script calling the library so the
campaign's decisions are code under version control.

## The Poryos2026 pipeline (`mamut_routing_tools.family`)

Per base instance (city × n × sampling method), three stages, each recorded in every artifact's `generator` block:

1. **`build_base`** (stage `generate-base`): full-city road graph, trimmed to the union of pinned free-flow
   fastest-path edges, both distance matrices, the indexed geo road cache; publishes the three slim CVRP metric
   instances (`euclidean`, `shortest`, `fastest`) plus the `geo`, `road` and `distances-*` sidecars into the collection.
2. **`derive_vrptw`** (stage `derive-vrptw`): name-seeded service times and time windows over the published fastest
   matrix; three TW sets (`td-shared`, the one the TD twins share; `tight` and `spread`, static only).
3. **`build_td`** (stage `build-td`): aligns the six traffic overlays (`bpr` and `wave` models × three intensities),
   materializes canonical ATFs, certifies anchor routes under every overlay, applies minimal shared deadline lifts,
   emits the twelve sha-pinned TD twins. Hard gates: the published `distances-fastest` equals the road graph's
   free-flow times after rounding, and the post-lift audit holds for every overlay.

Naming and tree layout are in `family/naming.py`; `family.materialize_distances` rebuilds pinned matrices;
`generation.bulk.generate_bulk_instances` / `preflight_rows` drive many bases from a row table.

```bash
# the per-instance CLI, for one base
mamut-tools osm fetch-city Lyon --country France --profile generation --osm-dir work/osmdata   # -> work/osmdata/Lyon.osm
mamut-tools generate single Lyon --osm-path work/osmdata/Lyon.osm --n 200 --output-dir work --vrptw
mamut-tools generate derive-td <folder> <base> --all      # folder and base name as printed by `generate single`
```

## The Mamut2026 design layer (`mamut_routing_tools.campaign`)

Before generating, decide *which* instances make a set worth reporting on:

1. `city_profile`: measure each city's road-network distortion from the Euclidean plane and stratify.
2. `poi_capacity`: measure how many POI-only customers a city can supply (the 35 curated amenity categories).
3. `ladder`: the size ladder (geometric n from 100 to 1000, one per rung) and rung → city → method assignment.
4. `design`: enumerate a balanced candidate pool and evaluate cheaply (selection and demands, no matrices).
5. `select`: max-min spread over the descriptor space under the coverage quotas of `quotas.py`.

Then `generation.single` / `family.build_base` produce the artifacts. Record the plan files (profiles, capacities,
ladder) with the campaign script; the collection README documents the achieved coverage.

## Converting an external distribution

`conversion/blauth2024.py` is the template: a pure relabeling (no numeric transformation, so the canonical bytes and
`atf_sha256` pins are identical on any machine), the family contract spelled out in the module docstring (time unit,
horizon, depot window, service, capacity, fleet, objective and its constants), per-instance assertions for every
assumption, and a pointer to the design note. The command is `mamut-tools convert blauth2024 <upstream-checkout>
<output>`. Older TD conversions (Ari2018, Vu2020, Rifki2020, Lera2026) predate the tools and are documented in their
satellite READMEs.

## Memory and time

Distance matrices are computed in Dijkstra chunks of 256 sources; a 5000-source run over a 100k-vertex graph is
several GB of float64. City extracts run to ~150 MB of XML and are parsed incrementally. Large Overpass downloads
are tiled with a persistent tile cache so an interrupted fetch resumes. Parallelism is per city
(`ProcessPoolExecutor`) in the campaign steps.

After generating: validate every instance and BKS with the lib, run the [BKS campaign](bks-campaigns.md), then
[add the family](add-a-family.md).
