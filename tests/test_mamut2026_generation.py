from __future__ import annotations

from random import Random

from mamut_routing_publish.td_generation.family import _audit_and_lift, capacity_lower_bound
from mamut_routing_publish.td_generation.julia_driver import avg_route_size_for_n
from mamut_routing_publish.td_generation.tw_synthesis import (
    construct_anchor_routes,
    synthesize_time_windows,
    validate_static_anchor,
)


class ConstantTravelAtf:
    def __init__(self, travel: float):
        self.travel = travel

    def evaluate(self, departure: float) -> float:
        return departure + self.travel


def test_size_aware_route_size_policy() -> None:
    assert avg_route_size_for_n(10) == 1
    assert avg_route_size_for_n(25) == 2
    assert avg_route_size_for_n(26) == 4
    assert avg_route_size_for_n(1000) == 4


def test_capacity_lower_bound_requires_two_routes() -> None:
    assert capacity_lower_bound([0, 5, 4, 3], 11) == 2
    assert capacity_lower_bound([0, 5, 4, 3], 12) == 1


def test_anchor_routes_are_deterministic_capacity_feasible_and_cover_clients() -> None:
    fastest = [
        [0.0, 1.0, 2.0, 3.0],
        [1.0, 0.0, 1.0, 2.0],
        [2.0, 1.0, 0.0, 1.0],
        [3.0, 2.0, 1.0, 0.0],
    ]
    demands = [0, 4, 4, 4]
    service_times = [0, 1, 1, 1]
    routes, arrivals = construct_anchor_routes(fastest, demands, 8, service_times)
    assert routes == [[1, 2], [3]]
    windows = synthesize_time_windows(Random(42), fastest, service_times, arrivals)
    assert all(earliest < latest for earliest, latest in windows)
    validate_static_anchor(routes, fastest, demands, 8, service_times, windows)


def test_global_anchor_repair_only_lifts_deadlines() -> None:
    routes = [[1, 2]]
    windows = [(0, 100), (5, 10), (15, 20)]
    service_times = [0, 0, 0]
    arcs = {
        (0, 1): ConstantTravelAtf(20),
        (1, 2): ConstantTravelAtf(20),
        (2, 0): ConstantTravelAtf(20),
    }
    lifted, repairs = _audit_and_lift(
        windows,
        service_times,
        routes,
        {"bpr-heavy": arcs},
        100,
    )
    assert lifted == [(0, 100), (5, 20), (15, 40)]
    assert repairs["1"]["deadline_binding_overlay"] == "bpr-heavy"
    assert repairs["2"]["deadline_binding_overlay"] == "bpr-heavy"
    assert all(earliest < latest for earliest, latest in lifted)

