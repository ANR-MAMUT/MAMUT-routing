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
