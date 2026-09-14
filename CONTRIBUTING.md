# Contributing to MAMUT-routing

Thank you for helping. MAMUT-routing is four repositories (this one, `MAMUT-routing-lib`, `MAMUT-routing-tools`
and the benchmark satellites) with one contract; the
[documentation](https://mamut-routing.univ-ubs.fr/docs/) has the guides, this page has the rules.

## What is welcome

- **Better solutions.** Send the solution file (routes) in an issue or a pull request on the family's repository;
  we run the checker and store the validated cost. Never edit a BKS file by hand.
- **New benchmark material**: families, problem classes, objective functions. Open an issue first so the contract
  change (an enum in the lib, a section in the family texts, a license clause) is agreed before the data lands.
- **Fixes and features** in the lib, the tools, the publisher and the website.
- **Documentation**: every page under `docs/` is a pull request away; generated pages say where their source is.

## Ground rules

1. **The checker is the authority.** Costs stored anywhere are checker costs; a change to a checker is a contract
   change with a version bump and a report in `docs/reports/`.
2. **Every published byte is reproducible.** Sorted JSON keys, sha256-pinned sidecars, deterministic archives,
   seeded generation. Tests enforce byte-identity where it matters (`.vrp` export, route geometry).
3. **Satellites are optional.** Code, tests, builds and docs must work with empty satellite directories.
4. **Data licenses travel with the data.** A family `LICENSE` with an `SPDX-License-Identifier` first line, a clause
   in `NOTICE`, and the license paragraph in the family README.
5. **Decisions get a dated report** (`docs/reports/YYYY-MM-DD-<slug>.md`), never a rewrite of an older one.

## Workflow

```bash
git clone git@github.com:ANR-MAMUT/MAMUT-routing.git && cd MAMUT-routing
git submodule update --init --recursive MAMUT-routing-lib MAMUT-routing-tools
uv sync
uv run pytest                       # publisher + lib
uv run mkdocs build --strict        # documentation
```

Branch from `main`, keep pull requests focused, describe the *why*. Commits that touch a submodule pointer say which
commit and why. The `Docs` workflow must pass; the tools' own CI runs on their repository.

## Authorship

Contributors are listed in [AUTHORS.md](AUTHORS.md); say in your pull request how you want to be credited.
