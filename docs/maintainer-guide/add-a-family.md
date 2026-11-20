# Add a benchmark family

Bringing a new family online touches the lib (the name), the superproject (the mount and the texts) and this
documentation (regenerated). Order matters because the publisher only sees names the lib knows.

## 1. Prepare the family repository

- Layout: every family is a collection. The repository root *is* the family directory `benchmarks/<Family>/`. It holds `mamut-collection.json`, one tree per problem type and `sidecars/`. The marker's `layout_version` is 2 for the classic shape (`<ProblemType>/[<subset>/]n=<N>/<file>.vrp.json`) and 1 for the generated-collection shape of Poryos2026 (see [Layouts](../benchmarks/formats/layouts.md)).
- Files at the root, one set for all the problem types: `README.md` (sources, provenance, conventions, how it was built), `CHANGELOG.md`, `CITATION.cff`, `LICENSE` whose first line is `SPDX-License-Identifier: <id>` (the website's license card is parsed from it), and the generator record in every artifact's `generator` block.
- Every instance loads and every BKS validates: `mamut-routing --benchmarks-dir <root> list` and a checker pass
  over the BKS files.
- Size: keep repositories under a few hundred MB where possible (Lera2026 ships IGP specifications instead of ATFs
  for that reason; large distance matrices are pinned, not committed). GitHub refuses files over 100 MB.

## 2. Name it in the lib

Add the member to `BenchmarkName` in `mamut_routing_lib/enums.py` (and `InstanceOrigin` if the family has a new raw
source). Release the lib (see [Cut a release](release.md)) and bump the tools' nested lib pointer and the
superproject's pointers.

## 3. Mount it

```bash
git submodule add git@github.com:ANR-MAMUT/MAMUT-routing-<Family>.git benchmarks/<Family>
```

Prefer the `git@github.com:ANR-MAMUT/...` URL form used by the other entries; the deploy host rewrites it to HTTPS.

## 4. Describe it

- Add a ``### `Family` (ProblemType)`` section (one per problem type) to
  `src/mamut_routing_publish/site_assets/texts/mamut-routing_benchmark_families.md`. It becomes the website's family
  context page and the family page of this documentation.
- Add the license clause to `NOTICE` and the row to the README family table (and the layout notes if it is a generated collection).

## 5. Special cases

- **Materialized td models.** A TD family that ships no ATF sidecar (igp-profile like Lera2026, road-graph like
  Poryos2026 TD) is materialized at build time by `atf_cache.py`; the model tag must be in `MATERIALIZED_TD_MODELS`.
- **Route geometry.** Road-network families need their OSM extracts under `osmdata/`; the build fetches missing ones
  from the sidecar bounds unless `--no-fetch-missing-osm`.
- **Non-commercial data** (CC BY-NC): say so in `NOTICE`, the family README and the family section.

## 6. Verify and publish

```bash
uv run pytest
uv run mamut-routing-publish site build --skip-atf-cache --skip-route-geometry \
    --site-output-dir dist-preview --state-dir dist-preview-state      # a scratch state dir: a preview is not a publication
uv run mamut-routing-publish serve --site-dir dist-preview            # then open /benchmarks/<type>/<family>/ and /docs/benchmarks/families/
```

Then a real build with the caches, a release if the family is meant to be downloadable (`release build` emits one archive per family), and the deploy. Add the family to the README download hints with its size.
