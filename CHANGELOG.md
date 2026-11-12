# Changelog

Notable changes of the MAMUT-routing repository (benchmark tree, publisher, website, documentation). The
per-snapshot data deltas (families, instances and BKS added, removed, improved) are on the website's
[History](https://mamut-routing.univ-ubs.fr/history/) page; each satellite keeps its own `CHANGELOG.md`; the lib and
the tools have their own release notes.

## Unreleased — solver integration (branch `feat/solver-integration`, stacked on the MapLibre test branch)

### Library and tools (pinned: lib `feat/solver-integration`, tools `feat/solver-integration`)

- **Solvers by name, behind one protocol.** `mamut_routing_lib.solvers` holds the protocol, a registry (built-ins,
  the `mamut_routing.solvers` entry-point group, `register_solver`) and `run_solver`, which prices every result
  with the reference checker. PyVRP and KAYROS are adapters; KAYROS results are now checked by the TD checker.
- **External solvers.** FILO2, HGS-CVRP, AILS-II and LKH-3 run as executables declared in a user solvers config
  (`~/.config/mamut-routing/solvers.toml`, `$MAMUT_ROUTING_SOLVERS_CONFIG`; any CVRPLIB-I/O solver can be added).
  Inputs are scaled to integers exactly when the data allow (x1000 for Mamut2026/Poryos2026), conservatively for
  time windows otherwise; solvers run in their own process group with a hard timeout. Solvers that need symmetric
  costs (FILO2, AILS-II, and by default any solver declared in the config) refuse the asymmetric `fastest` and
  `shortest` variants with the reason; LKH-3 gets them as `ACVRP`; HGS-CVRP reads the published full matrix (any
  metric) through a reader patch the lib ships (`solvers/external/patches/hgs-cvrp-explicit-matrix.patch`).
- **Solutions found elsewhere.** `mamut-routing check` and `mamut-routing bks submit` read CVRPLIB `.sol`, JSON
  and LKH-3 solution files; `mamut-routing solvers list` shows what is available.
- **Breaking: `mamut-routing solve --save-bks` is opt-in and needs `--authors`** (it wrote BKS by default, credited
  to the maintainers); `mamut-tools solve --update-bks` needs `--authors` too; `solve_and_update_bks` requires
  `authors=`. The `solve` COST column is the checker's cost (it showed PyVRP's x1000 objective on collection
  instances).
- **Workbench.** A Solver select (`GET /api/solvers`), solve jobs with any registered solver, runs that record
  their solver, real cancellation of external solvers, LKH-3 solution import.
- **`mamut-tools bks-campaign`**: spec-driven, resumable multi-solver campaigns with a frozen baseline, a
  single-writer harvest and ledger / cross-solver reports -- the pattern of the Mamut2026 campaigns 2 and 3.
- **Ease of use.**
  - `solve --output-dir` keeps every solution, and `bks submit` stores one later with its provenance.
  - The `solve` table gains a GAP column (to the stored BKS).
  - Both CLIs accept `--time-limit-s`/`--time-limit` and `--save-bks`/`--update-bks`.
  - `mamut-routing solvers init` writes a commented starter solvers config, and `solvers list` is shorter.
  - An error in one config table disables only that solver, with a "did you mean". Values are type-checked,
    `extends` works in any order, and relative paths are read from the config's folder.
  - Campaigns keep every harvest, and SIGTERM aborts a campaign run at once.
  - The workbench refuses unsupported solver/variant pairs at submission and shows Animate on the Solve and Runs
    tabs.
  - Workbench instances generated before the Mamut2026 -> Poryos2026 rename open again.
- **Fixes from the branch review (2026-11-12).**
  - KAYROS runs in a child Python process: a stop request (Ctrl-C, a GUI cancel) was ignored once the search
    stopped improving, until the time limit. A stopped solve keeps its last incumbent.
  - A failed external run reports the solver's last output lines instead of only "no solution file".
  - LKH-3 `extra_args` reach the parameter file also when the command is wrapped (`taskset`, a launcher).
  - A loose `progress_pattern` can no longer end a working solve; `check` exits 2 on JSON that is not a solution
    (`null`, a number) instead of printing a traceback.
  - One solve reads the distance matrix once (it was three times with `--save-bks`):
    `submit_bks(..., checkable=solved.checkable)`, `load_checkable`.
  - Campaigns: `warm_start = "best"` runs start last, from the campaign's own results (they started first, from
    the stored BKS); a harvest records what it wrote even when a store call fails or it is interrupted; the orphan
    kill after a dead worker only touches that worker's processes.
  - Workbench: displaying a saved run refreshes the solver list for its metric; a run the `fastest` times cannot
    clock animates at constant speed, with the reason, instead of failing; the solver-support cache no longer
    keeps whole instances in memory.

### Website

- The route animation's time slider no longer jumps under the pointer while playback runs.
- Blauth2024 instances are drawn on their cities again: they publish real longitudes and latitudes without
  `reference_lla`, and the planar display frame (new with MapLibre) took them for a plane and drew them around
  (0, 0). They declare their coordinates (`metadata.coordinates_convention`), which now decides.
- The "needs WebGL2" notice no longer dims the routes or shows "Stop animation"; a scrubber drag no longer leaves a
  listener (and the closed animation's data) behind.

### Documentation

- Getting started has a sixth tutorial, "Tour the tools" (`docs/getting-started/tour-the-tools.md`): one pass from a
  city download to a generated instance solved under three metrics and under traffic, exported, and opened in the
  workbench GUI.
- The tools test command is `uv run --directory MAMUT-routing-tools pytest`: with `--project`, as documented,
  pytest still collected from the repository root and ran the publisher and lib suites a second time.
- Getting started (solve and BKS), solution formats, BKS campaigns, update a BKS, workbench API (the
  `/api/workbench/solve` row was wrong), environment variables, developer and user guides.

## Unreleased — MapLibre workbench map and route animation (test branch `test/maplibre-trips-animation`)

### Website

- **The workbench map is MapLibre GL; Leaflet and the maplibre-gl-leaflet bridge are gone.**
  - Routes, line-placed direction arrows, customers and the depot star are styled through feature-state, so focus,
    the fade sliders and hide/show never rebuild geometry. On Bogotá n = 4000, a slider tick went from about 0.9 s
    to about 1 ms. This closes audit finding C-workbench-geometry-05.
  - Huge solutions are thinned to a 1 M-point budget with an exact, one-pass ranked Douglas–Peucker before they
    reach MapLibre.
  - Popups are text-only.
- **Route animation.** **Animate** plays a BKS's vehicles with deck.gl 9.4.0 `TripsLayer`, vendored and loaded on
  demand. Times come from:
  - new per-BKS `timeline.<Objective>.json` payloads (VRPTW: the checker's schedule; CVRP: the free-flow
    `fastest` clock);
  - `td_schedules` for TD instances;
  - a labelled constant 25 km/h otherwise.
- `site.js` exports `payloadSidecarHref` (formerly `routeFunctionsHref`).
- The map code is shared byte for byte with the tools GUI (`mamut-map.js`, `mamut-trips.js`, the vendored
  MapLibre and deck.gl). `tests/test_shared_frontend_assets.py` keeps the copies equal.
- Pins the tools test branch (MapLibre GUI, `/timeline`, `arc_starts`).

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
