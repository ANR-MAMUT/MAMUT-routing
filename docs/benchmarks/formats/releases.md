# Release archives

`mamut-routing-publish release build` turns the benchmark tree into downloadable archives that the lib's
`mamut-routing remote` commands consume.

## Archives

Two shapes, both with entry paths relative to the repository root (`benchmarks/...`):

| Scope | File name | Content |
|---|---|---|
| `problem_family` | `<ProblemType>-<Family>-snapshot-<snapshot-id>.zip` | the classic `benchmarks/<ProblemType>/<Family>/` tree (instances, BKS, sidecars) |
| `family_collection` | `<Family>-snapshot-<snapshot-id>.zip` | a whole family-first collection `benchmarks/<Family>/`: every problem type, the shared `sidecars/`, the `mamut-collection.json` marker, README, LICENSE, CHANGELOG |

A collection asset has `problem_type: null`; its sidecars resolve by walking up from an instance to the marker, so
the extracted tree works wherever it lands. Files a family ships as sha256 pins rather than bytes are pins in the
archive as well (see the family page for the `materialize` step). Deterministic: fixed entry timestamps
(1980-01-01), mode 0644, deflate level 9 by default, sha256 streamed while writing, `.git` gitfiles never archived.
Guards: an asset over 1.5 GiB warns, over 2 GiB fails (GitHub's asset limit); repository files over 100 MB are
refused; at most 1000 assets per release. The `family_collection` scope needs `mamut-routing-lib` 0.6.0 or later
to read the manifest.

Archives never contain local state: `.git` gitfiles, `.mamut-release.json` stamps, `.mamut-staging/` directories
and `*.partial` temp files are skipped, so a release built from a fetched tree is clean.

## Extraction (`remote fetch`, lib ≥ 0.12.0)

`mamut-routing --benchmarks-dir <bd> remote fetch …` keeps each archive at `<bd>/<filename>` and extracts the
subtree under the asset's `archive_root` into the **canonical tree**: `benchmarks/VRPTW/Sintef2008` lands at
`<bd>/VRPTW/Sintef2008`, a collection `benchmarks/Poryos2026` at `<bd>/Poryos2026`. `mamut-routing list`,
`discover_benchmark_instances(<bd>)` and the website then give the same instance IDs. `extract_release_archive`
does the work:

- every member is validated first (relative, no `..`, inside `archive_root`; the root is inferred when an older
  manifest lacks it);
- the archive is extracted into `<bd>/.mamut-staging/` and swapped in, so a failure leaves the previous subtree
  untouched;
- the target gets a `.mamut-release.json` stamp (file name, checksum, snapshot id, release tag, archive root);
- an existing target is replaced only if it carries a stamp (a previous fetch) or with `--force` (for example over
  a git checkout of the family). Re-fetching replaces the whole subtree, including files written into it since,
  such as BKS saved by `solve`.

`remote verify` checks the kept archives against the manifest (`OK`, `MISMATCH`, `NO_SHA`) and, when an archive was
deleted after extraction, the stamp of its extracted tree (`EXTRACTED` for this checksum, `STALE` for another
snapshot, `MISSING` otherwise). Before 0.12.0 the lib extracted under `<bd>/<archive stem>/benchmarks/…`, which
discovery could not read; `fetch` warns about such leftover directories and leaves them in place.

## Manifest (`snapshot-manifest.json`)

`ReleaseArchiveManifest` in `mamut_routing_lib.remote`:

| Field | |
|---|---|
| `schema_version` | manifest schema |
| `snapshot_id`, `published_at`, `source_commit`, `source_branch`, `release_tag` | the snapshot identity (same id as the website's history entry when built from the same commit) |
| `assets[]` | `ReleaseArchiveAsset`: `scope`, `filename`, `download_url`, `problem_type`, `benchmark_name`, `checksum_sha256`, `size_bytes`, `archive_root` (extra keys are rejected) |

`--release-tag` and `--download-base-url` fill the download URLs; the manifest and the archives are uploaded as
assets of the GitHub release. Consumers: `mamut-routing remote list | fetch | verify | manifest`
(`MAMUT_ROUTING_RELEASE_REPO`; `--tag` is an option of `remote` itself: `mamut-routing remote --tag vX.Y.Z list`). See [Cut a release](../../maintainer-guide/release.md).
