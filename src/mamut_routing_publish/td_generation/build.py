"""Assembly of road-graph TD instances from the bridge + stage-1 artifacts.

For one (base instance, traffic model, intensity) cell this module:

1. builds the full-city road graph from the bridge and runs the lib's pinned
   Dijkstra from every instance node to collect the union of used path edges;
2. trims the graph to that union, renumbers vertices in ascending OSM-id
   order, and re-checks (exact equality) that node-to-node free-flow
   distances are preserved on the trimmed subgraph;
3. writes the ``<name>.road.json.gz`` sidecar, materializes the canonical
   ATFs through the lib code path, and pins both sha256 digests;
4. synthesizes service times and TD-feasible time windows (TDVRPTW twin);
5. writes the TDVRP + TDVRPTW instance files in the 7-part Mamut2026 layout.

The TDVRP and TDVRPTW twins share the same road sidecar content (one copy in
each problem-type tree), service times and ATFs; only the time windows
differ (absent from the TDVRP twin).
"""

from __future__ import annotations

import time
import zlib
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from random import Random
from typing import Any

from mamut_routing_lib.json_utils import save_json_to_file
from mamut_routing_lib.td import (
    InstanceRoadGraph,
    build_adjacency,
    compute_atf_sha256,
    compute_fastest_path_tree,
    compute_road_graph_sha256,
    load_td_instance,
    materialize_instance_atfs_roadgraph,
    save_instance_road_graph,
    td_instance_from_payload,
)

from mamut_routing_publish.td_generation.bridge import BridgeFormatError, BridgeGraph, BridgeNodes, BridgeSpeeds
from mamut_routing_publish.td_generation.naming import td_instance_dir, td_instance_name
from mamut_routing_publish.td_generation.tw_synthesis import (
    nearest_neighbour_visit_times,
    synthesize_service_times,
    synthesize_time_windows,
)

TD_HORIZON = (0.0, 86400.0)
DEFAULT_EXTENSION_END = 172800.0
DEFAULT_SAMPLE_STEP = 60.0
DEFAULT_SIMPLIFY_TOLERANCE = 1.0


@dataclass
class BuiltInstancePair:
    instance_name: str
    tdvrp_instance_path: Path
    tdvrptw_instance_path: Path
    graph_sha256: str
    atf_sha256: str
    num_road_vertices: int
    num_road_edges: int
    sidecar_bytes_gz: int
    mean_breakpoints: float
    build_seconds: float


def _stable_seed(*parts: str) -> int:
    return zlib.crc32("|".join(parts).encode("utf-8"))


def _full_city_road_graph(
    graph: BridgeGraph,
    speeds: BridgeSpeeds,
    nodes: BridgeNodes,
    *,
    base_name: str,
    sample_step: float,
    simplify_tolerance: float,
    extension_end: float,
    generator: dict[str, Any],
) -> InstanceRoadGraph:
    osm_ids = sorted({osm for osm_u, osm_v, _, _ in graph.edges for osm in (osm_u, osm_v)})
    index_of = {osm: index for index, osm in enumerate(osm_ids)}
    edges = sorted(
        (index_of[osm_u], index_of[osm_v], length_m, row)
        for (osm_u, osm_v, length_m, _), row in zip(graph.edges, speeds.speeds)
    )
    missing = [osm for osm in nodes.node_osm_ids if osm not in index_of]
    if missing:
        raise ValueError(f"instance nodes not present in the bridge graph: OSM {missing[:5]}...")
    bin_edges = [TD_HORIZON[0] + k * graph.bin_seconds for k in range(graph.num_bins + 1)]
    if bin_edges[-1] != TD_HORIZON[1]:
        raise ValueError(f"bridge bins {graph.num_bins} x {graph.bin_seconds}s do not tile the horizon")
    return InstanceRoadGraph(
        base_name=base_name,
        benchmark_name="Mamut2026",
        num_customers=len(nodes.node_osm_ids) - 1,
        horizon=TD_HORIZON,
        extension_end=extension_end,
        bin_edges=bin_edges,
        sample_step=sample_step,
        simplify_tolerance=simplify_tolerance,
        num_vertices=len(osm_ids),
        vertex_osm_ids=osm_ids,
        node_vertices=[index_of[osm] for osm in nodes.node_osm_ids],
        edges=[(u, v, length, list(row)) for u, v, length, row in edges],
        generator=generator,
    )


