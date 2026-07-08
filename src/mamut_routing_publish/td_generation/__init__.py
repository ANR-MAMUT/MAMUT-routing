"""Mamut2026 collection generation (v2, Stream 12').

Consumes the TD bridge exported by ``webapp/td_traffic.jl`` (city road graph
with coordinates and free-flow limits + per-edge hourly speed profiles +
per-instance node maps) plus the stage-1 sampling intermediates, and
publishes the whole family into a marker-rooted collection tree: slim CVRP /
VRPTW instances, shared ``geo`` / ``road`` / ``traffic`` / ``distances``
sidecars, and the TDVRP/TDVRPTW twins of the ``road-graph`` v2 td model.
"""

from mamut_routing_publish.td_generation.bridge import (
    BridgeGraph,
    BridgeNodes,
    BridgeSpeeds,
    load_bridge_graph,
    load_bridge_nodes,
    load_bridge_speeds,
)
from mamut_routing_publish.td_generation.family import (
    DEFAULT_EXTENSION_END,
    DEFAULT_SAMPLE_STEP,
    TD_HORIZON,
    TD_INTENSITIES,
    TD_MODELS,
    BuiltBase,
    BuiltTDBase,
    build_base,
    build_td,
    derive_vrptw,
    ensure_collection_root,
    sampling_seed,
    simplify_tolerance_for,
)
from mamut_routing_publish.td_generation.naming import (
    FAMILY,
    METHOD_TAGS,
    base_instance_name,
    subinstance_name,
    td_instance_dir,
    td_instance_name,
)

__all__ = [
    "BridgeGraph",
    "BridgeNodes",
    "BridgeSpeeds",
    "BuiltBase",
    "BuiltTDBase",
    "DEFAULT_EXTENSION_END",
    "DEFAULT_SAMPLE_STEP",
    "FAMILY",
    "METHOD_TAGS",
    "TD_HORIZON",
    "TD_INTENSITIES",
    "TD_MODELS",
    "base_instance_name",
    "build_base",
    "build_td",
    "derive_vrptw",
    "ensure_collection_root",
    "load_bridge_graph",
    "load_bridge_nodes",
    "load_bridge_speeds",
    "sampling_seed",
    "simplify_tolerance_for",
    "subinstance_name",
    "td_instance_dir",
    "td_instance_name",
]
