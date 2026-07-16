"""Stage-2 (VRPTW) synthesis of service times and time windows (v2, Stream 12').

The single implementation of the family's name-seeded synthesis
(language-boundary tier 2). One **service-time set** exists per base, shared
by every VRPTW instance and TDVRPTW subinstance. Three **TW sets** exist per
base:

- ``td-shared`` (the TD-paired set): route-centered over the **static
  free-flow fastest** travel times, seeded from the base name, shared
  verbatim (post ``build-td`` repair) by the plain VRPTW instance and every
  TDVRPTW subinstance. The v1 per-variant, TD-anchored synthesis is retired:
  anchoring windows on each traffic variant's own arrivals partially
  cancelled the traffic effect the family is built to measure.
- ``tight`` (static-only): same route-centered machinery and hence the same
  window centers as ``td-shared``, but much narrower widths (a controlled
  width comparison over identical demand geometry).
- ``spread`` (static-only): window centers drawn uniformly over each
  customer's individually feasible interval, destroying the route structure
  (Solomon R-class flavor); widths follow the ``td-shared`` distribution.

The static-only sets are never audited under traffic and are **not** the
TDVRPTW windows; they exist to widen the static VRPTW layer of the family.

Values are integer seconds (exact in binary64). Feasibility bounds at free
flow: a window ``[e, l]`` guarantees ``l >= t_0i`` (a vehicle leaving the
depot at the horizon start reaches the customer by ``l``) and
``l + s_i + t_i0 <= horizon end`` (starting service at ``l`` returns in
time). For ``td-shared``, stage 3 (``build-td``) then certifies the complete
anchor routes under every traffic overlay and applies minimal shared deadline
lifts. The static-only sets are feasible by construction under the free-flow fastest
matrix (route-centered: the deterministic multi-route anchor serves everyone in-window;
spread: every customer is individually serveable, so singleton routes fit
the horizon) and receive no repair.

All randomness comes from ``random.Random`` seeded per base and TW set; the
windows are shipped data, never re-derived at load time.
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
TW_WIDTH_RATIO_MIN = 0.01
TW_WIDTH_RATIO_MAX = 1.0
TIGHT_TW_WIDTH_RATIO_MEAN = 0.05
TIGHT_TW_WIDTH_RATIO_STD = 0.02
TIGHT_TW_WIDTH_RATIO_MIN = 0.01
TIGHT_TW_WIDTH_RATIO_MAX = 0.15


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


def construct_anchor_routes(
    fastest: list[list[float]],
    demands: list[int],
    capacity: int,
    service_times: list[int],
) -> tuple[list[list[int]], list[float]]:
    """Build deterministic capacity-and-horizon-feasible TW anchor routes.

    Every route starts at the depot at the horizon start. The next customer
    is the nearest unserved customer that respects capacity and still permits
    a direct return to the depot within the horizon. Ties break on customer
    index. The returned visit times are the free-flow arrivals independently
    simulated on those routes.
    """
    num_nodes = len(fastest)
    if len(demands) != num_nodes or len(service_times) != num_nodes:
        raise ValueError("fastest, demands and service_times must have identical dimensions")
    if capacity <= 0:
        raise ValueError("vehicle capacity must be positive")

    unserved = set(range(1, num_nodes))
    arrivals = [HORIZON_START] * num_nodes
    routes: list[list[int]] = []
    while unserved:
        route: list[int] = []
        current = 0
        load = 0
        clock = HORIZON_START
        while True:
            feasible: list[tuple[float, int, float]] = []
            for customer in unserved:
                demand = demands[customer]
                arrival = clock + fastest[current][customer]
                completion = arrival + service_times[customer]
                if load + demand <= capacity and completion + fastest[customer][0] <= HORIZON_END:
                    feasible.append((fastest[current][customer], customer, arrival))
            if not feasible:
                break
            _, customer, arrival = min(feasible, key=lambda item: (item[0], item[1]))
            route.append(customer)
            unserved.remove(customer)
            arrivals[customer] = arrival
            load += demands[customer]
            clock = arrival + service_times[customer]
            current = customer
        if not route:
            customer = min(unserved)
            raise ValueError(
                f"customer {customer} cannot start a capacity-and-horizon-feasible anchor route"
            )
        routes.append(route)
    return routes, arrivals


def validate_static_anchor(
    routes: list[list[int]],
    fastest: list[list[float]],
    demands: list[int],
    capacity: int,
    service_times: list[int],
    time_windows: list[tuple[int, int]],
) -> None:
    """Hard-check a static anchor certificate against its generated windows."""
    expected = set(range(1, len(fastest)))
    visited = [customer for route in routes for customer in route]
    if len(visited) != len(expected) or set(visited) != expected:
        raise AssertionError("anchor routes must cover every customer exactly once")
    for route in routes:
        load = sum(demands[customer] for customer in route)
        if load > capacity:
            raise AssertionError(f"anchor route load {load} exceeds capacity {capacity}")
        clock = HORIZON_START
        previous = 0
        for customer in route:
            arrival = clock + fastest[previous][customer]
            earliest, latest = time_windows[customer]
            clock = max(arrival, earliest)
            if clock > latest:
                raise AssertionError(
                    f"anchor route reaches customer {customer} at {clock} after deadline {latest}"
                )
            clock += service_times[customer]
            previous = customer
        if clock + fastest[previous][0] > HORIZON_END:
            raise AssertionError("anchor route returns after the horizon end")


def _feasible_bounds(
    fastest: list[list[float]], service_times: list[int], i: int
) -> tuple[int, int]:
    """Integer free-flow feasibility bounds for customer ``i``'s service start."""
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
    return lo, hi