def _trim_road_graph(full: InstanceRoadGraph) -> InstanceRoadGraph:
    """Trim to the union of pinned fastest-path edges between instance nodes,
    then verify node-to-node free-flow distances are bit-identical."""
    adjacency = build_adjacency(full)
    node_set = full.node_vertices
    used_edges: set[int] = set()
    full_dists: list[list[float]] = []
    for source in node_set:
        dist, pred_edge = compute_fastest_path_tree(full, adjacency, source)
        full_dists.append([dist[target] for target in node_set])
        walked: set[int] = {source}
        for target in node_set:
            if target == source:
                continue
            vertex = target
            # Paths merge toward the source in the tree: once a vertex was
            # walked for this source, its chain to the source is collected.
            while vertex not in walked:
                edge_index = pred_edge[vertex]
                if edge_index < 0:
                    raise ValueError(
                        f"vertex OSM {full.vertex_osm_ids[target]} unreachable from "
                        f"OSM {full.vertex_osm_ids[source]} in the bridge graph"
                    )
                used_edges.add(edge_index)
                walked.add(vertex)
                vertex = full.edges[edge_index][0]

    kept = sorted(used_edges)
    kept_osm_ids = sorted(
        {full.vertex_osm_ids[endpoint] for index in kept for endpoint in full.edges[index][:2]}
    )
    index_of = {osm: index for index, osm in enumerate(kept_osm_ids)}
    old_to_new = {
        old: index_of[full.vertex_osm_ids[old]]
        for index in kept
        for old in full.edges[index][:2]
    }
    trimmed_edges = sorted(
        (old_to_new[u], old_to_new[v], length, list(speeds))
        for u, v, length, speeds in (full.edges[index] for index in kept)
    )
    trimmed = InstanceRoadGraph(
        base_name=full.base_name,
        benchmark_name=full.benchmark_name,
        num_customers=full.num_customers,
        horizon=full.horizon,
        extension_end=full.extension_end,
        bin_edges=list(full.bin_edges),
        sample_step=full.sample_step,
        simplify_tolerance=full.simplify_tolerance,
        num_vertices=len(kept_osm_ids),
        vertex_osm_ids=kept_osm_ids,
        node_vertices=[old_to_new[vertex] for vertex in full.node_vertices],
        edges=trimmed_edges,
        generator=dict(full.generator),
    )

    trimmed_adjacency = build_adjacency(trimmed)
    for row, source in zip(full_dists, trimmed.node_vertices):
        dist, _ = compute_fastest_path_tree(trimmed, trimmed_adjacency, source)
        trimmed_row = [dist[target] for target in trimmed.node_vertices]
        if trimmed_row != row:
            raise AssertionError(
                f"trimmed-graph free-flow distances diverge from the full graph for {full.base_name}"
            )
    return trimmed


