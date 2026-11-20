# 6. Tour the tools: from a city to a solved instance

One pass over the `mamut-tools` command groups and the `mamut-routing` commands around them: browse the published
data, solve a classic instance, download a city, generate an instance on its road network, solve it under three
metrics and under traffic, export it, and open it in the workbench GUI. Count about ten minutes; the only network
step is the city download. The figures quoted below come from a run on 2026-10-22: OpenStreetMap changes every day,
so the city figures on your machine will differ slightly.

## Set up a workspace

```bash
export MAMUT_TOOLS_WORKSPACE=~/mamut-tutorial   # OSM extracts, instances, solver runs and GUI state live here
uv run mamut-tools --version
uv run mamut-tools --help       # osm, roadgraph, generate, solve, geometry, convert, bks-campaign, gui
uv run mamut-routing --help     # list, solve, check, export, remote, bks, solvers
```

Every level of the command tree answers `--help` (`uv run mamut-tools generate --help`,
`uv run mamut-tools generate single --help`). Run the commands from the root of the checkout of
[step 2](install.md): `mamut-routing` scans `./benchmarks` by default.

Keep the variable set for the whole tutorial. `gui status` and `gui stop` look for the server in the workspace, so a
server started in another workspace is reported as not running.

## Browse the published benchmarks

```bash
uv run mamut-routing remote list                                       # release archives of the latest snapshot
uv run mamut-routing list | sed -n '/^Summary/,/Metric variants/p'    # what is checked out locally
uv run mamut-routing list --problem-type VRPTW --benchmark-name sintef2008 | tail -4
```

`remote list` reads the release manifest on GitHub: one zip per family, with its size and sha256
([step 1](browse-and-download.md) downloads them). The local summary counts only what is checked out; each satellite
submodule you initialize adds its family.

## Solve a classic instance

```bash
uv run mamut-tools solve benchmarks/VRPTW/Sintef2008/n=100/C101.vrp.json \
    --objective HierarchicalVehicleCost --time-limit 10 | jq -c '{cost, n_routes, validation}'
jq -c '{cost, n_routes: (.routes|length)}' \
    benchmarks/VRPTW/Sintef2008/n=100/C101.bks.HierarchicalVehicleCost.json
```

PyVRP finds the published BKS of Solomon's C101 within the 10 s: cost 828.94 with 10 routes, `valid` for the
checker. `cost` is always the checker's price of the routes, not the solver's own figure. Like
`mamut-routing solve` ([step 4](solve-and-bks.md)), `mamut-tools solve` writes nothing unless you pass
`--update-bks`, with `--authors` to say who is credited.

## Download a city and build its road graph

```bash
uv run mamut-tools osm fetch-city Vannes --country France --osm-dir $MAMUT_TOOLS_WORKSPACE/osmdata
uv run mamut-tools osm validate $MAMUT_TOOLS_WORKSPACE/osmdata/Vannes.osm
uv run mamut-tools roadgraph info $MAMUT_TOOLS_WORKSPACE/osmdata/Vannes.osm \
    | jq '{vertices, edges, total_edge_length_km}'
```

`fetch-city` geocodes the name with Nominatim and downloads the drivable roads and the candidate customer amenities
from Overpass: 7 MB for Vannes, one to three minutes depending on the Overpass server's load. Tiles are cached, so an interrupted download resumes. It writes
to `./osmdata` unless told otherwise, hence `--osm-dir`: generation looks for `<workspace>/osmdata/<City>.osm`. For a
large city, clamp the administrative area with `--max-radius-km`. `roadgraph info` builds the graph the generator
routes on: 13,183 intersections and 27,176 road segments, 1,436 km in all.

## Generate an instance

```bash
uv run mamut-tools generate preview Vannes --n 30 --seed 1 \
    | jq -r '.features[].properties | select(.role=="customer") | .poi_category' | sort | uniq -c
uv run mamut-tools generate single Vannes --n 30 --seed 1 --vrptw | jq '{action, base_name, folder}'
uv run mamut-tools generate single Vannes --n 30 --seed 1 --vrptw | jq .action
ls $MAMUT_TOOLS_WORKSPACE/instances/osm/vannes/n31
```

- `preview` returns the selection as GeoJSON and writes nothing: 30 customers drawn from the restaurants, schools,
  cafés, bars and fast-food places of the extract.
- `single` writes the instance `vannes_poi-n31-k3` under the three arc-cost metrics, with its metadata and manifest;
  `--vrptw` adds the time-window twin. In the name, `n31` counts the depot and `k3` is a lower bound on the number of
  routes, as in CVRPLIB's `X-n101-k25`.
