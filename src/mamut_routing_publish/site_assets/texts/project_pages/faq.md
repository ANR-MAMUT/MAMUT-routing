# FAQ

This page collects short answers to common questions about contributing benchmark material and comparing MAMUT-routing conventions with other VRPTW sources.

## How to download and manipulate instances and BKS

The benchmark instances and their best-known solutions (BKS) can be retrieved in two complementary ways. Pick whichever fits your workflow best.

### Option A — Install `mamut-routing-lib` and use its CLI

Recommended for selective downloads, programmatic access, and scripting. The library is published on PyPI and ships an optional `mamut-routing` CLI backed by per-family release archives, so you only pull what you need (typically a few MB to a few hundred MB per family rather than the whole tree).

Install with pip or the [`uv`](https://github.com/astral-sh/uv) package manager. The `[cli]` extra adds the `mamut-routing` command-line interface:

```bash
pip install "mamut-routing-lib[cli]"
# or
uv add "mamut-routing-lib[cli]"
```

List, download, and verify benchmark archives from the published [GitHub release](https://github.com/ANR-MAMUT/MAMUT-routing/releases) feed:

```bash
# Get help on the CLI
mamut-routing --help
mamut-routing remote --help
mamut-routing <command> --help

# List archives available in the latest release directly from GitHub (requires network)
mamut-routing remote list

# Filter by problem-type and benchmark family
mamut-routing remote list --problem-type CVRP --benchmark-name Mamut2026

# Download and extract one or more archives into ./benchmarks
mamut-routing --benchmarks-dir ./benchmarks remote \
    fetch --problem-type CVRP --benchmark-name Mamut2026

# Verify local zip checksums against the remote manifest
mamut-routing --benchmarks-dir ./benchmarks remote verify
```

Once instances are on disk, list and load them locally:

```bash
# List local instances under ./benchmarks
mamut-routing --benchmarks-dir ./benchmarks list \
    --problem-type CVRP --benchmark-name Mamut2026

# Print only matching paths (useful for piping into other tools)
mamut-routing --benchmarks-dir ./benchmarks list \
    --problem-type CVRP --paths-only
```

From Python, the same instances can be discovered and loaded directly:

```python
from pathlib import Path
from mamut_routing_lib import discover_benchmark_instances, load_benchmark_instance

items = discover_benchmark_instances(benchmarks_root=Path("./benchmarks"))
instance = load_benchmark_instance("benchmarks/.../mamut-n100-9517368.vrp.json")
```

A `[pyvrp]` extra wires up the [PyVRP](https://github.com/PyVRP/PyVRP) HGS metaheuristic so the same CLI can also solve loaded instances. See the [MAMUT-routing-lib README](https://github.com/ANR-MAMUT/MAMUT-routing-lib) for the full reference.

### Option B — Add MAMUT-routing as a git submodule

Recommended when you want the **entire** benchmark tree available offline and pinned to a specific commit, for example to reference a frozen snapshot from a paper or experiment.

```bash
git submodule add https://github.com/ANR-MAMUT/MAMUT-routing.git external/MAMUT-routing
git submodule update --init --recursive
```

Heads-up: the full checkout is on the order of several gigabytes, dominated by VRPTW road-geometry sidecar files (`*.meta.json`). If you only need a single problem family or a subset of metric variants, `mamut-routing-lib`'s `remote fetch` command above will be much lighter.

## Contributions

`MAMUT-routing`, including its tooling, website, instance collection, and BKS collection, is open-source. Modifications, new benchmark instances, new problem classes, new objective functions, and other contributions are welcome.

Use the [GitHub repository](https://github.com/ANR-MAMUT/MAMUT-routing) to discuss or request changes, propose your help, fix issues, or upload new BKS files directly.

## CVRPLib, SINTEF, and DIMACS BKS

[CVRPLib](https://galgos.inf.puc-rio.br/cvrplib/en/instances) also lists Solomon and Gehring-Homberger VRPTW instances with BKS. However, the listed BKS appear to be computed on a `MonoCost` objective over floating-point Euclidean arc costs.

That differs from the historic [SINTEF](https://www.sintef.no/en/) [VRPTW benchmark](https://www.sintef.no/projectweb/top/vrptw/), which uses a hierarchical objective: first minimize the number of vehicles, then minimize travel cost.

It also differs from the newer [DIMACS](http://dimacs.rutgers.edu/) [VRPTW benchmark](http://dimacs.rutgers.edu/index.php/programs/challenge/vrp/vrptw/), which uses the same mono-cost objective but on scaled integerized arc costs. This integerization changes the optimization landscape, so BKS values and routes are only comparable when the complete benchmark contract matches.
