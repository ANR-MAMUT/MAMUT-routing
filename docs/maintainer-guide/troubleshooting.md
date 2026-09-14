# Troubleshooting

Things that have gone wrong at least once, with the fix that worked.

## Builds

**Route geometry worker killed (OOM) or runs for hours.** A large city graph needs 10 to 15+ GiB. Keep
`--route-geometry-jobs 1`, compute on a workstation and copy `dist/route-geometry-cache` to the host (content-addressed
by BKS sha256, so it is portable); the build then reports `generated=0 reused=N`. The build aborts before the release
swap, so the live site is safe.

**Pages fall back to straight route lines.** The geometry for that BKS is not in the cache: geometry was skipped
(`--skip-route-geometry`), the OSM extract was missing and fetching disabled (`--no-fetch-missing-osm`), or the BKS
changed after the last materialization. Run `site materialize-route-geometry --fetch-missing-osm`.

**Lera2026 / Poryos2026 TD instance pages have no schedule table or arc viewer.** The ATF cache phase was skipped or
capped below that size (`--atf-max-n`, default 400). Run `site materialize-atf --max-n <N> --jobs <k>` (each worker
holds one full ATF set).

**Floating-point overshoot at the horizon boundary in schedule tables.** Cosmetic, clamped in the display layer; see
the [2026-07-07 report](../reports/2026-07-07-td-schedule-horizon-boundary-clamp.md).

**Docs phase fails.** Strict MkDocs: read the warning (a link to a page that does not exist, an API page whose module
moved). `uv run mkdocs build --strict` reproduces it in seconds. Missing toolchain: `uv sync --group docs`. A checkout
without `mkdocs.yml` skips the phase silently.

## Dependencies and submodules

**`uv sync` fails with two editable sources for `mamut-routing-lib`.** The superproject must use the nested
`MAMUT-routing-tools/MAMUT-routing-lib` path (see [Repository topology](repository-topology.md)); never add a second
source.

**The tools do not behave as their README says.** A source checkout imports the nested lib, a PyPI install the
published one; check `mamut-tools --version` (prints the package directory) and the lib version it resolves.

**A re-added submodule shows the old content or the wrong remote.** Git reused the stale module clone under
`<gitdir>/modules/<path>`. Remove that directory, `git submodule deinit -f <path>`, then re-add. On a host with a
pre-rename clone: `git -C <path> remote set-url origin <new url>` then `git submodule update --init <path>`.

**The deploy host cannot reach GitHub over SSH.** Site repositories are public: `GIT_SUBMODULE_TRANSPORT=https`.
The private deploy superproject can be pushed to the host directly over ssh
(`git push ssh://<host>/<path> main:refs/remotes/local-push/main`, then fast-forward there).

**Satellite directories are empty after a clone.** Expected: `git submodule update --init <path>` per family.

## Deployments

**`deploy.sh` finished in seconds and only restarted the server.** `START_API_ONLY=1` was exported in the shell. Pass
`START_API_ONLY=0` explicitly every time.

**The host thrashes and sshd stops answering during a deploy.** Something was unpacked under a tmpfs `/tmp`. Use a
directory under `/home` (or the releases root) for archives and scratch.

**Disk full.** Releases keep the newest `KEEP_RELEASES`; check `df -h`, the stale-submodule archive directory and old
`osmdata` copies.

**`/docs/` returns 404 after a deploy.** The build ran with `--skip-docs`, or an older publisher without the phase.
Rebuild (or `site docs --site-output-dir <release dir>` into the live release, then precompress).

## Data

**A BKS file fails validation on load.** The write path re-validates before replacing, so this is a hand edit, a
sidecar whose pin changed, or a checker change. Recompute with the checker; never adjust the stored cost by hand.

**A sidecar pin mismatch.** The instance references a sidecar by sha256; regenerate the sidecar with the tool that
made it (`materialize-distances`, the family pipeline) so the pin and the bytes agree.

**Overpass errors or truncated extracts.** The fetch mirrors rotate (`overpass-api.de`, `maps.mail.ru`,
`overpass.private.coffee`); large cities are tiled with a persistent cache, so rerun the same command. `mamut-tools osm
validate` rejects incomplete files.
