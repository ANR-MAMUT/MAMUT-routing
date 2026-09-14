# 2. Install the Python stack

Three packages, three roles. Install what you need.

=== "Use the benchmarks (lib)"

    ```bash
    pip install "mamut-routing-lib[cli]"          # models, checkers, BKS logic, remote archives, export + CLI
    pip install "mamut-routing-lib[cli,pyvrp]"    # + the PyVRP solver wrapper
    mamut-routing --version
    ```

    With uv: `uv add "mamut-routing-lib[cli]"` in a project, or `uv tool install "mamut-routing-lib[cli]"` for the
    CLI alone.

=== "Generate and solve locally (tools)"

    ```bash
    uvx --from mamut-routing-tools mamut-tools --help     # no install: uv runs it in an ephemeral environment
    pip install mamut-routing-tools                       # or install it
    pip install "mamut-routing-tools[kayros]"             # + KAYROS for time-dependent instances
    ```

=== "Develop or maintain (checkout)"

    ```bash
    git clone git@github.com:ANR-MAMUT/MAMUT-routing.git && cd MAMUT-routing
    git submodule update --init --recursive MAMUT-routing-lib MAMUT-routing-tools   # recursive: the nested lib is the one uv installs
    uv sync                                                                          # publisher + lib + tools, editable, with the docs toolchain
    uv run mamut-routing --version && uv run mamut-tools --version && uv run mamut-routing-publish --version
    uv run pytest
    ```

    The tutorials that follow assume this checkout (`uv run ...`); with a pip install, drop the `uv run` prefix and
    point `--benchmarks-dir` at your data.

Environment variables you may want: `MAMUT_ROUTING_BENCHMARKS_ROOT` (default `--benchmarks-dir` of the CLI and
default root of the library), `MAMUT_TOOLS_WORKSPACE` (where the tools keep OSM extracts, instances and jobs). Full
list in the [reference](../reference/environment-variables.md). Next:
[Load an instance and check a solution](load-and-check.md).
