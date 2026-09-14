# Layouts, naming and pins

## Two trees

**Classic (problem-type first).** Historic families and the in-repo defaults:

```
benchmarks/<ProblemType>/<Family>/n=<N>/
    <base>.vrp.json                       the instance
    <base>.bks.<ObjectiveFunction>.json   one BKS per objective
    <base>.atf.json[.gz]                  TD families: the arrival-time functions (or an IGP sidecar)
    <base>.vrp                            optional committed CVRPLIB copy (n <= 200 CVRP only)
```

Sidecar references inside an instance are relative to the instance file.

**Family-first collection.** Generated collections (Poryos2026, Mamut2026) hold every problem-type layer of the same
base instances plus their shared sidecars, rooted by a marker:

```
benchmarks/<Family>/
    mamut-collection.json                 {"format": "mamut-collection", "format_version": 1, "family": "<Family>", "layout_version": 1}
    CVRP/<metric>/n=<N>/<base>.vrp.json   euclidean | shortest | fastest
    VRPTW/<tw-set>/...  TDVRP/...  TDVRPTW/...
    sidecars/{geo,road,distances,traffic,...}/
```

Sidecar references inside a collection instance are **relative to the collection root**
(`mamut_routing_lib.sidecars.find_collection_root` walks up to the marker). Discovery (`discover_benchmark_instances`)
parses either layout (`parse_layout`, `parse_collection_layout`) and yields `DiscoveredBenchmarkInstance` records
(problem type, family, metric variant, place, size, subset, time-window set, instance id and name, path).

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
