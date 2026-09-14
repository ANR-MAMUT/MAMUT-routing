# Release archives

`mamut-routing-publish release build` turns the benchmark tree into downloadable archives that the lib's
`mamut-routing remote` commands consume.

## Archives

One zip per (problem type, family): `<ProblemType>-<Family>-snapshot-<snapshot-id>.zip`, containing that family's
tree (instances, BKS, sidecars it references). Deterministic: fixed entry timestamps (1980-01-01), mode 0644,
deflate level 9 by default, sha256 streamed while writing. Guards: an asset over 1.5 GiB warns, over 2 GiB fails
(GitHub's asset limit); repository files over 100 MB are refused; at most 1000 assets per release.

## Manifest (`snapshot-manifest.json`)

`ReleaseArchiveManifest` in `mamut_routing_lib.remote`:

| Field | |
|---|---|
| `schema_version` | manifest schema |
| `snapshot_id`, `published_at`, `source_commit`, `source_branch`, `release_tag` | the snapshot identity (same id as the website's history entry when built from the same commit) |
| `assets[]` | `ReleaseArchiveAsset`: `scope`, `filename`, `download_url`, `problem_type`, `benchmark_name`, `sha256`, `size_bytes`, `archive_root` |

`--release-tag` and `--download-base-url` fill the download URLs; the manifest and the archives are uploaded as
assets of the GitHub release. Consumers: `mamut-routing remote list | fetch | verify | manifest`
(`MAMUT_ROUTING_RELEASE_REPO`, `--tag`). See [Cut a release](../../maintainer-guide/release.md).
