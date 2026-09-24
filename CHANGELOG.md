# Changelog

Notable changes of the MAMUT-routing repository (benchmark tree, publisher, website, documentation). The
per-snapshot data deltas (families, instances and BKS added, removed, improved) are on the website's
[History](https://mamut-routing.univ-ubs.fr/history/) page; each satellite keeps its own `CHANGELOG.md`; the lib and
the tools have their own release notes.

## Unreleased — 2026-09-24 codebase audit fixes

Fixes the two critical and eleven high findings of the 2026-09-24 audit, with the medium and low findings that sat
on the same code paths. Pins mamut-routing-lib 0.12.0 (`a9f7d9a`, both checkouts) and mamut-routing-tools 0.6.0
(`7e02980`).

### Data

- **TD BKS re-priced under the `td-fold/2` checker contract** (lib 0.12.0: exact vertex ready-time transform,
  exact slope-one travel). 3 072 TD BKS files checked (20 Blauth2024 n=1000/2000 wait for their unhosted
  sidecars), 870 cost moves, all float rounding except Rifki2020
  Rifki-30 (8292 -> 8267) and Rifki-13 n=60 (17386 -> 17385); no route changed; moved costs carry
  `metadata.repriced`; 210 optimality stamps follow their cost with a re-certification-pending note. Each
  family's CHANGELOG has the details (Dabia2013 is in-tree); a second pass reports every file unchanged.
- **Relaxation-twin cross-evaluation**: every TDVRPTW BKS was offered to its TDVRP twin and every collection VRPTW
  BKS to its CVRP twin through the improve-only stores. 43 BKS improved: 41 Poryos2026 TDVRP (up to -1.74 %), the
  Poryos2026 CVRP/fastest `hong_kong-n500-poi` (-0.26 %) and one Ari2018 TDVRP (-0.41 %); no stamped BKS was
  affected, and `tests/test_relaxation_invariants.py` now finds no relaxation BKS worse than its restriction over
  the 1 696 twin pairs.
- **Mamut2026**: the 31 campaign-2 "improvements" that were exact-decimal ties are restored to their first-pass
  solutions; the campaign tally is 285 improved, 45 tied.
- Dimacs2021 CHANGELOG: its costs are `trunc(10 × hypot)` on unscaled coordinates, not "coordinates × 10".

### Website and publisher

- Collection pages sort by BKS cost and route count again.
- No link-controlled payload source (`?payloadMode=api&apiPrefix=...` could load attacker markup); every href
  is percent-encoded or scheme-checked; the HTML shells escape their attributes and carry a Content-Security-Policy
  with hash-pinned inline scripts. `--payload-mode api` is gone (`static` only).
- `.vrp` downloads offer the coordinate-only `EUC_2D` / Solomon variants only where the coordinates define the
  costs (not Dimacs2021).
- The build-time ATF cache verifies reused entries against the instance's `atf_sha256`, regenerates stale or
  truncated ones, writes atomically; a page whose sidecar misses its pin loses its schedule table, not the build.
- The publication history lists re-priced BKS (same routes, new checker contract) in their own bucket instead of
  "improved" / "regressed".
- Release archives never ship `.mamut-release.json` stamps, `.mamut-staging/` or `*.partial` files.

### Tests and documentation

- New: release round-trip (build → `remote fetch` over `file://` → discovery, `list`, `verify`), relaxation
  invariants over every twin pair, td-fold/2 route vectors on the published data, collection sort, site security,
  ATF cache.
- The td-fold/2 contract is specified in `docs/benchmarks/formats/time-dependent.md` (with test vectors for
  KAYROS); new runbook *Re-price after a checker-contract change*; releases, exports, solve, the static store's
  exact ties and the tools' regeneration behaviour are documented.

### Push order

Pins point at commits on the `fix/audit-2026-09-24` branches: push the lib, then the tools, then the satellites,
then this repository, and merge without squashing (or re-pin after merging).

## Snapshot release 2026-09-23

First release archives since `snapshot-2026-07-06-172eb21`: adds Lera2026 (TDVRP, TDVRPTW), Blauth2024
(TDVRPTW) and the Poryos2026 and Mamut2026 collections; the v1 `CVRP/Mamut2026` and `VRPTW/Mamut2026` archives are
gone (that family is now Poryos2026). Per-family notes are in the GitHub release.

### Added

- `release build` packages each family-first collection as one `family_collection` archive
  (`<Family>-snapshot-<id>.zip`: every problem type, the shared sidecars, the marker); it used to fail on them.
- Documentation site (MkDocs Material) under `docs/`, served at `/docs/` and built as a phase of `site build`
  (`site docs`, `--skip-docs`); generated family, report, CLI and API reference pages; `Docs` CI workflow.
- `CONTRIBUTING.md` and this changelog.

### Changed

- Release archives no longer include the `.git` gitfiles of satellite submodules.
- The lib is pinned at 0.11.0.

- Home page featured showcase: three small Poryos2026 previews (VRPTW, TDVRP, TDVRPTW) and the three smallest
  Mamut2026 bases replace the four-Poryos-plus-two-historical mix; the card grows with the viewport instead of
  staying 400px wide.
- The website header links to the documentation.
- `uv sync` installs the `docs` dependency group by default.

## Earlier

The repository history before this file (2026-05 to 2026-09): the Poryos2026 and Mamut2026 generated collections,
the time-dependent families (Dabia2013, Ari2018, Vu2020, Rifki2020, Lera2026, Blauth2024) as satellites, the
Python publisher replacing the Julia site backend, keyed CARTO basemaps, the CVRPLIB `.vrp` export, route-rendering
controls. See `git log` and the website history.
