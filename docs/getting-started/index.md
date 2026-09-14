# Getting started

Three ways in, by increasing involvement. Each step is self-contained.

## 1. Browse and download

The [website](/) lists every published instance with its best-known solution (BKS), a route map, the
objective contract and the publication history. Every static instance page offers a `.vrp ↓` chip that writes the
classic CVRPLIB file in your browser.

For batches, the `mamut-routing` CLI pulls per-family release archives, so you download only what you need:

```bash
pip install "mamut-routing-lib[cli]"            # or: uv add "mamut-routing-lib[cli]"

mamut-routing remote list                                       # archives of the latest release
mamut-routing --benchmarks-dir ./benchmarks remote fetch \
    --problem-type CVRP --benchmark-name Poryos2026            # download + extract one family
mamut-routing --benchmarks-dir ./benchmarks remote verify        # sha256 against the manifest
mamut-routing --benchmarks-dir ./benchmarks list --problem-type CVRP
```

To pin the whole tree to a commit (for a paper or an experiment), add the repository as a submodule instead and
initialise the families you need:

```bash
git submodule add https://github.com/ANR-MAMUT/MAMUT-routing.git external/MAMUT-routing
git -C external/MAMUT-routing submodule update --init benchmarks/Mamut2026
```

A plain clone leaves the satellite directories empty; the default families (Sintef2008, Dimacs2021, Ortec2022,
Dabia2013) are in the repository itself. See [Benchmark families](../benchmarks/families/index.md) for sizes.

## 2. Load, check, solve, export

`mamut-routing-lib` is the contract: pydantic models for instances, solutions, BKS and sidecars, plus the
checkers that define what a valid solution costs.

```python
from pathlib import Path
from mamut_routing_lib import (
    discover_benchmark_instances, load_benchmark_instance, load_bks, check_solution,
)

items = discover_benchmark_instances(benchmarks_root=Path("./benchmarks"))
instance = load_benchmark_instance(items[0].instance_path)
bks = load_bks(items[0].bks_path)
report = check_solution(instance, bks)          # status, validated cost, route count
```

Time-dependent instances (TDVRP, TDVRPTW) use the exact, epsilon-free checker in `mamut_routing_lib.td`.
The full surface is in the [API reference](../reference/api/index.md).

Solving and proposing a BKS uses the PyVRP wrapper (`pyvrp` extra). A BKS file is only ever replaced by a
strictly better, re-validated solution:

```bash
pip install "mamut-routing-lib[cli,pyvrp]"
mamut-routing --benchmarks-dir ./benchmarks solve \
    --problem-type CVRP --benchmark-name Mamut2026 --time-limit-s 120 --seed 42 --save-bks
```

Solvers that do not read `.vrp.json` get the classic format:

```bash
mamut-routing export vrp path/to/instance.vrp.json          # writes <name>.vrp next to it
mamut-routing --benchmarks-dir ./benchmarks export vrp \
    --problem-type CVRP --benchmark-name Mamut2026 --output-dir ./vrp-out
```

The export is byte-identical across the CLI, the workbench and the website; the contract is documented in
[Formats](../benchmarks/formats/index.md).

## 3. Generate your own instances

Generation and solving run on your machine with `MAMUT-routing-tools` (the website is static by design, see the
[FAQ](../user-guide/faq.md)):

```bash
uvx --from mamut-routing-tools mamut-tools --help
uvx --from mamut-routing-tools mamut-tools osm fetch-city "Vannes, France" --output-dir ./work
uvx --from mamut-routing-tools mamut-tools generate single ./work/osmdata/vannes.osm --n 100 --output-dir ./work
uvx --from mamut-routing-tools mamut-tools gui start        # the local workbench, in your browser
```

The [User guide](../user-guide/index.md) walks through the workbench, the generation commands and the OSM
download profiles; the [CLI reference](../reference/cli/mamut-tools.md) lists every option.

## For maintainers and contributors

Clone with the tooling submodules, sync the uv workspace, run the tests, build the site:

```bash
git clone git@github.com:ANR-MAMUT/MAMUT-routing.git && cd MAMUT-routing
git submodule update --init MAMUT-routing-lib MAMUT-routing-tools
uv sync
uv run pytest
uv run mamut-routing-publish site build --skip-atf-cache --skip-route-geometry
uv run mamut-routing-publish serve            # http://127.0.0.1:8082/ and /docs/
```

Continue with the [Maintainer guide](../maintainer-guide/index.md) or the
[Developer guide](../developer-guide/index.md).
