# MAMUT-routing

Curated CVRP and VRPTW benchmarks, the static benchmark website, and the Julia webapp that visualizes instances and routes — all in one repository.

## MAMUT project context

This repository is part of the
[MAMUT project](https://github.com/ANR-MAMUT) ([ANR-22-CE22-0016](https://anr.fr/Project-ANR-22-CE22-0016)),
an academic research project advancing the state of the art in combinatorial optimization for logistics and transportation problems.

## Layout

| Path | Purpose |
|---|---|
| `benchmarks/` | Curated CVRP and VRPTW benchmark instances + BKS, served as the canonical browsable copy. |
| `osmdata/` | OpenStreetMap-derived data feeding the Mamut2026 generated benchmarks. |
| `webapp/` | Julia webapp (Genie) serving the static site and the route-payload API. |
| `dist/` *(generated, gitignored)* | Static HTML shell + payload JSON files produced by the Python publisher. |
| `dist-release/` *(generated, gitignored)* | Release `.zip` archives + `snapshot-manifest.json` produced by the Python publisher. |
| `src/mamut_routing_publish/` | Python publishing toolkit (this repo's own package). |
| `MAMUT-routing-lib/` *(submodule)* | Contract/runtime Python library — see [ANR-MAMUT/MAMUT-routing-lib](https://github.com/ANR-MAMUT/MAMUT-routing-lib). |
| `tests/` | Pytest suite for `mamut_routing_publish`. |

## Python publishing toolkit (`mamut-routing-publish`)

The Python package `mamut_routing_publish` owns site payload generation, static HTML shell generation, and release `.zip` archive generation. It depends on [`mamut-routing-lib`](https://github.com/ANR-MAMUT/MAMUT-routing-lib) for the benchmark data contract.

### Setup

#### Python
```bash
# clone with the nested mamut-routing-lib submodule
git clone --recurse-submodules git@github.com:ANR-MAMUT/MAMUT-routing.git
cd MAMUT-routing

# install (uses the local editable submodule for mamut-routing-lib)
uv sync
```

#### Julia

From the repo root, run:
```bash
julia --project=webapp -e 'using Pkg; Pkg.instantiate(); Pkg.precompile()'
```

This installs and precompiles the Julia dependencies declared in `webapp/Project.toml` and `webapp/Manifest.toml`.


### CLI

```bash
uv run mamut-routing-publish --help

# Build the site (payloads + static HTML shell) into ./dist/
uv run mamut-routing-publish site build

# Quiet build for scripts that do not want progress on stderr
uv run mamut-routing-publish site build --quiet

# Machine-readable progress events on stderr + generated file lists in stdout summary
uv run mamut-routing-publish site build --progress-format json --list-files

# Payloads only
uv run mamut-routing-publish site payloads

# Static HTML shell only (assumes payloads already exist)
uv run mamut-routing-publish site webapp

# Build release archives + manifest into ./dist-release/
uv run mamut-routing-publish release build
```

By default, the CLI resolves the MAMUT-routing repo root from the current working directory, or from the `MAMUT_ROUTING_ROOT` environment variable (shared with `mamut-routing-lib`). Override via `--output-repo-dir` / `--source-repo-dir`. `site build` reports progress and a final human-readable duration/file/memory summary to stderr by default, then keeps the machine-readable JSON summary on stdout. Instance payload resolution runs in parallel by default with `--jobs auto`, defined as `max(1, os.cpu_count() - 2)` and capped by the number of discovered instances. Use `--jobs 1` for serial resolution.

### Tests

```bash
uv run pytest
```

## Julia webapp

See [`webapp/README.md`](webapp/README.md) for the site API server and
geometry-cache filling instructions.

To run Julia webapp locally:
```bash
julia -t auto --project=webapp webapp/run_site_api.jl --repo-root "$(pwd)"
```

This command starts the server, serving the static site and the route-payload API from the local `dist/` directory. 

## License

The source code is licensed under the [MIT License](LICENSE).

This repository also contains benchmark data and generated artifacts under
family-specific terms. In particular, `Ortec2022` material is under
`CC BY-NC 4.0`, and OSM-derived `Mamut2026` artifacts are under `ODbL 1.0`
where applicable. See [NOTICE](NOTICE) and the `README.md`/`LICENSE` files in
each benchmark family directory.
