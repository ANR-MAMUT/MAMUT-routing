"""Stage-2 (VRPTW) synthesis of service times and time windows (v2, Stream 12').

The single implementation of the family's name-seeded synthesis
(language-boundary tier 2): windows are route-centered over the **static
free-flow fastest** travel times of the base, seeded from the **base name**,
so one service-time set and one TW set exist per base and are shared verbatim
by the VRPTW instance and every TDVRPTW subinstance. The v1 per-variant,
TD-anchored synthesis is retired: anchoring windows on each traffic variant's
own arrivals partially cancelled the traffic effect the family is built to
measure.

Values are integer seconds (exact in binary64). Feasibility bounds at free
flow: a window ``[e, l]`` guarantees ``l >= t_0i`` (a vehicle leaving the
depot at the horizon start reaches the customer by ``l``) and
``l + s_i + t_i0 <= horizon end`` (starting service at ``l`` returns in
time). Stage 3 (``build-td``) then audits these windows under every traffic
overlay and applies the minimal shared deadline lift, which only relaxes
deadlines, so free-flow feasibility is preserved.

All randomness comes from ``random.Random`` seeded per base; the windows are
shipped data, never re-derived at load time.
"""

from __future__ import annotations

import math
from random import Random

HORIZON_START = 0.0
HORIZON_END = 86400.0

SERVICE_MEAN_RATIO = 0.01
SERVICE_MEAN_RATIO_STD = 0.005
TW_WIDTH_RATIO_MEAN = 0.2
TW_WIDTH_RATIO_STD = 0.08


def _clamp(value: float, lo: float, hi: float) -> float:
    return lo if value < lo else hi if value > hi else value


def synthesize_service_times(rng: Random, num_customers: int) -> list[int]:
    """Gaussian integer service times, mean ~1% of the horizon."""
    horizon = HORIZON_END - HORIZON_START
    mean_ratio = _clamp(rng.gauss(0.0, 1.0) * SERVICE_MEAN_RATIO_STD + SERVICE_MEAN_RATIO, 0.001, 0.2)
    mean_service = horizon * mean_ratio
    upper = max(1, int(mean_service * 2))
    service_times = [0]
    for _ in range(num_customers):
        sampled = rng.gauss(0.0, 1.0) * (mean_service / 2.0) + mean_service
        service_times.append(int(_clamp(float(round(sampled)), 1.0, float(upper))))
    return service_times


def nearest_neighbour_visit_times(
    fastest: list[list[float]], service_times: list[int]
) -> list[float]:
    """Greedy nearest-neighbour tour over the static fastest times from the
    depot at the horizon start; returns the simulated arrival time at each
    node (depot: horizon start). Ties break on the smallest node index."""
    num_nodes = len(fastest)
    arrivals = [HORIZON_START] * num_nodes
    visited = [False] * num_nodes
    visited[0] = True
    current = 0
    clock = HORIZON_START
    for _ in range(num_nodes - 1):
        best = -1
        best_travel = float("inf")
        for j in range(1, num_nodes):
            if visited[j]:
                continue
            travel = fastest[current][j]
            if travel < best_travel:
                best_travel = travel
                best = j
        clock += best_travel
        arrivals[best] = clock
        clock += service_times[best]
        visited[best] = True
        current = best
    return arrivals


def synthesize_time_windows(
    rng: Random,
    fastest: list[list[float]],
    service_times: list[int],
    visit_times: list[float],
) -> list[tuple[int, int]]:
    """Route-centered integer windows repaired to the free-flow feasibility bounds."""
    horizon = HORIZON_END - HORIZON_START
    num_nodes = len(fastest)
    windows: list[tuple[int, int]] = [(int(HORIZON_START), int(HORIZON_END))]
    for i in range(1, num_nodes):
        earliest_arrival = fastest[0][i]
        latest_service_start = HORIZON_END - fastest[i][0] - service_times[i]
        lo = math.ceil(earliest_arrival)
        hi = math.floor(latest_service_start)
        if hi < lo:
            raise ValueError(
                f"customer {i} cannot be served within the horizon at free flow: "
                f"earliest arrival {earliest_arrival}, latest feasible service start "
                f"{latest_service_start}"
            )
        width_ratio = _clamp(rng.gauss(0.0, 1.0) * TW_WIDTH_RATIO_STD + TW_WIDTH_RATIO_MEAN, 0.01, 1.0)
        width = max(1.0, float(round(horizon * width_ratio)))
        center = visit_times[i]
        latest = int(_clamp(float(round(center + width / 2.0)), float(lo), float(hi)))
        earliest = int(_clamp(float(round(center - width / 2.0)), HORIZON_START, float(latest)))
        windows.append((earliest, latest))
    return windows
