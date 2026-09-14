# Maintainer guide

Runbooks for the people who keep the platform running. Each page is one task, in the order a maintainer usually
meets them; the [Developer guide](../developer-guide/index.md) covers the code, the [Reference](../reference/index.md)
every flag.

| Task | Page |
|---|---|
| Understand the repositories, submodules and the uv workspace | [Repository topology](repository-topology.md) |
| Ship a change to an existing family (instances, sidecars, README, changelog) | [Update a benchmark family](update-a-family.md) |
| Replace a best-known solution, stamp an optimality proof, refresh route geometry | [Update or submit a BKS](update-a-bks.md) |
| Run many solver runs and turn the winners into BKS with provenance | [Run a BKS campaign](bks-campaigns.md) |
| Bring a new family or collection online | [Add a benchmark family](add-a-family.md) |
| Extend the contract with a problem type or an objective | [Add a problem type or objective](add-a-problem-type.md) |
| Generate a collection with the tools, or convert an external distribution | [Generate or convert a family](generate-a-family.md) |
| Build the website locally or for a release, with its caches | [Build the website](build-the-website.md) |
| Put a build in production, roll it back, check health | [Deploy](deploy.md) |
| Cut a versioned release with archives, tags, PyPI and citation records | [Cut a release](release.md) |
| Understand the history ledger and snapshot inventories | [Publication history and state](publication-history.md) |
| Fix the things that have already gone wrong once | [Troubleshooting](troubleshooting.md) |

!!! tip "The three invariants"
    Every runbook here protects the same three things: **the checker is the authority** (no cost is stored that it
    did not compute), **every published byte is reproducible** (sorted JSON, sha256 pins, deterministic archives),
    and **the live site is never written in place** (staging builds, atomic release swap).
