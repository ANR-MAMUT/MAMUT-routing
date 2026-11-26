# 2. Install the Python stack

For edition `r1` of `mamut-routing/0.1`, use the development checkout below. It pins library 0.13.0.dev0 and tools 0.7.0.dev0. For the problem-first September 2026 snapshot, use the released library 0.12.0 in a separate environment. [Read the historical snapshot](browse-and-download.md#read-the-september-2026-snapshot)

=== "Released library on PyPI"

    ```bash
    pip install "mamut-routing-lib[cli]"          # models, checkers, BKS logic, remote archives, export + CLI
    pip install "mamut-routing-lib[cli,pyvrp]"    # + the PyVRP solver wrapper
    mamut-routing --version
    ```

    With uv: `uv add "mamut-routing-lib[cli]"` in a project, or `uv tool install "mamut-routing-lib[cli]"` for the
    CLI alone.

=== "Released tools on PyPI"

    ```bash
    uvx --from mamut-routing-tools mamut-tools --help     # no install: uv runs it in an ephemeral environment
    pip install mamut-routing-tools                       # or install it
    ```

    For Kayros 2.0 before the joint PyPI release, use the matching CPython development wheels listed in the [tools installation guide](../developer-guide/packages/mamut-routing-tools.md#optional-kayros-solver), or build from the checkout below. After the joint release, install `mamut-routing-tools[kayros]` with pip.

    Kayros 1.7.1 requires mamut-routing-lib below 0.12. Use a separate historical environment for that solver alongside the v0.13 tools.

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
