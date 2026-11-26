# Publish edition r1

The four publication decisions cover the library on PyPI, the benchmark snapshot, the production website and the public specification. Obtain approval for each destination and revision before publishing. The library, both route checkers, family archives and site work without Kayros. The generation tools are available at the source revision pinned in this collection. A tools or Kayros package release has its own schedule.

## Publish the library

Check out the reviewed library revision. Match the version in `pyproject.toml`, the lockfile and `CITATION.cff`. Use the actual release date when recording it. Validate the citation file and run the distribution workflow checks for CPython 3.11 through 3.14 on Linux x86-64, including a clean installation from the sdist. Check static and time-dependent incumbents with the installed CLI. Preserve the Python reference installation instructions for other platforms.

Once the library release and its PyPI upload have been approved, create the annotated tag on the reviewed library commit and publish its GitHub Release. The published-release event runs `.github/workflows/publish.yml`, which builds the distributions and uploads them through the `pypi` trusted-publishing environment. Verify the filenames, distribution hashes and installation from PyPI. Keep the collection's library pointer and the tools' nested library pointer on the same reviewed revision.

## Publish the family snapshot

Use a fresh checkout at the approved collection commit. Initialize every family from its recorded gitlink. The archive builder reads the files present on disk, so a generated matrix or an untracked file in a family checkout can change the ZIP.

```bash
git -c url.https://github.com/.insteadOf=git@github.com: submodule update --init --recursive
git submodule status --recursive
git submodule foreach --recursive 'test -z "$(git status --porcelain --untracked-files=all)"'
uv sync --locked
snapshot_id="$(date -u +%F)-$(git rev-parse --short=7 HEAD)"
tag="snapshot-$snapshot_id"
uv run mamut-routing-publish release build \
    --source-commit "$(git rev-parse HEAD)" --snapshot-id "$snapshot_id" --release-tag "$tag" \
    --download-base-url "https://github.com/ANR-MAMUT/MAMUT-routing/releases/download/$tag"
```

Check that every gitlink matches its recorded SHA and that `dist-release/snapshot-manifest.json` lists all 11 families. Each deterministic ZIP contains a whole family, including its shared sidecars, manifest and stored results. Mamut2026's POI-tier distance matrices and Blauth2024's n=1000/2000 ATF sidecars ship as regeneration instructions with hashes. Review size and SHA-256 for each asset. The builder warns at 1.5 GiB and rejects assets at or above 2 GiB.

After snapshot approval, attach the 11 ZIPs and manifest to a release of the collection at the snapshot tag. From a clean environment with the edition library installed, use the same tag and family selector for download and verification.

```bash
check="$(mktemp -d)"
mamut-routing remote --tag "$tag" list
mamut-routing --benchmarks-dir "$check" remote --tag "$tag" fetch --benchmark-name Sintef2008
mamut-routing --benchmarks-dir "$check" remote --tag "$tag" verify --benchmark-name Sintef2008
mamut-routing --benchmarks-dir "$check" list --benchmark-name Sintef2008 --problem-type VRPTW
```

A family ZIP spans its problem types. A remote `--problem-type` filter retains family collections because their contents can include the requested type. Use `--benchmark-name` to choose a ZIP and the local `list --problem-type` to select instances after extraction. An unfiltered remote `verify` expects all manifest assets in the destination.

## Deploy the site

Build the site from the approved collection and software revisions, preserving its data and history inputs. Verify the full coverage of benchmark manifests, stored results, witness bindings and route geometries. Run strict documentation, HTTP and browser checks on the build. Confirm the production deployment checkout, the previous serving revision and the operator authorized to switch them. Once deployment is approved, use the deployment repository's runbook and smoke tests. Check the public health endpoint, documentation, history entry, and at least one benchmark and result against the approved build.

## Publish the specification

Check the specification revision, PDF, companion schemas, examples and validation report. Agree on a publicly readable destination and version before publication. After approval, attach the verified files at that destination and record their SHA-256 and anonymous download URLs. Cite the specification and data snapshot separately. A Zenodo deposit or DOI has its own approval.