def synthesize_time_windows(
    rng: Random,
    fastest: list[list[float]],
    service_times: list[int],
    visit_times: list[float],
    *,
    width_ratio_mean: float = TW_WIDTH_RATIO_MEAN,
    width_ratio_std: float = TW_WIDTH_RATIO_STD,
    width_ratio_min: float = TW_WIDTH_RATIO_MIN,
    width_ratio_max: float = TW_WIDTH_RATIO_MAX,
) -> list[tuple[int, int]]:
    """Route-centered integer windows clamped to the free-flow feasibility bounds.

    Defaults reproduce the ``td-shared`` set byte-for-byte; the ``tight`` set
    passes the ``TIGHT_TW_WIDTH_RATIO_*`` parameters (same rng call sequence,
    so identical seeds with identical widths give identical windows).
    """
    horizon = HORIZON_END - HORIZON_START
    num_nodes = len(fastest)
    windows: list[tuple[int, int]] = [(int(HORIZON_START), int(HORIZON_END))]
    for i in range(1, num_nodes):
        lo, hi = _feasible_bounds(fastest, service_times, i)
        width_ratio = _clamp(
            rng.gauss(0.0, 1.0) * width_ratio_std + width_ratio_mean,
            width_ratio_min,
            width_ratio_max,
        )
        width = max(1.0, float(round(horizon * width_ratio)))
        center = visit_times[i]
        latest = int(_clamp(float(round(center + width / 2.0)), float(lo), float(hi)))
        earliest = int(_clamp(float(round(center - width / 2.0)), HORIZON_START, float(latest)))
        windows.append((earliest, latest))
    return windows


def synthesize_time_windows_spread(
    rng: Random,
    fastest: list[list[float]],
    service_times: list[int],
) -> list[tuple[int, int]]:
    """Uniform-center integer windows (the static-only ``spread`` set).

    Per customer, the width is drawn from the ``td-shared`` distribution and
    the center uniformly over the customer's feasible interval (width first,
    then center: the rng call order is part of the frozen policy). Clamping
    is identical to the route-centered synthesis, so every window satisfies
    the individual free-flow feasibility bounds by construction.
    """
    horizon = HORIZON_END - HORIZON_START
    num_nodes = len(fastest)
    windows: list[tuple[int, int]] = [(int(HORIZON_START), int(HORIZON_END))]
    for i in range(1, num_nodes):
        lo, hi = _feasible_bounds(fastest, service_times, i)
        width_ratio = _clamp(
            rng.gauss(0.0, 1.0) * TW_WIDTH_RATIO_STD + TW_WIDTH_RATIO_MEAN,
            TW_WIDTH_RATIO_MIN,
            TW_WIDTH_RATIO_MAX,
        )
        width = max(1.0, float(round(horizon * width_ratio)))
        center = rng.uniform(float(lo), float(hi))
        latest = int(_clamp(float(round(center + width / 2.0)), float(lo), float(hi)))
        earliest = int(_clamp(float(round(center - width / 2.0)), HORIZON_START, float(latest)))
        windows.append((earliest, latest))
    return windows
