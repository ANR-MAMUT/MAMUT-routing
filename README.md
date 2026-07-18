# MAMUT-routing

Curated CVRP, VRPTW, TDVRPTW and TDVRP benchmarks and the fully static benchmark website that visualizes instances and routes, all in one repository. Instance generation and solving run locally with [MAMUT-routing-tools](https://github.com/ANR-MAMUT/MAMUT-routing-tools); Julia remains only for the offline time-dependent benchmark generation pipeline.

[![SWH](https://archive.softwareheritage.org/badge/origin/https://github.com/ANR-MAMUT/MAMUT-routing/)](https://archive.softwareheritage.org/browse/origin/?origin_url=https://github.com/ANR-MAMUT/MAMUT-routing)

## MAMUT project context

This repository is part of the
[MAMUT project](https://github.com/ANR-MAMUT) ([ANR-22-CE22-0016](https://anr.fr/Project-ANR-22-CE22-0016)),
an academic research project advancing the state of the art in combinatorial optimization for logistics and transportation problems.
See [AUTHORS.md](AUTHORS.md) for authorship, supervision, funding context, and contributor information.

The time-dependent benchmark families curated here (TDVRPTW/TDVRP, with arrival-time-function sidecars and checker-validated best-known solutions) are the reference data of [KAYROS](https://github.com/0nyr/kayros), the MAMUT time-dependent VRP solver built on this repository's exact Duration checker.

## Layout

| Path | Purpose |
|---|---|
| `benchmarks/` | Curated CVRP, VRPTW, TDVRPTW and TDVRP benchmark instances + BKS, served as the canonical browsable copy. |
| `benchmarks/<ProblemType>/<Family>/` *(some are submodules)* | Large non-default benchmark families are self-contained satellite repositories mounted as submodules — see below. |
| `benchmarks/Mamut2026/` *(submodule)* | The generated **Mamut2026 collection**: one family-first repository holding all four problem-type trees plus shared sidecars — see below. |
| `osmdata/` | OpenStreetMap-derived data feeding the Mamut2026 generated benchmarks. |
| `webapp/` | Julia scripts of the offline time-dependent benchmark generation pipeline (`osm_generation.jl`, `td_traffic.jl`), driven by `workbench build-family`. The legacy site server they accompany is retired. |
| `dist/` *(generated, gitignored)* | Static HTML shell + payload JSON files produced by the Python publisher. |
| `dist-release/` *(generated, gitignored)* | Release `.zip` archives + `snapshot-manifest.json` produced by the Python publisher. |
| `src/mamut_routing_publish/` | Python publishing toolkit (this repo's own package). |
| `MAMUT-routing-lib/` *(submodule)* | Contract/runtime Python library — see [ANR-MAMUT/MAMUT-routing-lib](https://github.com/ANR-MAMUT/MAMUT-routing-lib). |
| `MAMUT-routing-tools/` *(submodule)* | Local generation tool suite (road-graph engine, route geometry, OSM fetch) — see [ANR-MAMUT/MAMUT-routing-tools](https://github.com/ANR-MAMUT/MAMUT-routing-tools). `site build` uses its road engine for BKS route geometry. |
| `publish-state/` *(generated, gitignored)* | Persistent publication state: history ledger + snapshot inventories, surviving fresh release directories. |
| `tests/` | Pytest suite for `mamut_routing_publish`. |

### Benchmark family satellites

The default family of each time-dependent problem type (`Dabia2013` for TDVRPTW and TDVRP) lives directly in this repository. The other TD families are **satellite repositories** mounted as submodules at their family directory; each satellite is self-contained (instances, ATF sidecars, BKS, and a README documenting raw sources, provenance, and the consolidation pipeline recorded in every artifact's `generator` block):

| Submodule | Mounted at |
|---|---|
| [MAMUT-routing-TDVRPTW-Ari2018](https://github.com/ANR-MAMUT/MAMUT-routing-TDVRPTW-Ari2018) | `benchmarks/TDVRPTW/Ari2018` |
| [MAMUT-routing-TDVRPTW-Vu2020](https://github.com/ANR-MAMUT/MAMUT-routing-TDVRPTW-Vu2020) | `benchmarks/TDVRPTW/Vu2020` |
| [MAMUT-routing-TDVRPTW-Rifki2020](https://github.com/ANR-MAMUT/MAMUT-routing-TDVRPTW-Rifki2020) | `benchmarks/TDVRPTW/Rifki2020` |
| [MAMUT-routing-TDVRPTW-Lera2026](https://github.com/ANR-MAMUT/MAMUT-routing-TDVRPTW-Lera2026) | `benchmarks/TDVRPTW/Lera2026` |
| [MAMUT-routing-TDVRP-Ari2018](https://github.com/ANR-MAMUT/MAMUT-routing-TDVRP-Ari2018) | `benchmarks/TDVRP/Ari2018` |
| [MAMUT-routing-TDVRP-Vu2020](https://github.com/ANR-MAMUT/MAMUT-routing-TDVRP-Vu2020) | `benchmarks/TDVRP/Vu2020` |
| [MAMUT-routing-TDVRP-Rifki2020](https://github.com/ANR-MAMUT/MAMUT-routing-TDVRP-Rifki2020) | `benchmarks/TDVRP/Rifki2020` |
| [MAMUT-routing-TDVRP-Lera2026](https://github.com/ANR-MAMUT/MAMUT-routing-TDVRP-Lera2026) | `benchmarks/TDVRP/Lera2026` |

`Lera2026` is the first `igp-profile` family: it ships compact IGP specifications instead of ATF sidecars (the canonical arrival-time functions materialize deterministically on load, pinned by `atf_sha256`), which keeps its two satellites at ~50 MB despite covering 200–1000 customers.

### The Mamut2026 collection

[MAMUT-routing-Mamut2026](https://github.com/ANR-MAMUT/MAMUT-routing-Mamut2026), mounted at `benchmarks/Mamut2026/`, is the generated city family and the first **family-first collection**: instead of one satellite per problem type, a single marker-rooted repository holds the CVRP, VRPTW, TDVRP and TDVRPTW trees of the same 60 base instances (5 cities × n ∈ {10, 25, 50, 100, 500, 1000} × 2 sampling methods; 1080 instances, all with checker-validated BKS) plus their shared sha256-pinned sidecars (geo, road graph, 6 traffic overlays, distance matrices). Arc costs are 3-decimal floats family-wide, VRPTW carries three time-window sets per base of which only the bare-base-named one is shared with the TDVRPTW twins; see the collection README for the conventions and the pairing rule. The retired per-problem-type v1 Mamut2026 satellites are archived with tombstone READMEs.

A plain `git clone` leaves satellite directories empty (the tooling and the default families work without them). Fetch only the families you need:

```bash
git submodule update --init benchmarks/TDVRPTW/Rifki2020   # one TD family (0.1–0.8 GB each)
git submodule update --init benchmarks/Mamut2026           # the generated collection (~0.4 GB)
git submodule update --init                                # everything (~2.5 GB of satellite data)
```

## Python publishing toolkit (`mamut-routing-publish`)

The Python package `mamut_routing_publish` owns site payload generation, static HTML shell generation, and release `.zip` archive generation. It depends on [`mamut-routing-lib`](https://github.com/ANR-MAMUT/MAMUT-routing-lib) for the benchmark data contract.

### Setup

#### Python
```bash
# clone with the tooling submodules (benchmark family satellites stay
# empty — opt in per family, see "Benchmark family satellites")
git clone git@github.com:ANR-MAMUT/MAMUT-routing.git
cd MAMUT-routing
git submodule update --init MAMUT-routing-lib MAMUT-routing-tools

# install (uv workspace: editable mamut-routing-lib + mamut-routing-tools)
uv sync
```

#### Julia (offline TD generation only)

Building and serving the website needs no Julia. Julia is only required to run the offline time-dependent benchmark generation pipeline (`workbench build-family` / `traffic-sim`). To set it up, run from the repo root:
```bash
julia --project=webapp -e 'using Pkg; Pkg.instantiate(); Pkg.precompile()'
```


### Publishing the site (build order)

The whole publish is three chained steps: fetch the data, install, build, then serve:

```bash
git submodule update --init MAMUT-routing-lib MAMUT-routing-tools benchmarks/Mamut2026 \
  && uv sync \
  && uv run mamut-routing-publish site build \
  && uv run mamut-routing-publish serve
```

`site build` materializes everything it needs itself, incrementally: the build-time ATF cache (`dist/atf-cache/`, TD schedule tables and arc-click sidecars for the materialized-model families; `--atf-max-n`, default 400) and the BKS route-geometry cache (`dist/route-geometry-cache/`, sha-pinned per BKS at every instance size, produced by the MAMUT-routing-tools road engine in parallel per city; `--route-geometry-jobs`, `--skip-route-geometry` to opt out). Staging builds seed the cache from the active `dist` and materialize the remainder into the staging output. The standalone `site materialize-atf` and `site materialize-route-geometry` commands remain available for pre-warming.

`serve` binds `127.0.0.1:8082` by default (pass `--host`/`--port` for deployments) and serves `dist/` plus the repo artifact roots with real cache headers, ETags, Range, and precompressed `.gz`/`.br` negotiation (build with `--precompress` to generate the sidecars). Persistent history state lives in `publish-state/`; release-style staging builds (`--site-output-dir`) never write the active `dist`.

Initialize more satellite submodules first to publish more families; `dist/` is fully static, so any web server can serve it instead of the last step.

### CLI variants

```bash
uv run mamut-routing-publish --help

# Quiet build for scripts that do not want progress on stderr
uv run mamut-routing-publish site build --quiet

# Machine-readable progress events on stderr + generated file lists in stdout summary
uv run mamut-routing-publish site build --progress-format json --list-files

# Payloads only / static HTML shell only (assumes payloads already exist)
uv run mamut-routing-publish site payloads
uv run mamut-routing-publish site webapp

# Build release archives + manifest into ./dist-release/
uv run mamut-routing-publish release build

# Generate a Mamut2026-pipeline family for a city (CVRP base, VRPTW TW sets,
# 6 traffic overlays, 12 TD twins, shared sidecars); requires Julia (offline
# TD generation pipeline). Interactive generation lives in MAMUT-routing-tools.
uv run mamut-routing-publish workbench build-family Lyon --n 25 --method poi_categories --out-root instances_v2/workbench-collection
```

By default, the CLI resolves the MAMUT-routing repo root from the current working directory, or from the `MAMUT_ROUTING_ROOT` environment variable (shared with `mamut-routing-lib`). Override via `--output-repo-dir` / `--source-repo-dir`. `site build` reports progress and a final human-readable duration/file/memory summary to stderr by default, then keeps the machine-readable JSON summary on stdout. Instance payload resolution runs in parallel by default with `--jobs auto`, defined as `max(1, os.cpu_count() - 2)` and capped by the number of discovered instances. Use `--jobs 1` for serial resolution.

### Tests

```bash
uv run pytest
```

## Serving

```bash
uv run mamut-routing-publish serve --repo-root "$(pwd)"
```

This starts the static site server (Python, `127.0.0.1:8082` by default): the built `dist/` tree plus the repo artifact roots (`LICENSE`, `benchmarks/`, `dist/` caches referenced by payloads) and `/healthz`. There are no compute endpoints; generation and solving live in [MAMUT-routing-tools](https://github.com/ANR-MAMUT/MAMUT-routing-tools).

## Archival and reproducibility

`MAMUT-routing` is archived by [Software Heritage](https://www.softwareheritage.org/). The badge above points to the archived GitHub origin and tracks the repository-level archive status:

- [Software Heritage origin](https://archive.softwareheritage.org/browse/origin/?origin_url=https://github.com/ANR-MAMUT/MAMUT-routing)
- [Software Heritage archival visits](https://archive.softwareheritage.org/browse/origin/visits/?origin_url=https://github.com/ANR-MAMUT/MAMUT-routing)

For academic referencing, use Software Heritage identifiers (SWHIDs) to cite precise archived objects rather than the moving repository origin. This is especially useful for reproducibility because MAMUT-routing contains several layers of research artifacts:

- a full repository revision, to identify the exact version of the benchmark contract and publishing tooling;
- a release directory or tagged revision, to identify a stable public snapshot;
- an individual instance file, BKS file, metadata file, or generated artifact, to pin-point the exact object used in an experiment;
- a line-level source-code reference, when a paper or report needs to cite a specific validation rule, parser, objective implementation, or publishing routine.

Versioned SWHIDs for public releases will be listed in the citation metadata and release notes. When reporting computational results, prefer citing both the MAMUT-routing release and the exact benchmark artifacts used whenever the distinction matters.

## License

The source code is licensed under the [MIT License](LICENSE).

This repository also contains benchmark data and generated artifacts under
family-specific terms. In particular, `Ortec2022` material is under
`CC BY-NC 4.0`, and OSM-derived `Mamut2026` artifacts are under `ODbL 1.0`
where applicable. See [NOTICE](NOTICE) and the `README.md`/`LICENSE` files in
each benchmark family directory.
