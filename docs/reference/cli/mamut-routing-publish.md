# `mamut-routing-publish` (MAMUT-routing)

The publishing toolkit of the MAMUT-routing repository itself: site payloads and static HTML shell, the
build-time caches (ATF sidecars, BKS route geometry), precompression, this documentation, release archives,
and the static file server. It runs from a checkout of the repository:

```bash
git submodule update --init --recursive MAMUT-routing-lib MAMUT-routing-tools
uv sync
uv run mamut-routing-publish --help
```

The reference below is generated from the Typer application at build time.

::: mkdocs-click
    :module: mamut_routing_publish._docs_cli
    :command: mamut_routing_publish
    :prog_name: mamut-routing-publish
    :depth: 1
    :style: table
    :list_subcommands: True
