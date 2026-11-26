# 2. Install the Python stack

Library 0.13.0 reads edition `r1` of `mamut-routing/0.1`. The September 2026 problem-first snapshot uses library 0.12.0 in a separate environment. [Read the historical snapshot](browse-and-download.md#read-the-september-2026-snapshot)

=== "Edition r1 library"

    ```bash
    python -m pip install 'mamut-routing-lib[cli]==0.13.0'
    mamut-routing --version
    ```

    Add the `pyvrp` extra for the static solver. The default Linux x86-64 wheels support CPython 3.11 through 3.14. Source builds use a C++20 compiler, Boost headers and GMP development files. [Library installation and reference-only build](../developer-guide/packages/mamut-routing-lib.md#exact-route-evaluation-on-v013)

=== "Generation tools and Kayros"

    The family-first generation and materialization commands use the tools revision pinned in the collection checkout below. PyPI tools 0.6.0 retain their original CLI, including `mamut-tools solve --time-limit`. These commands and both route checkers work without Kayros. For TD solving with Kayros 2.0, build the pinned development source as shown below or use matching development wheels. Published Kayros 1.7.1 requires `mamut-routing-lib<0.12` in a separate environment. [Tools installation with Kayros](../developer-guide/packages/mamut-routing-tools.md#optional-kayros-solver)

=== "Read edition r1 (checkout)"

    ```bash
    git clone https://github.com/ANR-MAMUT/MAMUT-routing.git
    cd MAMUT-routing
    git -c url.https://github.com/.insteadOf=git@github.com: submodule update --init --recursive MAMUT-routing-lib MAMUT-routing-tools
    git -c url.https://github.com/.insteadOf=git@github.com: submodule update --init benchmarks/Dimacs2021 benchmarks/Dabia2013
    uv sync --locked --python 3.12
    uv run mamut-routing --version
    uv run mamut-tools --version
    ```

    The native library build requires a C++20 compiler, Boost headers and GMP development files. Initialize further families with the same submodule command. The tutorials using Sintef2008 require `benchmarks/Sintef2008`. [Replay an edition result](../benchmarks/formats/edition-r1.md)

    To add Kayros to the checkout on Linux x86-64, install a C++23 compiler, Boost.Graph and the GMP development files. From the repository root, build the pinned library wheel for the interpreter that will build Kayros, then enable the tools extra in the workspace.

    ```bash
    wheelhouse=$(mktemp -d)
    uv build --python 3.12 --wheel --out-dir "$wheelhouse" MAMUT-routing-lib
    UV_FIND_LINKS="$wheelhouse" uv sync --locked --python 3.12 --all-packages --extra kayros
    .venv/bin/mamut-tools solve benchmarks/Dabia2013/TDVRPTW/n=25/C101.vrp.json --solver kayros --time-limit-s 2 --seed 1
    ```

    The tutorials that follow assume this checkout (`uv run ...`); with a pip install, drop the `uv run` prefix and
    point `--benchmarks-dir` at your data.

Environment variables you may want: `MAMUT_ROUTING_BENCHMARKS_ROOT` (default `--benchmarks-dir` of the CLI and
default root of the library), `MAMUT_TOOLS_WORKSPACE` (where the tools keep OSM extracts, instances and jobs). Full
list in the [reference](../reference/environment-variables.md). Next:
[Load an instance and check a solution](load-and-check.md).
