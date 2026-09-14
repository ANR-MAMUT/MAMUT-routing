# 5. Export to CVRPLIB `.vrp`

Solvers that read the classic TSPLIB-derived CVRPLIB text instead of `.vrp.json` get a byte-identical export from
the CLI, the workbench and the website.

```bash
uv run mamut-routing export vrp benchmarks/VRPTW/Sintef2008/n=25/C101.vrp.json          # writes C101.vrp next to it
uv run mamut-routing --benchmarks-dir benchmarks export vrp \
    --problem-type VRPTW --benchmark-name Sintef2008 --output-dir ./vrp-out             # a whole family, mirrored
```

Defaults and options:

- `EDGE_WEIGHT_TYPE : EXPLICIT` with the full matrix, so the solver sees exactly the published costs; VRPTW files
  use `TYPE : CVRPTW` with time-window and service-time sections (the dialect VRPLIB and PyVRP read).
- `--edge-weight-type EUC_2D` (euclidean-metric instances only) drops the matrix; readers then compute
  `nint(hypot)`, which is **not** the published cost, so BKS values do not transfer. `--format solomon` writes the
  Solomon `.txt` dialect for VRPTW instead of `.vrp`.
- Time-dependent instances have no static matrix and are refused.

The full contract is on the [CVRPLIB export](../benchmarks/formats/cvrplib-export.md) page. On the website, the
`.vrp ↓` chip of any static instance does the same in the browser.

That is the end of the tutorials. Continue with the [User guide](../user-guide/index.md) to generate your own
instances with `mamut-tools`, or with the [Benchmarks](../benchmarks/index.md) section for the formats.
