# Dabia2013 TDVRPTW benchmark family (TD-IGP-Solomon)

Canonical MAMUT-routing curation of the classic Duration-Minimization TDVRPTW benchmark introduced by Dabia et al. (2013): Solomon 1987 instances (25/50/100 customers) with IGP time-dependent travel times (Ichoua et al. 2003), as distributed with the open-source solver of Lera-Romero et al. (2020).

## Format

Each instance ships three artifacts per size bucket `n=<customers>`:

- `<Name>.vrp.json` — raw instance data in the MAMUT shape: depot index 0 (no duplicated end depot, contrary to historic distributions), `num_customers` counts customers only, mandatory `coordinates`, `horizon`, and a `td` block referencing the ATF sidecar with its storage-independent sha256.
- `<Name>.atf.json` (plain, n < 50) or `<Name>.atf.json.gz` (n ≥ 50) — the canonical ground truth: one arrival-time NDCPWLF per arc of the complete graph, exact consolidation of the raw IGP data. Conventions: breakpoints exactly where departure or arrival crosses a speed-zone boundary; the last zone's speed extends beyond the horizon so every ATF is total on `[0, T]`.
- `<Name>.bks.Duration.json` — best known solution under the `Duration` objective. Costs are the authoritative output of the pure-Python canonical checker (`mamut_routing_lib.td.check_td_solution`): exact IEEE-754 double arithmetic, no epsilon thresholds, routes in canonical order (sorted by first customer), total summed in that order. Seeded from the published Lera-Romero et al. (2020) solutions, all re-validated by the checker (146/146 feasible; several contain arrivals exactly on time-window deadlines, which fragile recomputation pipelines misreport as infeasible).

Population pipeline: `populate_td_dabia2013` v1, one-shot curation tooling maintained outside this repository (links to the migration scripts will be published with the benchmark paper); it cross-validates every consolidated ATF against direct Ichoua evaluation and reloads every written artifact through the full validation path. The `generator` block of every artifact records the pipeline name and version.

## Provenance and licensing

Instance definitions derive from Solomon (1987) and the TD extension of Dabia et al. (2013) / Ichoua et al. (2003); the raw JSON sources are those shipped with Lera-Romero et al. (2020), https://doi.org/10.1002/net.21937. MAMUT-routing-authored curation artifacts are distributed under the repository's MIT license; this notice does not relicense the underlying third-party benchmark definitions.
