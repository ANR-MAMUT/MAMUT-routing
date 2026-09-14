# Maintainer guide

Runbooks for the people who keep the platform running: the benchmark tree, the best-known solutions, the website
and its deployment, the releases. The pages of this section are being written in this order; until a topic has
its own page, the summary below is the reference.

## Repository topology

```
MAMUT-routing (superproject)
├── MAMUT-routing-lib/            submodule, kept for browsing; NOT the copy uv installs
├── MAMUT-routing-tools/          submodule + uv workspace member
│   └── MAMUT-routing-lib/        nested submodule: the lib uv actually installs ([tool.uv.sources])
├── benchmarks/<Type>/<Family>/   in-repo defaults (Sintef2008, Dimacs2021, Ortec2022, Dabia2013) and TD satellites
├── benchmarks/<Collection>/      family-first satellites (Poryos2026, Mamut2026)
├── src/mamut_routing_publish/    the publisher (site, caches, docs, releases, server)
├── docs/ + mkdocs.yml            this documentation (built into dist/docs/)
├── dist/                         site output (a symlink to the live release on deployments)
├── dist-release/                 release archives + snapshot-manifest.json
└── publish-state/                history ledger + snapshot inventories (survives fresh release dirs)
```

Both lib checkouts must point at the same commit. `uv` resolves `mamut-routing-lib` from the nested path because
the tools declare their own editable source; naming a second path would give uv two editable URLs for one package.

## Update a benchmark family

1. Commit the change in the satellite repository (instances, BKS, sidecars, its `CHANGELOG.md` and `README.md`).
2. In the superproject, bump the submodule pointer: `git -C benchmarks/<...> pull` then `git add benchmarks/<...>`.
3. Rebuild (`site build`); the history ledger records instances/BKS added, removed, improved or regressed.
4. Pass a meaningful `--history-summary` and commit; deploy.

If a satellite was re-added under a new name, purge `<gitdir>/modules/<path>` before re-adding it, otherwise the
stale module clone is reused.

## Update or submit a BKS

Static families: `mamut-routing solve --save-bks` or, from Python, `save_bks_if_improved` /
`save_solution_as_bks_if_improved` (`mamut_routing_lib.bks`). Both re-validate the stored BKS, compare under the
objective, and replace only a strictly better solution; the result says `created`, `replaced` or `kept_existing`.
Time-dependent families use `save_td_solution_as_bks_if_improved` and `annotate_td_bks_optimality`
(`mamut_routing_lib.td.bks`). A replaced BKS of a road-network family invalidates its route geometry: run
`site materialize-route-geometry` (content-addressed by BKS sha256) before deploying, on a machine with enough
memory (a large city graph can exceed 15 GiB).

Record provenance in the BKS metadata (method, seed, time limit, solver version, machine) so a campaign can be
re-run; see the [Mamut2026 BKS campaign 2 plan](../reports/2026-09-06-mamut2026-bks-campaign-2-plan.md) for the
campaign pattern (driver script calling the library, per-run archive, ledger, no solving on the site VM).

## Add a benchmark family

1. Create the satellite repository with the classic or collection layout, `README.md`, `CHANGELOG.md` and a
   `LICENSE` whose first line is `SPDX-License-Identifier: <id>` (the publisher reads it for the license card).
2. Add the family to `BenchmarkName` in `mamut_routing_lib.enums` (and release the lib).
3. Mount it: `git submodule add <url> benchmarks/<Type>/<Family>` (or `benchmarks/<Family>` for a collection).
4. Add a ``### `Family` (Type)`` section to `src/mamut_routing_publish/site_assets/texts/mamut-routing_benchmark_families.md`
   (it feeds both the website family page and this documentation).
5. Add the license clause to `NOTICE` and the row to the README satellite table.
6. Materialized-td-model families (igp-profile, road-graph) need `atf_cache.py` to know their model.
7. Build, check the family page and the instance pages, deploy.

## Add a problem type or objective

All in `mamut-routing-lib`: the `ProblemType` / `ObjectiveFunction` enums, the instance model, the layout parser
and loader dispatch in `artifacts.py` (`parse_layout`, `load_benchmark_instance`, `instance_problem_type`), the
checker, the BKS naming (`<base>.bks.<Objective>.json`). Then the publisher payload kinds and the website's
`site.js` renderer. There is no plugin registry: this is a deliberate, versioned contract change.

## Generate a family

Poryos2026 is built by the three-stage pipeline in `mamut_routing_tools.family` (`build_base` → `derive_vrptw` →
`build_td`), Mamut2026 adds the campaign design layer in `mamut_routing_tools.campaign` (city profiles, POI
capacity, size ladder, candidate evaluation, max-min selection under quotas). Bulk generation is a per-campaign
script, not a CLI command. Conversions of external distributions follow `mamut_routing_tools.conversion.blauth2024`.

## Build the website

```bash
git submodule update --init MAMUT-routing-lib MAMUT-routing-tools benchmarks/Poryos2026 benchmarks/Mamut2026
uv sync
uv run mamut-routing-publish site build [--precompress]
uv run mamut-routing-publish serve --host 0.0.0.0 --port 8081
```

Phases, in order: ATF cache (`--atf-max-n`, `--atf-jobs`), BKS route geometry (`--route-geometry-jobs`, OSM fetch of
missing extracts, `--skip-route-geometry`), payloads (`--jobs`), HTML shell, documentation (`--skip-docs`),
precompression. Staging builds (`--site-output-dir`) seed their caches from the active `dist` and never write it.

## Deploy

The site is static: nginx serves the release directory (`dist` symlink) with `try_files`, and `mamut-routing-publish
serve` provides the same tree with cache headers, ETags, Range and precompressed negotiation when nginx is not
used. The deploy superproject pins this repository and drives `deploy.sh` (source update, `uv sync`, staging build,
health check, release swap, keep the last N releases). Host-specific details live in that private repository's
`OPERATIONS.md`. Two rules learned the hard way: never unpack large archives under a tmpfs `/tmp`, and copy a
warm `route-geometry-cache` to the host instead of computing geometry on a small VM.

## Cut a release

1. Bump versions (`pyproject.toml`) and `CITATION.cff` in the repositories that changed; run `cffconvert --validate`.
2. Tag `vX.Y.Z`; the tools publish to PyPI from a GitHub release (trusted publishing workflow).
3. `uv run mamut-routing-publish release build --release-tag vX.Y.Z --download-base-url <assets url>`: one
   deterministic zip per (type, family) plus `snapshot-manifest.json` (asset size guards: warn 1.5 GiB, fail 2 GiB).
4. Upload the archives and the manifest to the GitHub release; `mamut-routing remote list` reads it.
5. Record the Software Heritage identifier of the release revision in `CITATION.cff` and the release notes.
