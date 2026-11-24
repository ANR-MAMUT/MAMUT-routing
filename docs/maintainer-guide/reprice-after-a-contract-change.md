# Re-price after a checker-contract change

This procedure reproduces the v0.12 migration of legacy TD records under `td-fold/2`. Current v0.13 records use `td-binary64-exact-v1` and bind the certified result to its edition manifest. The legacy `reprice-td` command refuses a marked exact record. [Historical TD fold](../benchmarks/formats/time-dependent.md#historical-td-fold-in-v012)

## 1. Point every checkout at the new lib

Both lib checkouts (`MAMUT-routing-lib/` and `MAMUT-routing-tools/MAMUT-routing-lib/`, the one the venv imports) must be on the same commit, and every family repository on a fresh branch from its pinned commit:

```bash
git -C MAMUT-routing-tools/MAMUT-routing-lib fetch ../../MAMUT-routing-lib <branch>
git -C MAMUT-routing-tools/MAMUT-routing-lib switch --detach FETCH_HEAD
git -C benchmarks/Rifki2020 switch -c <branch>                # and each TD family
```

## 2. Dry run and review

```bash
for d in benchmarks/*/TDVRP benchmarks/*/TDVRPTW; do
  uv run mamut-routing bks reprice-td "$d" --dry-run --jobs 8 --allow-missing-sidecars \
      --report "reprice-$(echo "$d" | tr / -).json"
done
```

`reprice-td` materializes only the arcs the stored routes use (sidecar, `igp-profile` or road-graph), prices each
BKS in canonical order and reports one action per file: `unchanged`, `would-reprice`, `skipped-missing-sidecar`,
`infeasible`, `stamp-conflict` or `error`. Before writing, check that:

- there is no `infeasible`, `stamp-conflict` or `error` row (the exit status is 1 otherwise);
- stamped moves stay within 1e-6 (the tool refuses larger ones on a stamped BKS);
- the large moves are the ones the contract change explains. In 2026-09 there were 870 cost moves in 3 072 files,
  all float rounding except Rifki2020 Rifki-30 (8292 → 8267) and Rifki-13 n=60 (17386 → 17385), both on stepwise
  travel times;
- skipped files are the expected ones (Blauth2024 n=1000/2000 ship no sidecar).

## 3. Write, re-check, commit

```bash
uv run mamut-routing bks reprice-td "$d" --write --jobs 8 --note-date <YYYY-MM-DD> --report ...
uv run mamut-routing bks reprice-td "$d" --dry-run        # must report every file unchanged
```

The write pass rewrites `cost`, `metadata.validated_cost`, `metadata.route_durations` and `metadata.route_departure_times` where they moved, adds `metadata.repriced` when the cost moved, and on a stamped BKS sets `optimality.proven_optimum` to the new cost with a `note` (proof obtained under the old contract, re-certification pending). Commit each family repository with a CHANGELOG entry giving the counts, the notable moves and the stamp notes. Then bump the gitlinks and run the root tests: `tests/test_td_fold_route_vectors.py` re-prices the published route vectors and `tests/test_relaxation_invariants.py` screens the relaxation twins.

## 4. After publication

- The website's publication history lists these BKS as **re-priced**, not improved or regressed: the inventory
  matches them on the `repriced` marker or on an unchanged routes fingerprint.
- Solvers that price routes themselves (KAYROS) must implement the new contract before their next campaign;
  refresh `MAMUT-routing-lib/tests/fixtures/td/fold-v2-vectors.json` for them, since until then about a quarter
  of their TD submissions are refused.
- Re-certify the stamped BKS under the new contract when compute is available, then drop the pending notes.
