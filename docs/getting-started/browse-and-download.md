# 1. Browse and download benchmarks

## On the website

The [website](/) lists every published instance with its best-known solution (BKS), a route map, the objective
contract and the publication history. Navigate problem type → family → metric variant → place → size → instance,
or filter any catalog level. An instance page links every artifact (`.vrp.json`, BKS, sidecars) and, for static
instances, offers a `.vrp ↓` chip that writes the classic CVRPLIB file in your browser.

## Read the September 2026 snapshot

The September snapshot uses the former problem-first tree. With Python 3.12 and uv, the following commands download and verify the TDVRPTW portion of Dabia2013 using the published reader.

```bash
uv venv --python 3.12 --seed .venv-mamut-012
. .venv-mamut-012/bin/activate
python -m pip install 'mamut-routing-lib[cli]==0.12.0'
mamut-routing --benchmarks-dir ./legacy-data remote --tag snapshot-2026-09-23-70ca946 fetch TDVRPTW-Dabia2013-snapshot-2026-09-23-70ca946.zip
mamut-routing --benchmarks-dir ./legacy-data remote --tag snapshot-2026-09-23-70ca946 verify --problem-type TDVRPTW --benchmark-name Dabia2013
deactivate
```

The read-only archive also preserves the former Git tree. [Archived collection](https://github.com/ANR-MAMUT/MAMUT-routing-archive-2026-11)

## Download a family-first release

The collection publishes a ZIP for each family and a checksum manifest on GitHub Releases. With library 0.13.0 installed, these commands download Sintef2008 from the latest snapshot, verify its checksum, and list its VRPTW instances. [Collection releases](https://github.com/ANR-MAMUT/MAMUT-routing/releases) · [Install the library](install.md)

```bash
mamut-routing --benchmarks-dir ./benchmarks remote fetch --benchmark-name Sintef2008
mamut-routing --benchmarks-dir ./benchmarks remote verify --benchmark-name Sintef2008
mamut-routing --benchmarks-dir ./benchmarks list --benchmark-name Sintef2008 --problem-type VRPTW
```

Each archive lands in the canonical tree (`./benchmarks/Sintef2008/…`), stamped with the snapshot it came from; fetching again replaces that directory, so keep your own files (for example BKS saved by `solve`) elsewhere or commit them first. Keep the same filters on `verify` as on `fetch`: an unfiltered `verify` checks every asset of the manifest and fails on the ones you did not download. To pin a release instead of the latest one, `--tag` is an option of `remote` itself: `mamut-routing remote --tag <tag> list`. This layout needs `mamut-routing-lib` 0.13.0 or later, which reads every family as a collection at `./benchmarks/<Family>/`. Versions before 0.12.0 extracted under `./benchmarks/<archive name>/benchmarks/…`.

!!! note "Collections"
    Every family is a collection, and its archive holds all its problem types: `remote fetch --benchmark-name Poryos2026` fetches it. A `--problem-type` filter alone selects every family archive (a `--problem-type TDVRP` fetch downloads all of them), so combine it with `--benchmark-name`. The archive lands at `./benchmarks/Poryos2026/`. Mamut2026's ten largest POI instances ship their distance matrices as sha256 pins; rebuild them with `mamut-tools generate materialize-distances` as the collection README explains. See [Release archives](../benchmarks/formats/releases.md).

## Everything, pinned to a commit, with git

For a paper or an experiment, add the repository as a submodule and initialise only the families you need. Every family is a submodule at `benchmarks/<Family>/`, so a plain clone leaves every family directory empty.

```bash
git submodule add https://github.com/ANR-MAMUT/MAMUT-routing.git external/MAMUT-routing
git -C external/MAMUT-routing -c url.https://github.com/.insteadOf=git@github.com: submodule update --init benchmarks/Mamut2026          # ~0.3 GB
git -C external/MAMUT-routing -c url.https://github.com/.insteadOf=git@github.com: submodule update --init benchmarks/Rifki2020          # one TD family
```

Sizes and licenses are on the [family pages](../benchmarks/families/index.md). Next:
[Install the Python stack](install.md).
