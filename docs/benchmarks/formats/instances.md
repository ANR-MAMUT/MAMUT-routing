# Static instances (CVRP, VRPTW)

Models in `mamut_routing_lib.models`. Two shapes exist.

## Embedded instances

`BenchmarkInstanceCVRP` and `BenchmarkInstance` (VRPTW) carry the full arc-cost matrix:

| Field | Type | Notes |
|---|---|---|
| `instance_name`, `instance_origin`, `benchmark_name` | str, `InstanceOrigin`, `BenchmarkName` | identity |
| `num_customers`, `num_vehicles`, `vehicle_capacity` | int, int or null, int | `num_vehicles: null` = unlimited fleet |
| `coordinates` | list of `[x, y]` | index 0 is the depot unless `depot` says otherwise |
| `demands` | list of int | depot demand 0 |
| `depot` | int, default 0 | |
| `arc_costs` | `(n+1) × (n+1)` matrix | int or float; Sintef2008 floats, Dimacs2021/Ortec2022 integers |
| `reference_lla` | `{lat, lon, alt}` or null | geodetic origin of the local frame |
| VRPTW only: `service_times`, `time_windows` | list of int, list of `[ready, due]` | |
| `metadata` | `InstanceMetadata` or dict | see below |

## Slim collection instances

`BenchmarkInstanceCVRPCollection` and `BenchmarkInstanceVRPTWCollection` replace the matrix by an `arc_costs_source`:

- `{"model": "euclidean", "decimals": 3}`: costs are Euclidean distances rounded to `decimals`;
- `{"model": "distances-sidecar", "distances": {"path": ..., "sha256": ...}}`: costs come from the pinned
  [distances sidecar](sidecars.md).

They also carry `metric_variant`. `hydrate_collection_instance` resolves the source into an embedded instance for
the checker and the solvers; `.vrp` export does the same.

## Metadata

`InstanceMetadata` (generated families) records authorship, generation time, problem type and metric variant,
place slug, source base name, city, seed and folder, `num_vehicles_lb`, the generator version and the submodule
commit, `artifact_paths` (vrp_json, vrp, meta, manifest), sibling and derived problem paths, and the data `license`
with its URL. Historic families use a free-form dict. Generated artifacts also carry a `generator` block per stage
(see [Generate a family](../../maintainer-guide/generate-a-family.md)).

## Validation

Models reject extra keys, inconsistent lengths (coordinates, demands, service times, windows versus
`num_customers + 1`), a square matrix of the wrong size, negative demands, windows with `ready > due`. Loading is
`load_benchmark_instance(path)`; the problem type of a loaded object is `instance_problem_type(instance)`.
