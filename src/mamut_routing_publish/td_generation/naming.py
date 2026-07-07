"""Instance naming and on-disk layout of the generated TD family.

Names are lowercase and self-describing:
``mamut-<place>-n<N>-<model>-<intensity>-<method>``, e.g.
``mamut-lyon-n100-bpr-heavy-poi``. Instances live in the 7-part Mamut2026
layout with the ``fastest`` metric slot (TD travel derives from
free-flow-fastest paths):
``<TDVRP|TDVRPTW>/Mamut2026/fastest/<place>/n=<N>/<instance>/<files>``.
"""

from __future__ import annotations

from pathlib import Path

TD_FAMILY = "Mamut2026"
TD_METRIC = "fastest"


def td_instance_name(place: str, n: int, model: str, intensity: str, method: str) -> str:
    return f"mamut-{place}-n{n}-{model}-{intensity}-{method}".lower()


def td_instance_dir(root: str | Path, problem_type: str, place: str, n: int, instance_name: str) -> Path:
    if problem_type not in ("TDVRP", "TDVRPTW"):
        raise ValueError(f"problem_type must be TDVRP or TDVRPTW, got {problem_type!r}")
    return Path(root) / problem_type / TD_FAMILY / TD_METRIC / place / f"n={n}" / instance_name
