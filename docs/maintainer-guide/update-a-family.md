# Update a benchmark family

For changes to an existing family: new instances, corrected sidecars, README or changelog edits, license
clarifications. BKS replacements have [their own page](update-a-bks.md).

## In the family repository

Every family is its own repository (`MAMUT-routing-<Family>`), checked out as a submodule at `benchmarks/<Family>/`. One repository holds all the problem types of the family.

1. Edit under `benchmarks/<Family>/<ProblemType>/` and keep the layout (`[<subset>/]n=<N>/` directories, `<base>.vrp.json`, `<base>.bks.<Objective>.json`, sidecars under `benchmarks/<Family>/sidecars/`).
2. Validate what you touched:
   ```bash
   uv run mamut-routing list --benchmark-name Sintef2008 --problem-type VRPTW      # every instance still resolves
   uv run pytest tests/test_vrp_export_regression.py                               # committed .vrp files still byte-identical
   ```
3. Add an entry to the family `CHANGELOG.md` at the family root (date, what, why, source).
4. Build a staging site and look at the family and instance pages (see [Build the website](build-the-website.md)).
5. Commit in the family checkout with a message that names the change, and push there first. The history ledger will record the instance/BKS deltas on the next publish.

## In the superproject

1. Record the new pointer:
   ```bash
   git -C benchmarks/Rifki2020 log --oneline -1        # the commit you just pushed
   git add benchmarks/Rifki2020
   git commit -m "chore: bump Rifki2020 to <short sha> (<what changed>)"
   ```
   A TD family has one mount for both its problem types (`benchmarks/<Family>/`), so one bump covers both.
2. Build a staging site and check the pages, then deploy. The deploy script updates submodules recursively and archives stale directories of retired submodules before the publisher scans `benchmarks/`.

## Sidecars and pins

Instances reference their sidecars by sha256. If you regenerate a sidecar (distance matrix, ATF, road graph, geo),
the instance's pin must change with it, or loading fails. The generators do that for you
(`mamut-tools generate materialize-distances` for large distance matrices, the family pipeline for the rest);
never edit a sidecar by hand.

Collections keep sidecars above a size threshold as **pins only** (the bytes are not committed). Rebuild them before a
campaign that needs them:

```bash
uv run --project MAMUT-routing-tools mamut-tools generate materialize-distances \
    benchmarks/Mamut2026/CVRP/shortest benchmarks/Mamut2026/CVRP/fastest
```

## Things that must stay in sync

| Changed | Also update |
|---|---|
| a family's description | the family section in `site_assets/texts/mamut-routing_benchmark_families.md` |
| a family's license | the family `LICENSE`, the root `NOTICE`, the README license paragraph |
| a family repository's URL or mount | `.gitmodules`, the README family table |
| a family's size or scope | the README layout notes and this documentation's [Families](../benchmarks/families/index.md) pages (regenerated) |

## Retiring or renaming a family repository

Retire the old repository with a tombstone README (the former per-variant repositories, now archived, are the example), remove the
submodule from `.gitmodules` and the index, and purge `<gitdir>/modules/<path>` before adding a replacement at the
same path, otherwise git reuses the stale module clone. The publisher's `_deduplicate_discovered_instances` handles a
retired collection checkout sitting next to its renamed replacement, and the deploy script archives stale directories,
but a clean checkout is still the goal. See [Troubleshooting](troubleshooting.md).
