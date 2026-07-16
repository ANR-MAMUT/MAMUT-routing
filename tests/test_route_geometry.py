from __future__ import annotations

import hashlib
from pathlib import Path

from mamut_routing_publish.route_geometry import (
    _PendingBks,
    _save_artifact,
    load_route_geometry,
    route_geometry_cache_path,
    route_geometry_for_bks,
)


def _write(path: Path, value: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")
    return path


def test_route_geometry_artifact_is_deterministic_and_bound_to_exact_bks(tmp_path: Path) -> None:
    instance_path = _write(tmp_path / "benchmarks/Mamut2026/TDVRP/n500/sample.vrp.json", '{"num_customers":500}\n')
    bks_path = _write(tmp_path / "benchmarks/Mamut2026/TDVRP/n500/sample.bks.Duration.json", '{"routes":[[1,2]]}\n')
    geo_path = _write(tmp_path / "benchmarks/Mamut2026/sidecars/sample.geo.json.gz", "fixture")
    entry = _PendingBks(
        instance_path=instance_path,
        instance_sha256=hashlib.sha256(instance_path.read_bytes()).hexdigest(),
        bks_path=bks_path,
        bks_sha256=hashlib.sha256(bks_path.read_bytes()).hexdigest(),
        geo_path=geo_path,
        geo_sha256="geo-digest",
        geo_file_sha256=hashlib.sha256(geo_path.read_bytes()).hexdigest(),
        metric="fastest",
        objective_function="Duration",
        routes=[[1, 2]],
    )
    edge_cache = {
        "node:0_1": [[4.0, 45.0], [4.1, 45.1]],
        "node:1_2": [[4.1, 45.1], [4.2, 45.2]],
        "node:2_0": [[4.2, 45.2], [4.0, 45.0]],
    }

    target = _save_artifact(tmp_path, entry, edge_cache, sorted(edge_cache))
    first_bytes = target.read_bytes()
    assert _save_artifact(tmp_path, entry, edge_cache, sorted(edge_cache)).read_bytes() == first_bytes

    loaded_target, payload = route_geometry_for_bks(tmp_path, bks_path) or (None, None)
    assert loaded_target == target
    assert payload == load_route_geometry(target)
    assert payload["bks_sha256"] == hashlib.sha256(bks_path.read_bytes()).hexdigest()
    assert payload["paths"] == {"0-1": [0, 1], "1-2": [1, 2], "2-0": [2, 0]}
    assert payload["straight_fallback_paths"] == []

    _save_artifact(tmp_path, entry, edge_cache, sorted(edge_cache), ["node:0_1"])
    assert load_route_geometry(target)["straight_fallback_paths"] == ["0-1"]

    bks_path.write_text('{"routes":[[2,1]]}\n', encoding="utf-8")
    assert _save_artifact(tmp_path, entry, edge_cache, sorted(edge_cache)) is None
    assert route_geometry_cache_path(tmp_path, bks_path) != target
    assert route_geometry_for_bks(tmp_path, bks_path) is None