- The second, identical call prints `"unchanged"`: same content, nothing rewritten. A different configuration that
  yields the same name is saved as `vannes_poi-n31-k3-2`; `--replace` replaces the instance and deletes what was
  derived from it (twins, BKS).

`--method` chooses between map amenities (`poi_categories`), synthetic points attached to the road network
(`parametric_attach`) and a mix of both (`hybrid`); `--depot-mode`, `--customer-mode`, `--demand-type` and
`--avg-route-size` shape the rest. The time-window twin is written as `vannes_poi-n31-k3_fastest.cvrptw.vrp` only, and
`mamut-tools solve` reads `.vrp.json`: that is why the VRPTW solve above uses a published instance.

## Same customers, three metrics

```bash
D=$MAMUT_TOOLS_WORKSPACE/instances/osm/vannes/n31
for m in euclidean shortest fastest; do
  uv run mamut-tools solve $D/vannes_poi-n31-k3_$m.vrp.json --time-limit 5 | jq -c "{metric: \"$m\", cost, n_routes}"
done
uv run mamut-tools solve $D/vannes_poi-n31-k3_fastest.vrp.json --time-limit 5 \
    --update-bks --authors "Your Name (handle)" | jq -c .bks_update
```

The three files share customers, demands and capacity; only the arc costs change: straight-line distance, shortest
road distance, fastest travel time. Their costs (19,577, 32,504 and 3,127) are therefore not comparable with each
other; how the solutions themselves change with the metric is the question the Mamut2026 collection is built for (see
[Benchmarks](../benchmarks/index.md)). `--update-bks` stores the solution next to the instance
(`"action": "created"`); run it again and the store answers `kept_existing` with `"tie": true`.

## Add traffic: the time-dependent twins

```bash
uv run mamut-tools generate derive-td $D vannes_poi-n31-k3 \
    | jq '{action, twins: [.combos[] | .tdvrptw_twin, .tdvrp_twin]}'
uv run --with 'kayros>=1.1.2' mamut-tools solve $D/vannes_poi-n31-k3-bpr-moderate.vrp.json \
    --solver kayros --time-limit 10 | jq '{cost, n_routes, status}'
```

`derive-td` simulates a traffic overlay on the road graph (by default the `bpr` commuter model at `moderate`
intensity), turns it into arrival-time functions, and lifts the time windows so they stay feasible under traffic. It
writes the TDVRPTW and TDVRP twins with their sha256-pinned sidecars, or nothing at all when the windows cannot be
certified. `--all` derives the six model × intensity combinations. [KAYROS](https://pypi.org/project/kayros/) solves
the Duration objective of time-dependent instances; it is an optional extra, so `uv run --with` adds it for this one
command (`pip install "mamut-routing-tools[kayros]"` installs it for good).

## Export to CVRPLIB `.vrp`

```bash
uv run mamut-routing export vrp $D/vannes_poi-n31-k3_fastest.vrp.json --output-dir $MAMUT_TOOLS_WORKSPACE/export
head -8 $MAMUT_TOOLS_WORKSPACE/export/vannes_poi-n31-k3_fastest.vrp
```

Generated instances follow the same contract as the published ones, so [step 5](export-vrp.md) applies unchanged.

## Open the workbench GUI

```bash
uv run mamut-tools gui start     # prints a tokened URL and opens it in the browser
uv run mamut-tools gui status    # prints the URL again if you lose the tab
uv run mamut-tools gui stop
```

The GUI reads the same workspace, so `vannes_poi-n31-k3` is already in its instance list: select it to see the depot
and customers on the map, solve it, draw the road-following routes, and press **Animate** to play the vehicles. Every
step above is also a button there (city fetch, preview, generation, solving, run comparison). Over SSH, add
`--no-open` and forward the printed port.

Three command groups were left out because they serve the maintainers: `geometry materialize-plan` computes the
road-following BKS routes of the website build, `convert blauth2024` rebuilds the Blauth2024 family from its
upstream distribution, and `bks-campaign` runs several solvers over many instances to improve the stored BKS
([BKS campaigns](../maintainer-guide/bks-campaigns.md)). Whole families are generated by campaign scripts on top of
the `mamut_routing_tools.family` library ([Generate or convert a family](../maintainer-guide/generate-a-family.md)).
The [User guide](../user-guide/index.md) lists every generation command and option.
