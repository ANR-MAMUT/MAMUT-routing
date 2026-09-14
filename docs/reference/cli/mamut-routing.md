# `mamut-routing` (mamut-routing-lib)

The command-line interface of [mamut-routing-lib](https://github.com/ANR-MAMUT/MAMUT-routing-lib): list local
benchmark instances, download and verify release archives, solve with PyVRP and propose best-known solutions,
and export static instances to the classic CVRPLIB `.vrp` format. Install it with the `cli` extra:

```bash
pip install "mamut-routing-lib[cli]"      # or: uv add "mamut-routing-lib[cli]"
mamut-routing --help
```

The reference below is generated from the Typer application at build time.

::: mkdocs-click
    :module: mamut_routing_publish._docs_cli
    :command: mamut_routing
    :prog_name: mamut-routing
    :depth: 1
    :style: table
    :list_subcommands: True
