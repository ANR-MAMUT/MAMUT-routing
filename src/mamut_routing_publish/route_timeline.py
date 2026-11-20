"""Per-BKS route timelines for the workbench animation (``timeline.<Objective>.json``).

The workbench animates the vehicles of a BKS along its routes. Where they are at
a given time comes from the solution's per-stop schedule, built here at publish
time, so the browser never has to re-implement the checker:

- VRPTW (``clock: "checker"``): the instance's own ``fastest`` arc costs, the
  checker's waiting and service rules. This is exactly the schedule the checker
  validates (``mamut_routing_tools.timeline.build_static_timeline``).
- CVRP (``clock: "free_flow_fastest"``): a capacity-only instance has no time, so
  the base's ``fastest`` matrix (free-flow seconds) clocks the routes, borrowed
  from the fastest sibling when the BKS is on the shortest or Euclidean metric.

Time-dependent BKS get no file: their pages already carry the checker-derived
``td_schedules``, which the client converts. Only family-first collections
(geographic instances the workbench can show) are covered. An instance whose
``fastest`` distances sidecar is not shipped (Mamut2026 above n = 1000) gets no
timeline, and the client falls back to constant-speed timing.
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from mamut_routing_lib.artifacts import is_collection_instance, load_benchmark_instance, resolve_arc_costs
from mamut_routing_lib.enums import ObjectiveFunction
from mamut_routing_tools.timeline import TimelineError, build_static_timeline

TimelineClock = Literal["checker", "free_flow_fastest"]


class RouteTimelineRoute(BaseModel):
    model_config = ConfigDict(extra="forbid")

    departure: float
    return_arrival: float
    #: ``[node, arrival, service_start, departure]`` per visited customer.
    stops: list[tuple[int, float, float, float]]


class RouteTimelinePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payload_kind: Literal["route_timeline"] = "route_timeline"
    schema_version: Literal[1] = 1
    objective_function: ObjectiveFunction
    route_path: str
    clock: TimelineClock
    #: The metric whose arc costs clock the routes (always ``fastest`` today).
    clock_metric: Literal["fastest"] = "fastest"
    time_unit: Literal["s"] = "s"
    start_rule: Literal["depot_at_zero"] = "depot_at_zero"
    routes: list[RouteTimelineRoute]


def route_timeline_filename(objective_function: ObjectiveFunction) -> str:
    return f"timeline.{objective_function.value}.json"


#: Fastest matrices by fastest-instance path. Resolution groups are per base, so a
#: worker holds the one matrix its CVRP/VRPTW variants share; site_payloads clears
#: the memo between groups.
_FASTEST_ARC_COSTS_MEMO: dict[Path, list[list[float]] | None] = {}


def clear_route_timeline_memo() -> None:
    _FASTEST_ARC_COSTS_MEMO.clear()


def _fastest_sibling_path(instance_path: Path, metric: str) -> Path | None:
    """The same base's ``fastest`` instance: the metric directory swapped."""
    parts = list(instance_path.parts)
    for index in range(len(parts) - 1, -1, -1):
        if parts[index] == metric:
            candidate = Path(*parts[:index], "fastest", *parts[index + 1 :])
            return candidate if candidate.is_file() else None
    return None


def fastest_arc_costs(instance, instance_path: Path) -> list[list[float]] | None:
    """The base's free-flow ``fastest`` matrix, sha-verified, or None when not shipped."""
    metric = getattr(getattr(instance, "metric_variant", None), "value", None)
    if metric is None:
        return None
    fastest_path = instance_path if metric == "fastest" else _fastest_sibling_path(instance_path, metric)
    if fastest_path is None:
        return None
    key = fastest_path.resolve()
    if key not in _FASTEST_ARC_COSTS_MEMO:
        try:
            fastest_instance = instance if metric == "fastest" else load_benchmark_instance(fastest_path)
            _FASTEST_ARC_COSTS_MEMO[key] = resolve_arc_costs(fastest_instance, fastest_path)
        except (OSError, ValueError):
            # Not shipped (large Mamut2026 tiers) or not a collection instance.
            _FASTEST_ARC_COSTS_MEMO[key] = None
    return _FASTEST_ARC_COSTS_MEMO[key]


def build_route_timeline(
    instance,
    instance_path: Path,
    routes: list[list[int]],
    objective_function: ObjectiveFunction,
    route_path: str,
) -> RouteTimelinePayload | None:
    if not is_collection_instance(instance):
        return None
    arc_costs = fastest_arc_costs(instance, instance_path)
    if arc_costs is None:
        return None
    time_windows = getattr(instance, "time_windows", None)
    try:
        timeline = build_static_timeline(
            routes,
            arc_costs,
            depot=instance.depot,
            time_windows=time_windows,
            service_times=getattr(instance, "service_times", None),
        )
    except TimelineError as error:
        warnings.warn(f"No route timeline for {instance_path} ({objective_function.value}): {error}", stacklevel=2)
        return None
    return RouteTimelinePayload(
        objective_function=objective_function,
        route_path=route_path,
        clock="checker" if time_windows is not None else "free_flow_fastest",
        routes=timeline["routes"],
    )
