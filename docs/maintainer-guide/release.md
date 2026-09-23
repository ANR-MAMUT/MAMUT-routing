# Cut a release

A release freezes three things: the code (tags and PyPI packages), the data (per-family archives with a manifest
that `mamut-routing remote` reads), and the citation record (versions, Software Heritage identifiers).

## 1. Versions

Each repository that changed gets a version bump in `pyproject.toml` (the lib and the tools follow semantic versioning;
a lib bump that changes the contract is a minor bump at least) and in `CITATION.cff` (`version`, `date-released`).
Validate the citation file:

```bash
uv run cffconvert --validate -i CITATION.cff
```

The lib and tools `CITATION.cff` have drifted from their `pyproject.toml` before; this step exists to stop that.

## 2. Tag and publish the packages

```bash
git commit -am "Release X.Y.Z"
git tag -a vX.Y.Z -m "Release X.Y.Z"        # annotated: --follow-tags ignores lightweight tags
git push origin main vX.Y.Z                 # push the tag explicitly
```

The tools publish to PyPI from a GitHub release via trusted publishing (`.github/workflows/publish.yml`, environment
`pypi`): create the GitHub release on the tag and the workflow uploads the sdist and wheel. Do the lib first, then
bump the tools' nested lib pointer and their dependency floor, then the tools, then the superproject's pointers.

## 3. Data archives

Check out every satellite first (`git submodule update --init`, then `git submodule status` shows no `-` or `+`):
the archives are built from the working tree, so an empty satellite directory is silently missing from the
release and a satellite off its pinned commit ships data the tag does not record.

```bash
uv run mamut-routing-publish release build \
    --release-tag vX.Y.Z \
    --download-base-url https://github.com/ANR-MAMUT/MAMUT-routing/releases/download/vX.Y.Z
```

Writes `dist-release/<ProblemType>-<Family>-snapshot-<id>.zip` for each classic family,
`dist-release/<Family>-snapshot-<id>.zip` for each family-first collection (the whole `benchmarks/<Family>/` tree:
every problem type, the shared `sidecars/`, the marker), both deterministic (fixed timestamps, mode 0644, deflate
level 9, sha256 streamed while writing, `.git` gitfiles skipped), and `snapshot-manifest.json`
(`ReleaseArchiveManifest`: snapshot id, published at, source commit, release tag, one `ReleaseArchiveAsset` per
archive with its download URL, sha256, size, scope `problem_family` or `family_collection`). Guards: an asset over
1.5 GiB warns, over 2 GiB fails (GitHub's limit), at most 1000 assets per release. `--jobs` parallelises compression.
Files a satellite ships as sha256 pins instead of bytes (Mamut2026's POI-tier distance matrices, Blauth2024's
n=1000/2000 ATF sidecars) are pins in the archive too; say so in the release notes.

Upload every archive and the manifest as assets of the GitHub release. Verify from a clean machine:

```bash
mamut-routing remote --tag vX.Y.Z list                       # --tag belongs to `remote`, before the subcommand
mamut-routing --benchmarks-dir /tmp/check remote --tag vX.Y.Z fetch --problem-type VRPTW --benchmark-name Sintef2008
mamut-routing --benchmarks-dir /tmp/check remote --tag vX.Y.Z verify --problem-type VRPTW --benchmark-name Sintef2008
```

Repeat the same `--tag` and the same family filters on `fetch` and `verify`: without `--tag` both fall back to the
latest release, and an unfiltered `verify` checks every asset of the manifest and fails on the ones you did not
download. A collection asset has no problem type, so select it with `--benchmark-name` alone
(`--benchmark-name Poryos2026`); adding `--problem-type` filters it out.

## 4. Archive and cite

Software Heritage archives the GitHub origins on its own schedule; trigger a save for the tagged revision if you
need the identifier now, then record the SWHID of the release revision in `CITATION.cff` (`identifiers`, type `swh`)
and in the release notes. Recommended citation granularity: the release revision for the contract and tooling, the
individual artifact for an experiment, a line-level reference for a validation rule.

## 5. Publish the site

Deploy with `--history-summary "Release vX.Y.Z: ..."` so the history page carries the release; the snapshot id of the
site and of the archives are the same `<date>-<short sha>` when built from the same commit.

## Checklist

- [ ] versions and `CITATION.cff` bumped, validated
- [ ] lib released and pinned in tools and superproject (both lib pointers on the same commit)
- [ ] tools released, PyPI shows the version, `uvx --from mamut-routing-tools mamut-tools --version`
- [ ] archives built, uploaded, `remote verify` clean
- [ ] SWHIDs recorded, release notes written
- [ ] site deployed, history entry visible, `/docs/` current
