"""Parsing and validation of the TD bridge written by ``webapp/td_traffic.jl``.

The bridge is a git-ignored per-city intermediate under
``instances_v2/td-bridge/<city>/``:

- ``graph.json`` — deduplicated directed edges ``[osm_u, osm_v, length_m,
  class]`` (OSM node ids are the stable keys);
- ``speeds-<model>-<intensity>.json`` — per-edge speed profiles (m/s, one
  value per hourly bin) aligned with the graph edge order;
- ``nodes-<instance_base>.json`` — instance node -> OSM node ids, depot
  first, for one stage-1 instance.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

BRIDGE_SCHEMA_VERSION = 1


class BridgeFormatError(ValueError):
    """Raised when a TD bridge file violates the expected format."""


@dataclass
class BridgeGraph:
    city: str
    osm_file: str
    map_options: dict
    num_bins: int
    bin_seconds: float
    edges: list[tuple[int, int, float, int]]  # (osm_u, osm_v, length_m, road_class)


@dataclass
class BridgeSpeeds:
    city: str
    model: str
    intensity: str
    seed: int
    num_trips: int
    params: dict
    speeds: list[list[float]]  # aligned with BridgeGraph.edges


@dataclass
class BridgeNodes:
    city: str
    instance_base: str
    node_osm_ids: list[int]  # depot first


def _read_bridge_payload(path: Path) -> dict:
    payload = json.loads(path.read_text())
    version = payload.get("schema_version")
    if version != BRIDGE_SCHEMA_VERSION:
        raise BridgeFormatError(f"{path.name}: unsupported bridge schema_version {version!r}")
    return payload


def load_bridge_graph(path: str | Path) -> BridgeGraph:
    source = Path(path)
    payload = _read_bridge_payload(source)
    edges: list[tuple[int, int, float, int]] = []
    for index, entry in enumerate(payload["edges"]):
        if len(entry) != 4:
            raise BridgeFormatError(f"{source.name}: edge {index} must be [osm_u, osm_v, length_m, class]")
        osm_u, osm_v, length_m, road_class = entry
        length_m = float(length_m)
        if length_m <= 0:
            raise BridgeFormatError(f"{source.name}: edge {index} has non-positive length {length_m}")
        edges.append((int(osm_u), int(osm_v), length_m, int(road_class)))
    if not edges:
        raise BridgeFormatError(f"{source.name}: no edges")
    return BridgeGraph(
        city=str(payload["city"]),
        osm_file=str(payload["osm_file"]),
        map_options=dict(payload["map_options"]),
        num_bins=int(payload["num_bins"]),
        bin_seconds=float(payload["bin_seconds"]),
        edges=edges,
    )


def load_bridge_speeds(path: str | Path, graph: BridgeGraph) -> BridgeSpeeds:
    source = Path(path)
    payload = _read_bridge_payload(source)
    speeds = [[float(v) for v in row] for row in payload["speeds"]]
    if len(speeds) != len(graph.edges):
        raise BridgeFormatError(
            f"{source.name}: {len(speeds)} speed rows do not match {len(graph.edges)} graph edges"
        )
    for index, row in enumerate(speeds):
        if len(row) != graph.num_bins:
            raise BridgeFormatError(
                f"{source.name}: row {index} has {len(row)} bins, expected {graph.num_bins}"
            )
        if any(v <= 0 for v in row):
            raise BridgeFormatError(f"{source.name}: row {index} has a non-positive speed")
    return BridgeSpeeds(
        city=str(payload["city"]),
        model=str(payload["model"]),
        intensity=str(payload["intensity"]),
        seed=int(payload["seed"]),
        num_trips=int(payload.get("num_trips", 0)),
        params=dict(payload.get("params", {})),
        speeds=speeds,
    )


def load_bridge_nodes(path: str | Path) -> BridgeNodes:
    source = Path(path)
    payload = _read_bridge_payload(source)
    node_osm_ids = [int(v) for v in payload["node_osm_ids"]]
    if len(node_osm_ids) < 2:
        raise BridgeFormatError(f"{source.name}: need at least depot + 1 customer")
    if len(set(node_osm_ids)) != len(node_osm_ids):
        raise BridgeFormatError(f"{source.name}: node_osm_ids must be distinct")
    if not payload.get("depot_first", False):
        raise BridgeFormatError(f"{source.name}: depot_first marker missing")
    return BridgeNodes(
        city=str(payload["city"]),
        instance_base=str(payload["instance_base"]),
        node_osm_ids=node_osm_ids,
    )
