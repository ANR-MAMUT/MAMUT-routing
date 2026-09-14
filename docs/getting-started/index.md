# Getting started

Five short tutorials, each self-contained and runnable as written (they were run on a fresh clone before being
published). Do them in order the first time; later, jump to the one you need.

| | Tutorial | You end up with |
|---|---|---|
| 1 | [Browse and download benchmarks](browse-and-download.md) | instances and BKS on your disk, by family |
| 2 | [Install the Python stack](install.md) | `mamut-routing`, `mamut-tools`, and a developer checkout |
| 3 | [Load an instance and check a solution](load-and-check.md) | the checker's verdict and cost on a published BKS |
| 4 | [Solve with PyVRP and propose a BKS](solve-and-bks.md) | a validated solution file, stored only if it improves |
| 5 | [Export to CVRPLIB `.vrp`](export-vrp.md) | classic-format files for solvers that do not read `.vrp.json` |

Then: the [User guide](../user-guide/index.md) for the website, the workbench and instance generation; the
[Benchmarks](../benchmarks/index.md) section for what the data is; the [Maintainer guide](../maintainer-guide/index.md)
if you keep the platform running.

## Requirements

Python 3.11 or newer, and [uv](https://github.com/astral-sh/uv) (pip works too). Everything runs on Linux, macOS
and Windows; the generation tools need network access to OpenStreetMap the first time a city is fetched.
