# Formats

Every artifact is JSON validated by a pydantic model with `extra="forbid"`; the normative description of each
format is the docstring of the module that owns it. This page is the map.

| Artifact | File | Format tag / version | Owner module |
|---|---|---|---|
| Static instance (CVRP, VRPTW) | `<name>.vrp.json` | — | [`mamut_routing_lib.models`](../../reference/api/lib/models.md) (`BenchmarkInstanceCVRP`, `BenchmarkInstance`, slim collection variants, `ArcCostsEuclidean` / `ArcCostsDistancesRef`) |
| Time-dependent instance | `<name>.vrp.json` | `mamut-td-atf` v1, `mamut-td-igp-categories` v1, `mamut-road-graph` v2, `mamut-traffic-overlay` v1 | [`mamut_routing_lib.td.models`](../../reference/api/lib/td/models.md) |
| Solution and BKS | `<base>.bks.<Objective>.json` | — | [`mamut_routing_lib.models`](../../reference/api/lib/models.md) (`BenchmarkSolution`, `BenchmarkBKS`, `OptimalityMetadata`), [`bks`](../../reference/api/lib/bks.md), [`td.bks`](../../reference/api/lib/td/bks.md) |
| Collection marker | `mamut-collection.json` | `mamut-collection` v1 | [`mamut_routing_lib.sidecars`](../../reference/api/lib/sidecars.md) |
| Distances sidecar | `sidecars/distances/...` | `mamut-distances` v1 | [`mamut_routing_lib.distances`](../../reference/api/lib/distances.md) |
| Geo sidecar (informative only) | `sidecars/geo/...` | `mamut-geo` v3 | [`mamut_routing_lib.geo`](../../reference/api/lib/geo.md) |
| Arrival-time functions | `<instance>.atf.json[.gz]` | `mamut-td-atf` v1 | [`mamut_routing_lib.td.artifacts`](../../reference/api/lib/td/artifacts.md) |
| IGP profiles (Lera2026) | in-instance | `mamut-td-igp-categories` v1 | [`mamut_routing_lib.td.igp`](../../reference/api/lib/td/igp.md) |
| Road graph and traffic overlay | `sidecars/road/...` | `mamut-road-graph` v2, `mamut-traffic-overlay` v1 | [`mamut_routing_lib.td.roadgraph`](../../reference/api/lib/td/roadgraph.md) |
| Piecewise-linear primitive | — | — | [`mamut_routing_lib.td.pwlf`](../../reference/api/lib/td/pwlf.md) (`NDCPWLF`) |
| CVRPLIB `.vrp` / Solomon `.txt` export | `<name>.vrp` | `EDGE_WEIGHT_TYPE: EXPLICIT` by default | [`mamut_routing_lib.cvrplib`](../../reference/api/lib/cvrplib.md); decision record: [CVRPLIB `.vrp` export contract](../../reports/2026-09-02-cvrplib-vrp-export-contract.md) |
| Release archives | `<Type>-<Family>-snapshot-<id>.zip` + `snapshot-manifest.json` | manifest models in [`mamut_routing_lib.remote`](../../reference/api/lib/remote.md) | `mamut-routing-publish release build` |
| Route geometry cache (website) | `dist/route-geometry-cache/<sha>.route-geometry.json.gz` | content-addressed by BKS sha256 | `mamut_routing_publish.route_geometry`, produced by `mamut-tools geometry materialize-plan` |

Common rules:

- **Sha256 pins.** Instances reference sidecars by path *and* sha256 of the uncompressed canonical JSON; gzip
  sidecars are written with `mtime=0` so bytes are reproducible.
- **Costs.** Generated collections use 3-decimal float arc costs (scaled ×1000 to integers for PyVRP, lossless);
  Dimacs2021 and Ortec2022 are integers; Sintef2008 is full-precision float. Blauth2024 counts time in integer
  milliseconds.
- **The checker's cost is the BKS cost.** `create_bks_from_solution` stores the validated cost, never the solver's.
- **Optimality is a claim with a certificate.** `metadata.optimality` (`proven: true`, `prover`, `certificate`,
  `date`, optional bounds and campaign fields) is validated like any other field.
