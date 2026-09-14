# Repository topology

```
MAMUT-routing (superproject, this repository)
├── MAMUT-routing-lib/               submodule kept for browsing/diffing; NOT the copy uv installs
├── MAMUT-routing-tools/             submodule and uv workspace member
│   └── MAMUT-routing-lib/           nested submodule: the lib uv installs ([tool.uv.sources])
├── benchmarks/
│   ├── VRPTW/{Sintef2008,Dimacs2021,Ortec2022}/     in-repo families
│   ├── TDVRPTW/Dabia2013/, TDVRP/Dabia2013/          in-repo default TD family
│   ├── TDVRPTW/<Family>/, TDVRP/<Family>/            satellite submodules (Ari2018, Vu2020, Rifki2020, Lera2026, Blauth2024)
│   ├── Poryos2026/, Mamut2026/                       family-first collection satellites
├── osmdata/                          git-ignored OSM extracts feeding route geometry
├── src/mamut_routing_publish/        the publisher
├── docs/ + mkdocs.yml                this documentation
├── tests/                            publisher tests (pytest also runs MAMUT-routing-lib/tests)
├── dist/                             site output; on deployments a symlink to the live release
├── dist-release/                     release archives + snapshot-manifest.json
└── publish-state/                    history ledger + snapshot inventories, git-ignored, survives releases
```

## Four repositories, one contract

| Repository | Owns | Published as |
|---|---|---|
| `MAMUT-routing-lib` | the contract: models, checkers, BKS logic, sidecars, remote archives, CVRPLIB export, `mamut-routing` CLI | PyPI `mamut-routing-lib` |
| `MAMUT-routing-tools` | everything that computes: OSM, road graphs, generation, traffic models, converters, geometry, workbench GUI, `mamut-tools` CLI | PyPI `mamut-routing-tools` |
| `MAMUT-routing` | the benchmark tree, the publisher, the website, the docs, the releases | GitHub releases (archives + manifest), the website |
| `mamut-routing-deploy` (private) | host provisioning, nginx and systemd templates, `deploy.sh`, the operations runbook of the production VM | not published |

The lib is the only shared dependency. The tools pin a lib commit as their nested submodule and declare it as an
editable source; the superproject **must** resolve `mamut-routing-lib` from that same nested path, otherwise uv sees
two editable URLs for one package and refuses to resolve. That is why `pyproject.toml` here says:

```toml
[tool.uv.sources]
mamut-routing-lib = { path = "MAMUT-routing-tools/MAMUT-routing-lib", editable = true }
mamut-routing-tools = { workspace = true }
```

Keep the top-level `MAMUT-routing-lib` pointer on the same commit as the nested one (it exists so a browse or a
`git diff` from the superproject shows the lib; nothing imports it).

## Satellites

A satellite is a self-contained repository (instances, BKS, sidecars, `README.md`, `CHANGELOG.md`, `LICENSE`) mounted
at its family directory. A plain clone leaves the directory **empty**; every tool, test and build must tolerate that,
and the documentation build does (family pages fall back to a GitHub link).

```bash
git submodule update --init benchmarks/TDVRPTW/Rifki2020    # one family (0.1–0.8 GB each)
git submodule update --init benchmarks/Poryos2026            # a collection (~0.4 GB)
git submodule update --init                                  # everything (~2.8 GB)
```

Two layouts, both discovered by `discover_benchmark_instances` in the lib:

- **classic**: `benchmarks/<ProblemType>/<Family>/n=<N>/<instance>.vrp.json`;
- **family-first collection**: `benchmarks/<Family>/{CVRP,VRPTW,TDVRP,TDVRPTW}/...` plus `benchmarks/<Family>/sidecars/`,
  rooted by `mamut-collection.json` (`{"format": "mamut-collection", "format_version": 1, "family": "<Family>", "layout_version": 1}`).

`.gitmodules` is the list of satellites; the README satellite table is the human copy.

## The uv workspace

```bash
uv sync                      # publisher + dev + docs groups, editable lib and tools
uv run pytest                # tests/ and MAMUT-routing-lib/tests
uv run --project MAMUT-routing-tools pytest
uv lock                      # after any dependency change; uv.lock is tracked
```

Environment variables that change where things are looked up are listed in the
[reference](../reference/environment-variables.md); the two that matter daily are `MAMUT_ROUTING_ROOT` (repo root for
the CLIs when not run from the checkout) and `MAMUT_BASEMAP_API_KEY`.

## Where the truth lives

| Question | Look at |
|---|---|
| Which families exist | `BenchmarkName` in `mamut_routing_lib.enums` and `.gitmodules` |
| What a family is, for the website and these docs | `src/mamut_routing_publish/site_assets/texts/mamut-routing_benchmark_families.md` |
| Data licenses | each family `LICENSE` (first line `SPDX-License-Identifier: ...`) and the root `NOTICE` |
| Why a decision was made | `docs/reports/` ([index](../reports/index.md)) |
| How the production host is set up | `mamut-routing-deploy/docs/OPERATIONS.md` (private) |
