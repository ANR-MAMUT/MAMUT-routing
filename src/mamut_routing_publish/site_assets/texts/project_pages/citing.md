# Citing MAMUT-routing

If you use `MAMUT-routing`, its benchmark artifacts, or accompanying tools such as the [`mamut-routing-lib` Python library and CLI](https://github.com/ANR-MAMUT/MAMUT-routing-lib), please cite the repository and identify the exact release or Git commit used in your experiments. Benchmark-family source publications should also be cited when applicable.

## GitHub "Cite this repository"

The repository provides a machine-readable [`CITATION.cff`](https://github.com/ANR-MAMUT/MAMUT-routing/blob/main/CITATION.cff) file. GitHub uses this file for its "Cite this repository" action in the repository sidebar and can produce ready-to-copy APA and BibTeX citations from the maintained project metadata.

For reproducibility, include the MAMUT-routing version and, when possible, the full Git commit alongside the generated citation. This identifies the precise benchmark, BKS, objective-contract, and checker state used by an experiment.

## Software Heritage

The [Software Heritage rolling pointer](https://archive.softwareheritage.org/browse/snapshot/log/?origin_url=https://github.com/ANR-MAMUT/MAMUT-routing) follows the latest archived visit of the MAMUT-routing GitHub origin. Use it to browse the evolving archived repository history.

For a citation that must identify an immutable archived state, use the Software Heritage persistent identifier recorded in `CITATION.cff`. The v0.1.0 release is archived as [`swh:1:rev:5dd0e60f69816a5e6afa3fa8c3c95902c5de3245`](https://archive.softwareheritage.org/swh:1:rev:5dd0e60f69816a5e6afa3fa8c3c95902c5de3245;origin=https://github.com/ANR-MAMUT/MAMUT-routing;visit=swh:1:snp:81443df7dfea454bbac85e88446639666fffa44b).

## What to cite

- Cite `MAMUT-routing` for the curated artifact tree, benchmark contracts, BKS provenance, validation tooling, and website publication.
- Cite the original benchmark-family publication or data source when using a historical family distributed by MAMUT-routing.
- Cite [`mamut-routing-lib`](https://github.com/ANR-MAMUT/MAMUT-routing-lib) separately when its Python API, CLI, loaders, or checkers are a material part of the experimental workflow.
- Record the exact objective function and metric variant because different MAMUT-routing artifacts for the same base instance can intentionally represent different optimization contracts.

## Additional publication records

HAL, DOI, and project-publication records will be linked here when available. The GitHub citation metadata and Software Heritage identifiers remain the current software-citation references.
