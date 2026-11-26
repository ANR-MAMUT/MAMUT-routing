# Edition r1 migration and replay

Edition `r1` identifies each instance of `mamut-routing/0.1` by a descriptor, its required sidecars and a SHA-256 digest of the materialized numerical inputs. A record's `metadata.standard.manifest_sha256` binds its routes and exact objective to that instance manifest. Pin the collection revision in your experiment and initialize the families you use. The family file `.mamut/editions/r1-index.json` lists the descriptor and manifest digests. [Installation](../../getting-started/install.md) · [Historical snapshot reader](../../getting-started/browse-and-download.md#read-the-september-2026-snapshot)

Static manifests declare the objective unit in `units.cost` and the time-window unit, when applicable, in `units.time`. For example, Mamut2026's fastest CVRP uses seconds and its shortest CVRP uses metres. A static VRPTW uses the arc matrix for both movement cost and travel time. Earlier development manifests also included the derived `cost_is_travel_time` field. Replaying an older manifest digest requires the family revision that issued it.

## Migration coverage

The November 2026 migration verified 5,048 best-known solution (BKS) records across 11 families with the native and Python Fraction evaluators. The TD columns count the migrated incumbents and their route witnesses. Each witness contains the minimum duration of a route and its earliest minimizing depot departure. A subsequent improvement can replace the routes in an individual record.

| Family | Static BKS | TD BKS | TD route witnesses |
|---|---:|---:|---:|
| Ari2018 | 0 | 320 | 1,522 |
| Blauth2024 | 0 | 40 | 611 |
| Dabia2013 | 0 | 336 | 1,640 |
| Dimacs2021 | 468 | 0 | 0 |
| Lera2026 | 0 | 960 | 35,429 |
| Mamut2026 | 330 | 0 | 0 |
| Ortec2022 | 350 | 0 | 0 |
| Poryos2026 | 360 | 720 | 15,809 |
| Rifki2020 | 0 | 360 | 2,183 |
| Sintef2008 | 468 | 0 | 0 |
| Vu2020 | 0 | 336 | 4,798 |
| **Total** | **1,976** | **3,072** | **61,992** |

## Replay a static and a time-dependent result

Run these commands from the collection root with the development library and its CLI installed. The native and Python evaluators use the exact binary64 operands stored in the edition. The static checker sums arc costs under `binary64-exact-v1`. The TD checker applies `td-binary64-exact-v1` to each route and evaluates the family objective.

```bash
static=benchmarks/Dimacs2021/VRPTW/n=100/C101
td=benchmarks/Dabia2013/TDVRPTW/n=25/C101
mamut-routing check "$static.vrp.json" "$static.bks.MonoCost.json" --json
mamut-routing check "$td.vrp.json" "$td.bks.Duration.json" --json
mamut-routing check "$td.vrp.json" "$td.bks.Duration.json" --backend python --json
```

DIMACS C101's certified cost is 8,273. Dabia C101's 4 routes have a total duration displayed as 24,709.177157546477. Compare the numerator and denominator in `metadata.standard.authoritative_cost` when comparing costs. The top-level `cost` is the nearest binary64 display, or `null` on overflow. A new solver claim of optimality identifies its solver and the family target profile separately from route feasibility and cost. [Solution fields and comparison rules](solutions.md)

## Replay a digest from before the static manifest reissue

Dimacs2021, Mamut2026, Ortec2022, Poryos2026 and Sintef2008 each include `.mamut/archives/r1-before-static-manifest-cleanup.json`. This record identifies the previous family commit, index and manifest archive. Its `overlay` entry gives the path and SHA-256 of the archive of previous files. Both sets of manifests carry the revision label `r1`. A recorded digest identifies which one an experiment used.

From a collection checkout with Dimacs2021 initialized at the reissue, this example restores the former manifests and incumbent files into a temporary directory. It verifies the archive before extraction and checks the former C101 digest and routes.

```bash
(
    set -eo pipefail
    replay=$(mktemp -d)
    git -C benchmarks/Dimacs2021 archive HEAD | tar -x -C "$replay"
    cd "$replay"
    overlay=$(python - <<'PY'
import hashlib
import json
from pathlib import Path

info = json.loads(Path(".mamut/archives/r1-before-static-manifest-cleanup.json").read_bytes())["overlay"]
with Path(info["path"]).open("rb") as stream:
    if hashlib.file_digest(stream, "sha256").hexdigest() != info["sha256"]:
        raise SystemExit("Predecessor overlay digest mismatch")
print(info["path"])
PY
    )
    tar -xzf "$overlay"
    instance=VRPTW/n=100/C101
    mamut-routing verify-manifest "$instance.vrp.json" --sha256 df691085577f72414ce84bc1eecd259a2e43aae6e0186e2ca542f86fb10e7f23
    mamut-routing check "$instance.vrp.json" "$instance.bks.MonoCost.json" --json
)
```

For another instance, use its descriptor, incumbent and former digest. The copied family supplies its sidecars and recipes. When an input is distributed as a pin, materialize it before running the verifier.

## Rebuild omitted inputs

For Mamut2026, the installed tools can reconstruct a pinned distance matrix from its published road graph. The example below visits only the fastest-metric Amiens descriptor. A new matrix is written after the digest matches, and an existing file yields `kept`. Run `verify-manifest` to check the inputs in either case.

```bash
dir=benchmarks/Mamut2026/CVRP/fastest/amiens/n=156
mamut-tools generate materialize-distances "$dir"
mamut-routing verify-manifest "$dir"/mamut-amiens-n156-k7-poi/mamut-amiens-n156-k7-poi.vrp.json
```

For Blauth2024, the 1,000- and 2,000-customer descriptors pin ATF sidecars that are distributed through their upstream source. Materialize the required cities and sizes in a separate directory and copy the sidecar into its published family path. The 10-customer Berlin example exercises the same converter. Set `size` to the number of customers you need.

```bash
git clone https://gitlab.com/muelleratorunibonnde/vrptdt-benchmark.git
git -C vrptdt-benchmark checkout 45f8f57e4d643af5c4e7641e77c2aad197233dc2
size=10
mamut-tools convert blauth2024 vrptdt-benchmark --cities berlin --sizes "$size" --output-dir regenerated
sidecar="sidecars/n=$size/Blauth-berlin.atf.json.gz"
mkdir -p "benchmarks/Blauth2024/sidecars/n=$size"
test -f "benchmarks/Blauth2024/$sidecar" || cp "regenerated/$sidecar" "benchmarks/Blauth2024/$sidecar"
mamut-routing verify-manifest "benchmarks/Blauth2024/TDVRPTW/n=$size/Blauth-berlin.vrp.json"
```

The converter reads the upstream delivery instance and travel-time matrix. The family README gives the source attribution, license and pins. [Blauth2024 family](https://github.com/ANR-MAMUT/MAMUT-routing-Blauth2024)
