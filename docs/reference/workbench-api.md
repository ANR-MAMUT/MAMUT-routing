# Workbench HTTP API

The local workbench (`mamut-tools gui start`) is a loopback FastAPI server owned by the CLI: it binds `127.0.0.1`,
checks the `Host` header, and every request must carry the per-session token that `gui start` prints in the URL. It
is not a public API and has no stability promise; this table exists so scripts and the frontend agree on what exists.
Handlers live in `mamut_routing_tools.gui.server`; job persistence in `gui.jobs`, solution runs in `gui.solutions`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | the workbench page |
| GET | `/static/{asset_path}` | bundled frontend assets |
| GET | `/healthz` | liveness |
| GET | `/api/workbench/generation/cities` | cities with a usable OSM extract in the workspace |
| GET | `/api/workbench/generation/pois` | POI categories and counts for a city |
| POST | `/api/workbench/generation/fetch-osm-city` | start an OSM fetch job (Nominatim + tiled Overpass) |
| GET | `/api/workbench/osmdata/audit` | audit extracts for missing way/relation POIs |
| POST | `/api/workbench/generation/preflight` | validate a single-instance request without generating |
| POST | `/api/workbench/generation/single` | generate one CVRP base (job) |
| POST | `/api/workbench/generation/single-download` | download the artifacts of a single generation |
| POST | `/api/workbench/generation/bulk-preflight` | validate a bulk row table |
| POST | `/api/workbench/generation/bulk` | bulk generation job over a row table |
| POST | `/api/workbench/generation/bulk-download` | download bulk artifacts |
| POST | `/api/workbench/generation/td-build` | derive the TDVRP/TDVRPTW twins (job) |
| GET | `/api/workbench/instances` | instances known to the workspace |
| GET | `/instances-file` | serve an instance file from the workspace |
| POST | `/api/workbench/instances/{instance_id}/export-vrp` | CVRPLIB `.vrp` export of a workspace instance |
| POST | `/api/workbench/solve` | solve an instance (PyVRP, or KAYROS for TD) as a job |
| POST | `/api/workbench/render-routes` | road-following route geometry for a solution |
| GET | `/api/instances/{instance_id}/solutions` | checker-validated solution runs of an instance |
| GET | `/api/instances/{instance_id}/map-data` | map payload (nodes, geo, cached roads) |
| POST | `/api/instances/{instance_id}/solutions/compare` | compare runs: objective, fleet, loads, route edges, customer grouping |
| POST | `/api/instances/{instance_id}/solutions/{run_id}/render` | render one run on the road network |
| POST | `/api/instances/{instance_id}/solutions/import` | import an external solution as a validated run |
| POST | `/api/jobs` | create a job |
| GET | `/api/jobs` | list jobs |
| GET | `/api/jobs/{job_id}` | job state |
| GET | `/api/jobs/{job_id}/log` | append-only job log |
| DELETE | `/api/jobs/{job_id}` | cooperative cancellation |
| GET, PUT | `/api/preferences` | per-workspace UI preferences |

Jobs are durable records under `<workspace>/state/jobs/` with logs under `state/logs/`; solution runs live under
`solutions/<instance-id>/` and survive restarts. Environment: `MAMUT_TOOLS_WORKSPACE`, `MAMUT_BASEMAP_API_KEY`, and the
internal `MAMUT_GUI_WORKSPACE` / `MAMUT_GUI_TOKEN` set by `gui start`.
