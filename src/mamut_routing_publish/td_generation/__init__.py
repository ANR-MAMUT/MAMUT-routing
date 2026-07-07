"""Workbench stage 3: TDVRP/TDVRPTW instance generation.

Consumes the TD bridge exported by ``webapp/td_traffic.jl`` (city road graph
+ per-edge hourly speed profiles + per-instance node maps) and stage-1 CVRP
artifacts, and emits ``road-graph`` td-model instances (TDVRP + TDVRPTW
twins) conforming to the TD benchmark standard.
"""

from mamut_routing_publish.td_generation.bridge import (
    BridgeGraph,
    BridgeNodes,
    BridgeSpeeds,
    load_bridge_graph,
    load_bridge_nodes,
    load_bridge_speeds,
)
from mamut_routing_publish.td_generation.build import (
    DEFAULT_EXTENSION_END,
    DEFAULT_SAMPLE_STEP,
    DEFAULT_SIMPLIFY_TOLERANCE,
    TD_HORIZON,
    BuiltInstancePair,
    build_td_instance_pair,
)
from mamut_routing_publish.td_generation.naming import td_instance_dir, td_instance_name

__all__ = [
    "BridgeGraph",
    "BridgeNodes",
    "BridgeSpeeds",
    "BuiltInstancePair",
    "DEFAULT_EXTENSION_END",
    "DEFAULT_SAMPLE_STEP",
    "DEFAULT_SIMPLIFY_TOLERANCE",
    "TD_HORIZON",
    "build_td_instance_pair",
    "load_bridge_graph",
    "load_bridge_nodes",
    "load_bridge_speeds",
    "td_instance_dir",
    "td_instance_name",
]