def build_td_instance_pair(
    *,
    graph: BridgeGraph,
    speeds: BridgeSpeeds,
    nodes: BridgeNodes,
    meta: dict[str, Any],
    vehicle_capacity: int,
    place: str,
    method: str,
    out_root: str | Path,
    sample_step: float = DEFAULT_SAMPLE_STEP,
    simplify_tolerance: float = DEFAULT_SIMPLIFY_TOLERANCE,
    extension_end: float = DEFAULT_EXTENSION_END,
    generated_at: str | None = None,
    force: bool = False,
    verify: bool = True,
) -> BuiltInstancePair | None:
    """Build one TDVRP + TDVRPTW twin pair. Returns None when both instance
    files already exist (idempotent resume), unless ``force``."""
    started = time.perf_counter()
    num_customers = len(nodes.node_osm_ids) - 1
    name = td_instance_name(place, num_customers, speeds.model, speeds.intensity, method)

    tdvrp_dir = td_instance_dir(out_root, "TDVRP", place, num_customers, name)
    tdvrptw_dir = td_instance_dir(out_root, "TDVRPTW", place, num_customers, name)
    tdvrp_instance_path = tdvrp_dir / f"{name}.vrp.json"
    tdvrptw_instance_path = tdvrptw_dir / f"{name}.vrp.json"
    if not force and tdvrp_instance_path.exists() and tdvrptw_instance_path.exists():
        return None

    generator = {
        "name": "mamut-routing-workbench",
        "stage": "td-road-graph",
        "version": 1,
        "traffic_model": speeds.model,
        "intensity": speeds.intensity,
        "traffic_seed": speeds.seed,
        "city": place,
    }
    full = _full_city_road_graph(
        graph, speeds, nodes,
        base_name=name,
        sample_step=sample_step,
        simplify_tolerance=simplify_tolerance,
        extension_end=extension_end,
        generator=generator,
    )
    road = _trim_road_graph(full)
    graph_sha = compute_road_graph_sha256(road)

    meta_nodes = meta["nodes"]
    coordinates = [[float(node["enu_x"]), float(node["enu_y"])] for node in meta_nodes]
    demands = [int(node["demand"]) for node in meta_nodes]
    meta_reference_lla = meta.get("reference_lla")
    if not isinstance(meta_reference_lla, dict):
        raise BridgeFormatError(f"stage-1 meta for {name} has no reference_lla geodetic anchor")
    reference_lla = {
        "lat": float(meta_reference_lla["lat"]),
        "lon": float(meta_reference_lla["lon"]),
        "alt": float(meta_reference_lla.get("alt", 0.0)),
    }

    service_rng = Random(_stable_seed(name, "service"))
    service_times = synthesize_service_times(service_rng, num_customers)

    sidecar_name = f"{name}.road.json.gz"
    base_payload: dict[str, Any] = {
        "instance_name": name,
        "instance_origin": "OsmCvrpGen",
        "benchmark_name": "Mamut2026",
        "num_customers": num_customers,
        "num_vehicles": None,
        "vehicle_capacity": int(vehicle_capacity),
        "coordinates": coordinates,
        "demands": demands,
        "service_times": service_times,
        "depot": 0,
        "reference_lla": reference_lla,
        "horizon": list(TD_HORIZON),
        "td": {
            "model": "road-graph",
            "graph_path": sidecar_name,
            "graph_sha256": graph_sha,
        },
        "metadata": {},
    }
    instance = td_instance_from_payload(base_payload)
    atfs = materialize_instance_atfs_roadgraph(instance, road)
    atf_sha = compute_atf_sha256(atfs)
    base_payload["td"]["atf_sha256"] = atf_sha

    tw_rng = Random(_stable_seed(name, "tw"))
    visit_times = nearest_neighbour_visit_times(atfs, service_times)
    time_windows = synthesize_time_windows(tw_rng, atfs, service_times, visit_times)

    metadata = {
        "authors": "MAMUT-routing workbench (generated instance)",
        "generated_at": generated_at or date.today().isoformat(),
        "generator": dict(generator),
        "city": place,
        "customer_sampling": {
            "method": method,
            "base_instance": str(meta.get("instance_name", "")),
            "source_osm_file": str(meta.get("source_osm_file", "")),
        },
        "traffic": {
            "model": speeds.model,
            "intensity": speeds.intensity,
            "seed": speeds.seed,
            "num_trips": speeds.num_trips,
            "params": speeds.params,
        },
        "notes": (
            "Time dependence is derived from the city's OSM road network: per-edge "
            "hourly speed profiles (synthetic traffic, see metadata.traffic) are "
            "stored in the road-graph sidecar; arrival-time functions are "
            "materialized deterministically on load and pinned by td.atf_sha256."
        ),
    }

    # TDVRP twin (no time windows).
    tdvrp_payload = dict(base_payload)
    tdvrp_payload["metadata"] = dict(metadata)
    tdvrp_dir.mkdir(parents=True, exist_ok=True)
    save_instance_road_graph(road, tdvrp_dir / sidecar_name)
    save_json_to_file(tdvrp_payload, tdvrp_instance_path)

    # TDVRPTW twin.
    tdvrptw_payload = dict(base_payload)
    tdvrptw_payload["time_windows"] = [list(window) for window in time_windows]
    tdvrptw_payload["metadata"] = dict(metadata)
    tdvrptw_dir.mkdir(parents=True, exist_ok=True)
    save_instance_road_graph(road, tdvrptw_dir / sidecar_name)
    save_json_to_file(tdvrptw_payload, tdvrptw_instance_path)

    if verify:
        for path in (tdvrp_instance_path, tdvrptw_instance_path):
            load_td_instance(path, verify_sha256=True)

    breakpoints = [f.num_breakpoints() for f in atfs.arcs.values()]
    return BuiltInstancePair(
        instance_name=name,
        tdvrp_instance_path=tdvrp_instance_path,
        tdvrptw_instance_path=tdvrptw_instance_path,
        graph_sha256=graph_sha,
        atf_sha256=atf_sha,
        num_road_vertices=road.num_vertices,
        num_road_edges=len(road.edges),
        sidecar_bytes_gz=(tdvrp_dir / sidecar_name).stat().st_size,
        mean_breakpoints=sum(breakpoints) / len(breakpoints),
        build_seconds=time.perf_counter() - started,
    )
