"""Parsing and validation of the TD bridge written by ``webapp/td_traffic.jl``.

The bridge is a git-ignored per-city intermediate under
``instances_v2/td-bridge/<city>/`` (schema v2, Stream 12'):

- ``graph.json`` — deduplicated directed edges ``[osm_u, osm_v, length_m,
  class, free_speed_ms]`` (OSM node ids are the stable keys; the free-flow
  limit uses the same 3-decimal rounding as the speed profiles) plus
  ``vertices`` ``[osm_id, lon, lat]`` for every vertex incident to an edge;
- ``speeds-<model>-<intensity>.json`` — per-edge speed profiles (m/s, one
  value per hourly bin) aligned with the graph edge order;
- ``nodes-<instance_base>.json`` — instance node -> OSM node ids, depot
  first, for one stage-1 instance.

The bridge is Julia's only output surface (language-boundary tier 3): every
published byte is canonicalized downstream by the Python builder.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

BRIDGE_SCHEMA_VERSION = 2


class BridgeFormatError(ValueError):
    """Raised when a TD bridge file violates the expected format."""


@dataclass
class BridgeGraph:
    city: str
    osm_file: str
    map_options: dict
    num_bins: int
    bin_seconds: float
    edges: list[tuple[int, int, float, int, float]]  # (osm_u, osm_v, length_m, class, free_speed_ms)
    vertex_lonlat: dict[int, tuple[float, float]]  # osm_id -> (lon, lat)


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
    edges: list[tuple[int, int, float, int, float]] = []
    for index, entry in enumerate(payload["edges"]):
        if len(entry) != 5:
            raise BridgeFormatError(
                f"{source.name}: edge {index} must be [osm_u, osm_v, length_m, class, free_speed_ms]"
            )
        osm_u, osm_v, length_m, road_class, free_speed = entry
        length_m = float(length_m)
        free_speed = float(free_speed)
        if length_m <= 0:
            raise BridgeFormatError(f"{source.name}: edge {index} has non-positive length {length_m}")
        if free_speed <= 0:
            raise BridgeFormatError(f"{source.name}: edge {index} has non-positive free speed {free_speed}")
        edges.append((int(osm_u), int(osm_v), length_m, int(road_class), free_speed))
    if not edges:
        raise BridgeFormatError(f"{source.name}: no edges")
    vertex_lonlat: dict[int, tuple[float, float]] = {}
    for index, entry in enumerate(payload["vertices"]):
        if len(entry) != 3:
            raise BridgeFormatError(f"{source.name}: vertex {index} must be [osm_id, lon, lat]")
        osm_id, lon, lat = entry
        vertex_lonlat[int(osm_id)] = (float(lon), float(lat))
    for osm_u, osm_v, _, _, _ in edges:
        if osm_u not in vertex_lonlat or osm_v not in vertex_lonlat:
            raise BridgeFormatError(f"{source.name}: edge endpoint without vertex coordinates")
    return BridgeGraph(
        city=str(payload["city"]),
        osm_file=str(payload["osm_file"]),
        map_options=dict(payload["map_options"]),
        num_bins=int(payload["num_bins"]),
        bin_seconds=float(payload["bin_seconds"]),
        edges=edges,
        vertex_lonlat=vertex_lonlat,
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
