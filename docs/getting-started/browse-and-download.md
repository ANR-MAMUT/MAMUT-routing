# 1. Browse and download benchmarks

## On the website

The [website](/) lists every published instance with its best-known solution (BKS), a route map, the objective
contract and the publication history. Navigate problem type → family → metric variant → place → size → instance,
or filter any catalog level. An instance page links every artifact (`.vrp.json`, BKS, sidecars) and, for static
instances, offers a `.vrp ↓` chip that writes the classic CVRPLIB file in your browser.

## Per family, with the CLI

Release archives are one zip per family, holding all its problem types, so you download only what you need. Install the lib with its CLI extra, then:

```bash
pip install "mamut-routing-lib[cli]"            # or: uv tool install "mamut-routing-lib[cli]"

mamut-routing remote list                                                    # archives of the latest release
mamut-routing remote list --problem-type VRPTW --benchmark-name Sintef2008  # filter
mamut-routing --benchmarks-dir ./benchmarks remote fetch \
    --problem-type VRPTW --benchmark-name Sintef2008                          # download and extract
mamut-routing --benchmarks-dir ./benchmarks remote verify \
    --problem-type VRPTW --benchmark-name Sintef2008                          # sha256 against the manifest
mamut-routing --benchmarks-dir ./benchmarks list --problem-type VRPTW        # what is on disk now
```

Each archive lands in the canonical tree (`./benchmarks/Sintef2008/…`), stamped with the snapshot it came from; fetching again replaces that directory, so keep your own files (for example BKS saved by `solve`) elsewhere or commit them first. Keep the same filters on `verify` as on `fetch`: an unfiltered `verify` checks every asset of the manifest and fails on the ones you did not download. To pin a release instead of the latest one, `--tag` is an option of `remote` itself: `mamut-routing remote --tag <tag> list`. This layout needs `mamut-routing-lib` 0.13.0 or later, which reads every family as a collection at `./benchmarks/<Family>/`. Versions before 0.12.0 extracted under `./benchmarks/<archive name>/benchmarks/…`.

!!! note "Collections"
    Every family is a collection, and its archive holds all its problem types: `remote fetch --benchmark-name Poryos2026` fetches it. A `--problem-type` filter alone selects every family archive (a `--problem-type TDVRP` fetch downloads all of them), so combine it with `--benchmark-name`. The archive lands at `./benchmarks/Poryos2026/`. Mamut2026's ten largest POI instances ship their distance matrices as sha256 pins; rebuild them with `mamut-tools generate materialize-distances` as the collection README explains. See [Release archives](../benchmarks/formats/releases.md).

## Everything, pinned to a commit, with git

For a paper or an experiment, add the repository as a submodule and initialise only the families you need. Every family is a submodule at `benchmarks/<Family>/`, so a plain clone leaves every family directory empty.

```bash
git submodule add https://github.com/ANR-MAMUT/MAMUT-routing.git external/MAMUT-routing
git -C external/MAMUT-routing submodule update --init benchmarks/Mamut2026          # ~0.3 GB
git -C external/MAMUT-routing submodule update --init benchmarks/Rifki2020          # one TD family
```

Sizes and licenses are on the [family pages](../benchmarks/families/index.md). Next:
[Install the Python stack](install.md).
