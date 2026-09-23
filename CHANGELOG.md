# Changelog

Notable changes of the MAMUT-routing repository (benchmark tree, publisher, website, documentation). The
per-snapshot data deltas (families, instances and BKS added, removed, improved) are on the website's
[History](https://mamut-routing.univ-ubs.fr/history/) page; each satellite keeps its own `CHANGELOG.md`; the lib and
the tools have their own release notes.

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
