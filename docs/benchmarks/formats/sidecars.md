# Distances and geo sidecars

Both live under `sidecars/` of a collection, are referenced by sha256-pinned collection-relative paths, and are
hashed over their uncompressed canonical JSON bytes (gzip `mtime=0`).

## Distances (`mamut-distances` v1, `mamut_routing_lib.distances`)

One sidecar per (base, metric): the full `(n+1) × (n+1)` matrix of the `fastest` (free-flow travel times) or
`shortest` (path lengths) metric, rounded to the family's precision (3 decimals). Slim instances reference it
through `arc_costs_source.model = "distances-sidecar"`. Generation gate: the `fastest` sidecar of a base equals the
free-flow node-to-node times of its road-graph sidecar after the same rounding. Above a size threshold the bytes are
not committed, only the pin; `mamut-tools generate materialize-distances` rebuilds them.

## Geo (`mamut-geo` v3, `mamut_routing_lib.geo`)

One sidecar per base (`<base>.geo.json[.gz]`), shared by every problem-type layer: per-node geodetic (lat, lon) and
local ENU positions, the reference frame, and for `n <= 100` a complete road-path cache over all ordered node pairs for
the `fastest` and `shortest` metrics in an indexed encoding (one `vertex_lonlat` table plus per-metric maps from `"i-j"`
arc keys to index lists), about five times smaller gzipped than repeated polylines. It is static: BKS changes never
touch it (v3 retired the growing `road_cache` of the old `meta.json`).

**Purely informative**: the checker never reads it; the website and the workbench draw with it. Route polylines of
BKS for larger instances come from the website's route-geometry cache, computed by the tools' road engine and keyed by
BKS sha256.
