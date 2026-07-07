"""TD-aware synthesis of service times and time windows.

Port of the workbench VRPTW stage's ``route_centered`` method
(``webapp/site_api.jl``) with time-dependent pricing: the nearest-neighbour
tour and the simulated visit times are computed on the materialized
arrival-time functions instead of a static matrix, and the feasibility
bounds used by the repair are the TD ones (earliest arrival from the depot
departing at the horizon start; latest service start that still reaches the
depot by the horizon end through the time-dependent return leg).

All randomness comes from ``random.Random`` seeded per instance, so the
synthesis is deterministic; the resulting windows are shipped data (never
re-derived at load time).
"""

from __future__ import annotations

from bisect import bisect_right
from random import Random

from mamut_routing_lib.td import InstanceATFs, NDCPWLF

HORIZON_START = 0.0
HORIZON_END = 86400.0

SERVICE_MEAN_RATIO = 0.01
SERVICE_MEAN_RATIO_STD = 0.005
TW_WIDTH_RATIO_MEAN = 0.2
TW_WIDTH_RATIO_STD = 0.08


def _clamp(value: float, lo: float, hi: float) -> float:
    return lo if value < lo else hi if value > hi else value


def synthesize_service_times(rng: Random, num_customers: int) -> list[float]:
    """Gaussian service times, mean ~1% of the horizon (VRPTW-stage semantics)."""
    horizon = HORIZON_END - HORIZON_START
    mean_ratio = _clamp(rng.gauss(0.0, 1.0) * SERVICE_MEAN_RATIO_STD + SERVICE_MEAN_RATIO, 0.001, 0.2)
    mean_service = horizon * mean_ratio
    upper = max(1.0, float(int(mean_service * 2)))
    service_times = [0.0]
    for _ in range(num_customers):
        sampled = rng.gauss(0.0, 1.0) * (mean_service / 2.0) + mean_service
        service_times.append(_clamp(float(round(sampled)), 1.0, upper))
    return service_times


def _travel(atfs: InstanceATFs, i: int, j: int, clock: float) -> float:
    """TD travel time i -> j departing at ``clock`` (clamped into the horizon:
    past-horizon departures reuse the last-piece travel time, which the
    extended-speed construction makes the late-night steady state)."""
    atf = atfs.arcs[(i, j)]
    departure = _clamp(clock, atf.xs[0], atf.xs[-1])
    return atf.evaluate(departure) - departure


def nearest_neighbour_visit_times(atfs: InstanceATFs, service_times: list[float]) -> list[float]:
    """Greedy TD nearest-neighbour tour from the depot at the horizon start;
    returns the simulated arrival time at each node (depot: horizon start).
    Ties break on the smallest node index."""
    num_nodes = atfs.num_customers + 1
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
            travel = _travel(atfs, current, j, clock)
            if travel < best_travel:
                best_travel = travel
                best = j
        clock += best_travel
        arrivals[best] = clock
        clock += service_times[best]
        visited[best] = True
        current = best
    return arrivals


def latest_departure_at_or_below(atf: NDCPWLF, arrival_bound: float) -> float:
    """Largest departure ``x`` in the ATF domain with ``atf(x) <= arrival_bound``."""
    if atf.ys[0] > arrival_bound:
        raise ValueError(f"arrival bound {arrival_bound} unreachable (min arrival {atf.ys[0]})")
    k = bisect_right(atf.ys, arrival_bound) - 1
    if k >= atf.num_breakpoints() - 1:
        return atf.xs[-1]
    x_lo, x_hi = atf.xs[k], atf.xs[k + 1]
    y_lo, y_hi = atf.ys[k], atf.ys[k + 1]
    if x_lo == x_hi or y_hi == y_lo:
        return x_lo
    return x_lo + (arrival_bound - y_lo) / (y_hi - y_lo) * (x_hi - x_lo)


def synthesize_time_windows(
    rng: Random,
    atfs: InstanceATFs,
    service_times: list[float],
    visit_times: list[float],
) -> list[tuple[float, float]]:
    """Route-centered windows repaired to TD feasibility bounds.

    Every customer window ``[e, l]`` guarantees individual feasibility: a
    vehicle leaving the depot at the horizon start arrives no later than
    ``l`` (``l >= alpha_0i(start)``), and starting service at ``l`` still
    reaches the depot by the horizon end through the TD return leg.
    """
    horizon = HORIZON_END - HORIZON_START
    num_nodes = atfs.num_customers + 1
    windows: list[tuple[float, float]] = [(HORIZON_START, HORIZON_END)]
    for i in range(1, num_nodes):
        earliest_arrival = atfs.arcs[(0, i)].evaluate(HORIZON_START)
        latest_return_departure = latest_departure_at_or_below(atfs.arcs[(i, 0)], HORIZON_END)
        latest_service_start = latest_return_departure - service_times[i]
        if latest_service_start < earliest_arrival:
            raise ValueError(
                f"customer {i} cannot be served within the horizon: earliest arrival "
                f"{earliest_arrival}, latest feasible service start {latest_service_start}"
            )
        width_ratio = _clamp(rng.gauss(0.0, 1.0) * TW_WIDTH_RATIO_STD + TW_WIDTH_RATIO_MEAN, 0.01, 1.0)
        width = max(1.0, float(round(horizon * width_ratio)))
        center = visit_times[i]
        latest = _clamp(float(round(center + width / 2.0)), earliest_arrival, latest_service_start)
        earliest = _clamp(float(round(center - width / 2.0)), HORIZON_START, latest)
        windows.append((earliest, latest))
    return windows
