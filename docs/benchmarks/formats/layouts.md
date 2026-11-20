# Layouts, naming and pins

## The 2 layout versions

Every family is a **collection** at `benchmarks/<Family>/`, rooted by a marker. The marker's `layout_version` says how the paths below the root are shaped:

```
benchmarks/<Family>/
    mamut-collection.json                 {"format": "mamut-collection", "format_version": 1, "family": "<Family>", "layout_version": 1 | 2}
    README.md, LICENSE, CHANGELOG.md, CITATION.cff    one set for all the problem types of the family
    sidecars/                             sidecars shared by the problem-type trees, when the family has any
```

**Layout 2 (classic families).** Sintef2008, Dimacs2021, Ortec2022, Dabia2013, Ari2018, Vu2020, Rifki2020, Lera2026 and Blauth2024:

```
benchmarks/<Family>/<ProblemType>/[<subset>/]n=<N>/
    <base>.vrp.json                       the instance
    <base>.bks.<ObjectiveFunction>.json   one BKS per objective
benchmarks/<Family>/sidecars/n=<N>/
    <base>.atf.json[.gz]                  TD families: the arrival-time functions (or an IGP sidecar), shared by the TDVRPTW and TDVRP twins
```

The optional `<subset>` directory sits between the problem type and the size (`final` and `public` for Ortec2022, `S1` to `S3` for Lera2026).

**Layout 1 (generated collections).** Poryos2026 and Mamut2026 hold every problem-type layer of the same base instances plus their shared sidecars:

```
benchmarks/<Family>/
    CVRP/<metric>/<city>/n=<N>/<base>/<base>.vrp.json                   euclidean | shortest | fastest
    CVRP/<metric>/<city>/n=<N>/<base>/<base>.vrp                        optional committed CVRPLIB copy (n <= 200 CVRP only)
    VRPTW/<metric>/<city>/n=<N>/<base>/<base>[-tw-<set>].vrp.json
    TDVRP/<city>/n=<N>/<base>/<subinstance>/<base>-<subinstance>.vrp.json   (TDVRPTW alike)
    sidecars/{geo,road,distances,traffic,...}/
```

Sidecar references inside an instance are **relative to the collection root**, in both layouts (`mamut_routing_lib.sidecars.find_collection_root` walks up to the marker). Discovery (`discover_benchmark_instances`) parses every path with `parse_collection_layout` under the layout version of its marker, refuses a file outside any collection, and yields `DiscoveredBenchmarkInstance` records (problem type, family, metric variant, place, size, subset, time-window set, instance id and name, path). The problem-type-first layout (`benchmarks/<ProblemType>/<Family>/...`) was read up to mamut-routing-lib 0.12.

## Names

- Instance files: `<base>.vrp.json`; the base name is the instance identity across problem-type layers
  (`poryos-<city>-n<N>-<method>`, `mamut-<city>-n<N>-k<K>-<method>` where `k` is a lower bound on the route count,
  as in CVRPLIB's `X-n101-k25`).
- BKS files: `<base>.bks.<ObjectiveFunction>.json`, built by `get_bks_path_for_instance`.
- TD twins: `<base>.<subinstance>` for the traffic overlays (`traffic-<model>-<intensity>`).
- Metric variants: `fastest` (free-flow travel time), `shortest` (path length), `euclidean`.

## Pins

A sidecar reference is a `SidecarRef` with exactly two fields: `path` and an optional `sha256` (no other key is
accepted). The hash covers the uncompressed canonical JSON bytes; when it is present the loader recomputes it and
refuses a mismatch. Consequences:

- a sidecar can be stored as `.json` or `.json.gz` interchangeably;
- large sidecars may be **pinned but not committed** (the POI-tier distance matrices of Mamut2026); the generator
  rebuilds them bit-identically (`mamut-tools generate materialize-distances`);
- editing a sidecar by hand invalidates every instance that pins it.

Time-dependent instances additionally record `atf_sha256`, the pin of the canonical ATF set, whether the ATFs are
shipped or materialized on load.
