# TD schedule derivation: horizon-boundary floating-point overshoot (cosmetic)

**Date:** 2026-07-07
**Component:** `mamut-routing-publish` site publisher — TD per-stop schedule reconstruction
**Severity:** cosmetic (site rendering only; no impact on benchmark data, BKS values, or the solution checker)
**Status:** fixed at the display layer; checker and PWLF core deliberately untouched

## Summary

Rebuilding the static benchmark website emitted two `UserWarning`s of the form *"Unable to derive the TD schedule for … : x=1501.0000000000005 is outside the domain of the function"*, one for each of two horizon-tight `Lera2026` instances. The consequence was purely cosmetic: those two instances rendered without their per-stop schedule table and route ready-time-function plot, while their best-known-solution value, routes, and every other page element rendered normally. The cause is IEEE-754 rounding drift in a **display-only forward reconstruction** of the schedule, which can present a departure time a fraction of a ULP past an arc arrival-time-function's domain edge. The fix clamps such dust-scale overshoot back onto the domain boundary before evaluation, in the publisher only. The exact solution checker and the deliberately epsilon-free PWLF core are not modified.

## Symptom

Observed during `mamut-routing-publish site build`:

```
UserWarning: Unable to derive the TD schedule for benchmarks/TDVRP/Lera2026/S2/n=400/Lera-C1_4_8-S2.bks.Duration.json: x=1501.0000000000005 is outside the domain of the function
UserWarning: Unable to derive the TD schedule for benchmarks/TDVRP/Lera2026/S3/n=200/Lera-C1_2_1-S3.bks.Duration.json: x=1351.0000000000005 is outside the domain of the function
```

Exactly two instances across the full TD corpus (≈3600 TD instance pages), both in the `Lera2026` family. In each case the offending `x` equals the instance planning horizon plus `~5e-13`: the cached arrival-time functions carry `horizon = [0, 1501]` and `[0, 1351]` respectively, so `x = horizon + 5e-13`.

## Root cause

The publisher reconstructs each TD solution's per-stop schedule table by **forward point-evaluation** (`_build_td_schedules` in `site_payloads.py`). Starting from the checker's earliest optimal depot departure `t*_r`, it walks the route arc by arc, at each stop evaluating the canonical arc arrival-time function (an `NDCPWLF`) at the running time `current`, then advancing `current` by wait and service:

```
current = departure_time                                  # = t*_r
for vertex in route:
    arrival  = atfs.arcs[(previous, vertex)].evaluate(current)
    current  = max(arrival, earliest) + service_times[vertex]
return_arrival = atfs.arcs[(previous, depot)].evaluate(current)
```

Each arc `NDCPWLF` is defined over the departure axis `[0, horizon]` (`xs[-1] == horizon`), and `NDCPWLF.evaluate` is intentionally strict with **no tolerance**: it raises `PWLFError` for `x < xs[0]` or `x > xs[-1]`. This strictness is a deliberate design property of the PWLF module, which is the pure-Python canonical reference for the checker's function algebra and is kept epsilon-free so it can be reimplemented independently and produce bit-identical results.

The forward reconstruction reaches its final time by **accumulating** one rounding error per stop (arrival, `max` with the time window, `+ service_time`), across up to 400 stops. For a route that saturates the planning horizon — i.e. whose last feasible departure/return lands *exactly* on `horizon` in exact arithmetic — this accumulated drift can push the reconstructed `current` to `horizon + ε` (here `ε ≈ 5e-13`, ULP-scale at magnitude ~1500). The strict `x > xs[-1]` check then fires and the schedule derivation for that instance aborts, is caught, and downgrades to the `UserWarning` above, dropping only the schedule table and δ_r plot.

The value *at* the boundary is well-defined — `evaluate(horizon)` returns `ys[-1]` — so the correct schedule is recoverable simply by treating a time within rounding distance of the edge as being *on* the edge.

## Why the solution checker is unaffected

The checker does not use this forward reconstruction. It computes each route's ready-time function `δ_r` by the exact PWLF fold (composition + min-shift), a structurally different computation whose rounding path stays within the domain. The reconstruction here exists solely to render a human-readable per-stop table on the website; the two instances remain valid, checker-accepted best-known solutions regardless. This is why the fix belongs strictly in the publisher and not in the shared library.

## Why only two instances

Two independent conditions must coincide, which is why this is a boundary coincidence rather than a family-wide defect:

1. **The route must saturate the horizon** — its final arc time must land *at* `horizon`, not comfortably below it. The overwhelming majority of routes finish strictly inside the domain, so `current` never approaches `xs[-1]` and no boundary is in play.
2. **The accumulated drift must round *upward*.** Even among horizon-pinned routes, the drift is as likely to land at `horizon − ε` or exactly `horizon` (both in-domain, no error) as at `horizon + ε`. Only the upward-rounding case exceeds the strict bound.

The intersection of these across the corpus is tiny — here exactly two instances, both in `Lera2026`, the family with the tightest horizons where routes are most likely to press right up against the planning horizon `T`. The shared signature `x = horizon + 5e-13` on both is the fingerprint of precisely this mechanism.

## Decision and fix

**Decision:** absorb the dust at the display layer, keep the checker and PWLF core exact and strict.

The fix could conceptually be phrased as "widen the last piece's domain by an epsilon," but placing any tolerance inside `NDCPWLF.evaluate` would erode the exactness guarantee the checker depends on. Instead the tolerance lives entirely in the publisher's reconstruction, where the concern is cosmetic:

- A small helper `_evaluate_on_domain(fn, x)` clamps `x` back onto `fn`'s domain edge when it overshoots by no more than a dust tolerance `_TD_SCHEDULE_DOMAIN_TOL = 1e-6`, then calls `fn.evaluate`. The two point-evaluations in `_build_td_schedules` route through it.
- The tolerance is ~6 orders of magnitude above the observed drift (`5e-13`) yet far below any physically meaningful time increment in these instances, so a *genuine* out-of-domain time (a real infeasibility, which would overshoot by fractions of a time unit or more) still raises `PWLFError` loudly and is not masked.

This makes the per-stop schedule table render correctly for the affected instances — it is a correctness improvement for the display, not a suppression of the warning.

### Changes

- `src/mamut_routing_publish/site_payloads.py`: added `_TD_SCHEDULE_DOMAIN_TOL` and `_evaluate_on_domain`; routed the two arc evaluations in `_build_td_schedules` through the helper.
- `tests/test_site_payloads.py`: added `test_evaluate_on_domain_absorbs_horizon_ulp_overshoot`, asserting that (a) interior points are unchanged, (b) a `horizon + 5e-13` overshoot returns the boundary image instead of raising, (c) the lower edge is clamped symmetrically, and (d) an overshoot well beyond the tolerance still raises `PWLFError`.

### Explicitly not changed

- `mamut-routing-lib` `NDCPWLF` / `pwlf.py`: remains epsilon-free and strict.
- The TD solution checker and the fold used to compute `δ_r`, `t*_r`, `Δ*_r`.
- Any benchmark instance, arrival-time function, or best-known-solution artifact.

## Verification

Full `site build` after the fix (`generated_files=9313`, up from `9309` before the fix): the two `UserWarning`s no longer appear (`grep -c` = 0), no traceback, and the two formerly-failing instances now emit their `route-functions.Duration.json` payloads and render their per-stop schedule tables. The four additional generated files are the schedule/route-function payloads for the two recovered instances (both problem-type variants). The unit test `test_evaluate_on_domain_absorbs_horizon_ulp_overshoot` passes.
