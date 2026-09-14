# Add a problem type or objective

There is no plugin registry: problem types and objectives are enumerations of the contract, and the dispatch is by
directory layout and model class. Adding one is a versioned contract change across the stack. Read the
[Formats](../benchmarks/formats/index.md) page first.

## In `mamut-routing-lib`

| Concern | Where |
|---|---|
| the name | `ProblemType` / `ObjectiveFunction` in `enums.py` |
| the instance model | `models.py` (static) or `td/models.py` (time-dependent), pydantic with `extra="forbid"`, format tags and versions for any new sidecar |
| layout parsing | `artifacts.parse_layout` and `parse_collection_layout` derive the problem type from the first path segment |
| loading | `artifacts.load_benchmark_instance` picks the model; `instance_problem_type` maps back by `isinstance` |
| validation | `checker.check_solution` / `td/checker.check_td_solution` and `is_better_solution` for the objective order |
| BKS files | `<base>.bks.<Objective>.json`; the store functions in `bks.py` / `td/bks.py` |
| CLI filters | the shared `--problem-type` / `--objective` options in `cli.py` |
| export | `cvrplib.py` if the classic format can express it |
| tests | one fixture instance per problem type in `tests/`, checker tests for every failure status |

Bump the lib version; it is a contract change.

## In `MAMUT-routing-tools`

Generation twins (`generate derive-*`), the TD traffic bridge, the solver wrapper (`solve` only knows PyVRP for
static and KAYROS for TD Duration), the workbench's instance readers.

## In the publisher and the website

`site_payloads.py` builds one payload kind per page (`problem_index`, `family_index`, ..., `instance_page`,
`objectives_page`); a new problem type needs its index route, the objectives page text and the instance page
descriptors. `site.js` renders payloads client-side, so any new field needs a renderer. The release builder needs
nothing: it archives by (type, family).

## In the documentation

The [Benchmarks](../benchmarks/index.md) table, the Formats page, and the family sections. The family pages regenerate.

## Write the report

A new problem type or objective deserves a dated report in `docs/reports/` stating the pricing rule, the tie-breaks
and the reference implementation, so later checkers can be validated against it.
