# 1. Browse and download benchmarks

## On the website

The [website](/) lists every published instance with its best-known solution (BKS), a route map, the objective
contract and the publication history. Navigate problem type → family → metric variant → place → size → instance,
or filter any catalog level. An instance page links every artifact (`.vrp.json`, BKS, sidecars) and, for static
instances, offers a `.vrp ↓` chip that writes the classic CVRPLIB file in your browser.

## Per family, with the CLI

Release archives are one zip per (problem type, family), plus one zip per family-first collection (Poryos2026,
Mamut2026), so you download only what you need. Install the lib with its CLI extra, then:

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

Keep the same filters on `verify` as on `fetch`: an unfiltered `verify` checks every asset of the manifest and
fails on the ones you did not download. To pin a release instead of the latest one, `--tag` is an option of
`remote` itself: `mamut-routing remote --tag <tag> list`.

!!! note "Collections"
    A collection archive holds every problem type of the family, so select it by family alone:
    `remote fetch --benchmark-name Poryos2026` (adding `--problem-type` filters it out). Mamut2026's ten largest
    POI instances ship their distance matrices as sha256 pins; rebuild them with `mamut-tools generate
    materialize-distances` as the collection README explains. See [Release archives](../benchmarks/formats/releases.md).

## Everything, pinned to a commit, with git

For a paper or an experiment, add the repository as a submodule and initialise only the families you need. A plain
clone leaves the satellite directories empty; the default families (Sintef2008, Dimacs2021, Ortec2022, Dabia2013)
are in the repository itself.

```bash
git submodule add https://github.com/ANR-MAMUT/MAMUT-routing.git external/MAMUT-routing
git -C external/MAMUT-routing submodule update --init benchmarks/Mamut2026          # ~0.3 GB
git -C external/MAMUT-routing submodule update --init benchmarks/TDVRPTW/Rifki2020  # one TD family
```

Sizes and licenses are on the [family pages](../benchmarks/families/index.md). Next:
[Install the Python stack](install.md).
