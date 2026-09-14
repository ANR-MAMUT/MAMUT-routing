# Changelog

Notable changes of the MAMUT-routing repository (benchmark tree, publisher, website, documentation). The
per-snapshot data deltas (families, instances and BKS added, removed, improved) are on the website's
[History](https://mamut-routing.univ-ubs.fr/history/) page; each satellite keeps its own `CHANGELOG.md`; the lib and
the tools have their own release notes.

## Unreleased

### Added

- Documentation site (MkDocs Material) under `docs/`, served at `/docs/` and built as a phase of `site build`
  (`site docs`, `--skip-docs`); generated family, report, CLI and API reference pages; `Docs` CI workflow.
- `CONTRIBUTING.md` and this changelog.

### Changed

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
