# MAMUT-routing documentation

MAMUT-routing is a curated collection of vehicle-routing benchmarks (CVRP, VRPTW, TDVRP, TDVRPTW) with
checker-validated best-known solutions, a fully static [website](/) that browses and visualises them, and a
Python stack to load, check, solve, generate and publish them. It is part of the
[ANR MAMUT project](https://anr.fr/Project-ANR-22-CE22-0016).

This documentation follows the [Diátaxis](https://diataxis.fr/) split: tutorials to learn, guides to get a
task done, reference to look things up, and explanation where the *why* matters.

<div class="grid cards" markdown>

-   :material-download:{ .lg .middle } **I want to use the benchmarks**

    ---

    Download instances and best-known solutions, read the formats, check a solution, export to CVRPLIB `.vrp`,
    cite the data.

    [:octicons-arrow-right-24: Getting started](getting-started/index.md) ·
    [:octicons-arrow-right-24: Benchmarks](benchmarks/index.md)

-   :material-wrench:{ .lg .middle } **I maintain the platform**

    ---

    Update a family or a BKS, add a family or a problem type, run generation and BKS campaigns, build and
    deploy the website, cut a release.

    [:octicons-arrow-right-24: Maintainer guide](maintainer-guide/index.md)

-   :material-source-branch:{ .lg .middle } **I contribute code**

    ---

    Architecture of the four repositories, development setup, tests, conventions and the
    generated API reference.

    [:octicons-arrow-right-24: Developer guide](developer-guide/index.md) ·
    [:octicons-arrow-right-24: Reference](reference/index.md)

-   :material-map-search:{ .lg .middle } **I want to browse first**

    ---

    The website's catalog, instance pages with route maps, objectives, publication history and the upload
    workbench.

    [:octicons-arrow-right-24: Open the website](/)

</div>

## The pieces

| Repository | Role | Install |
|---|---|---|
| [MAMUT-routing](https://github.com/ANR-MAMUT/MAMUT-routing) | The benchmark tree (families as submodules), the website publisher `mamut-routing-publish`, this documentation | checkout + `uv sync` |
| [MAMUT-routing-lib](https://github.com/ANR-MAMUT/MAMUT-routing-lib) | The data contract: models, checkers, BKS logic, remote archives, CVRPLIB export, `mamut-routing` CLI | `pip install "mamut-routing-lib[cli]"` |
| [MAMUT-routing-tools](https://github.com/ANR-MAMUT/MAMUT-routing-tools) | Local generation and solving: OSM fetch, road graphs, instance generation, converters, workbench GUI, `mamut-tools` CLI | `uvx --from mamut-routing-tools mamut-tools` |
| Benchmark satellites | One repository per large family or collection (`MAMUT-routing-TDVRPTW-Rifki2020`, `MAMUT-routing-Poryos2026`, ...) | `git submodule update --init benchmarks/<...>` |

## Where things are

- **Benchmark families**, one page each, with their repository README: [Families](benchmarks/families/index.md).
- **Formats and the checker contract**: [Formats](benchmarks/formats/index.md) and the
  [Python API reference](reference/api/index.md).
- **Every command-line option**: [CLI reference](reference/cli/mamut-routing.md).
- **Why things are the way they are**: the [FAQ](user-guide/faq.md) and the [Developer guide](developer-guide/index.md).
