"""No published BKS of a relaxation may be worse than the BKS of its restriction.

Every TDVRPTW BKS is a feasible TDVRP solution of no larger duration (FIFO
arrival-time functions, the TDVRP twin drops the windows), and every
collection VRPTW BKS (any time-window set) is a CVRP solution of the same cost
on the same metric. The 2026-09 audit found 40 Poryos2026 TDVRP BKS and one
CVRP BKS beaten by their twin's routes; this screens every pair on the stored
values (exact decimals, ``mamut_routing_lib.relaxation``) plus the twins'
structural identity, and names the offending pairs.

Pricing the strict routes on the relaxation (``priced=True``) is the stronger
check the twin cross-evaluation campaign runs; it needs the ATFs, so it is not
repeated here.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mamut_routing_lib.relaxation import check_relaxation_pair, relaxation_twin

REPO_ROOT = Path(__file__).resolve().parents[1]
BENCHMARKS = REPO_ROOT / "benchmarks"


def _strict_bks_files() -> list[Path]:
    if not BENCHMARKS.is_dir():
        return []
    found = []
    for path in sorted(BENCHMARKS.rglob("*.bks.*.json")):
        base = path.name.partition(".bks.")[0]
        if relaxation_twin(path.with_name(f"{base}.vrp.json")) is not None:
            found.append(path)
    return found


STRICT_BKS = _strict_bks_files()


@pytest.mark.skipif(not STRICT_BKS, reason="no relaxation twins (benchmark satellites not checked out)")
def test_no_relaxation_bks_is_worse_than_its_restriction() -> None:
    inverted: list[str] = []
    structural: list[str] = []
    screened = 0
    for strict_bks in STRICT_BKS:
        check = check_relaxation_pair(strict_bks)
        if check is None:
            continue
        screened += 1
        relative = strict_bks.relative_to(BENCHMARKS).as_posix()
        if check.issues:
            structural.append(f"{relative}: {', '.join(check.issues)}")
        elif check.inverted:
            inverted.append(f"{relative}: relaxation {check.relaxed_cost} > {check.strict_cost}")
    assert screened, "no twin pair has a BKS on both sides"
    assert not structural, f"{len(structural)} twin pairs are not relaxations: {structural[:5]}"
    assert not inverted, f"{len(inverted)} of {screened} relaxation BKS are worse than their restriction: {inverted[:10]}"
