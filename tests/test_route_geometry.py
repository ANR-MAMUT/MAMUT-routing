from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import pytest

from mamut_routing_publish.route_geometry import (
    _PendingBks,
    _city_key,
    _resolve_workers,
    _save_artifact,
    load_route_geometry,
    materialize_route_geometry,
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


def test_route_geometry_cache_dir_overrides_the_active_dist_location(tmp_path: Path) -> None:
    instance_path = _write(tmp_path / "benchmarks/Mamut2026/CVRP/n10/sample.vrp.json", '{"num_customers":10}\n')
    bks_path = _write(tmp_path / "benchmarks/Mamut2026/CVRP/n10/sample.bks.MonoCost.json", '{"routes":[[1]]}\n')
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
        objective_function="MonoCost",
        routes=[[1]],
    )
    edge_cache = {
        "node:0_1": [[4.0, 45.0], [4.1, 45.1]],
        "node:1_0": [[4.1, 45.1], [4.0, 45.0]],
    }
    staging_cache = tmp_path / "staging" / "route-geometry-cache"

    target = _save_artifact(tmp_path, entry, edge_cache, sorted(edge_cache), cache_dir=staging_cache)
    assert target is not None
    assert staging_cache in target.parents
    assert not (tmp_path / "dist" / "route-geometry-cache").exists()

    # The staging cache resolves the artifact; the default location does not.
    assert route_geometry_for_bks(tmp_path, bks_path, cache_dir=staging_cache) is not None
    assert route_geometry_for_bks(tmp_path, bks_path) is None
    assert route_geometry_cache_path(tmp_path, bks_path, cache_dir=staging_cache) == target


def test_city_key_batches_every_group_of_a_city_together() -> None:
    assert _city_key("benchmarks/Mamut2026/sidecars/hong_kong/n=10/x/x.geo.json.gz") == "hong_kong"
    assert _city_key("benchmarks/Mamut2026/sidecars/lyon/n=500/y/y.geo.json.gz") == "lyon"
    assert _city_key("elsewhere/without/marker.geo.json.gz") == "elsewhere/without"


def test_resolve_workers_clamps_to_batches_and_validates() -> None:
    assert _resolve_workers(8, 3) == 3
    assert _resolve_workers(2, 5) == 2
    assert _resolve_workers("auto", 1) == 1
    assert _resolve_workers(None, 0) == 1
    assert _resolve_workers("auto", 100) >= 1
    with pytest.raises(ValueError):
        _resolve_workers(0, 3)
    with pytest.raises(ValueError):
        _resolve_workers("three", 3)


def test_site_materialization_can_skip_groups_whose_gitignored_osm_extract_is_absent(tmp_path: Path) -> None:
    collection = tmp_path / "benchmarks" / "Mamut2026"
    instance_path = _write(
        collection / "CVRP" / "fastest" / "missing_city" / "n=10" / "sample" / "sample.vrp.json",
        json.dumps(
            {
                "num_customers": 1,
                "metadata": {
                    "sidecars": {
                        "geo": {
                            "path": "sidecars/missing_city/n=10/sample/sample.geo.json.gz",
                            "sha256": "geo-digest",
                        }
                    }
                },
            }
        ),
    )
    _write(instance_path.with_name("sample.bks.MonoCost.json"), '{"routes":[[1]]}\n')
    geo_path = collection / "sidecars" / "missing_city" / "n=10" / "sample" / "sample.geo.json.gz"
    geo_path.parent.mkdir(parents=True)
    with gzip.open(geo_path, "wt", encoding="utf-8") as handle:
        json.dump(
            {
                "source_osm_file": "osmdata/Missing-City.osm",
                "nodes": [
                    {"instance_node_id": 0, "poi_lon": 4.0, "poi_lat": 45.0},
                    {"instance_node_id": 1, "poi_lon": 4.1, "poi_lat": 45.1},
                ],
            },
            handle,
        )

    summary = materialize_route_geometry(tmp_path, workers=1, skip_missing_osm=True)

    assert summary["generated"] == 0
    assert summary["groups"] == 1
    assert summary["processed_groups"] == 0
    assert summary["skipped_missing_osm_groups"] == 1
    assert summary["skipped_missing_osm_bks"] == 1
    assert summary["missing_osm_files"] == ["osmdata/Missing-City.osm"]
    assert summary["workers"] == 0

    with pytest.raises(RuntimeError, match="Unable to resolve source OSM file 'osmdata/Missing-City.osm'"):
        materialize_route_geometry(tmp_path, workers=1)


def test_site_materialization_fetches_missing_osm_from_committed_sidecar_bounds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import mamut_routing_tools.osm as osm_module

    collection = tmp_path / "benchmarks" / "Mamut2026"
    instance_path = _write(
        collection / "CVRP" / "fastest" / "missing_city" / "n=10" / "sample" / "sample.vrp.json",
        json.dumps(
            {
                "num_customers": 1,
                "metadata": {
                    "sidecars": {
                        "geo": {
                            "path": "sidecars/missing_city/n=10/sample/sample.geo.json.gz",
                            "sha256": "geo-digest",
                        }
                    }
                },
            }
        ),
    )
    _write(instance_path.with_name("sample.bks.MonoCost.json"), '{"routes":[[1]]}\n')
    sidecar_dir = collection / "sidecars" / "missing_city" / "n=10" / "sample"
    sidecar_dir.mkdir(parents=True)
    geo_path = sidecar_dir / "sample.geo.json.gz"
    with gzip.open(geo_path, "wt", encoding="utf-8") as handle:
        json.dump(
            {
                "city": "Missing City",
                "source_osm_file": "osmdata/Missing-City.osm",
                "map_options": {"only_intersections": True, "trim_to_connected_graph": True},
                "nodes": [
                    {"instance_node_id": 0, "poi_lon": 4.0, "poi_lat": 45.0},
                    {"instance_node_id": 1, "poi_lon": 4.008, "poi_lat": 45.0},
                ],
            },
            handle,
        )
    with gzip.open(sidecar_dir / "sample.road.json.gz", "wt", encoding="utf-8") as handle:
        json.dump({"vertex_lonlat": [[4.0, 45.0], [4.008, 45.0]]}, handle)
    _write(
        tmp_path / "osmdata" / "Missing-City.osm",
        (
            '<osm version="0.6"><bounds minlat="44.9" minlon="3.9" '
            'maxlat="45.1" maxlon="4.1"/><remark>runtime error: out of memory</remark></osm>'
        ),
    )

    def fake_fetch(
        min_lat: float,
        min_lon: float,
        max_lat: float,
        max_lon: float,
        outpath: str | Path,
        *,
        profile: str,
        progress=None,
    ) -> dict:
        assert profile == "road_cache"
        assert min_lat < 45.0 < max_lat
        assert min_lon < 4.0 < 4.008 < max_lon
        target = Path(outpath)
        _write(
            target,
            """<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <bounds minlat="44.9" minlon="3.9" maxlat="45.1" maxlon="4.1"/>
  <node id="1" lat="45.0" lon="4.0"/>
  <node id="2" lat="45.0" lon="4.008"/>
  <way id="10">
    <nd ref="1"/><nd ref="2"/>
    <tag k="highway" v="residential"/>
  </way>
</osm>
""",
        )
        return {
            "bbox": {"minlat": min_lat, "minlon": min_lon, "maxlat": max_lat, "maxlon": max_lon},
            "dataset_mode": "tiled_roads",
            "validation": {"nodes": 2, "ways": 1},
            "road_tiling": {"tiles_total": 1},
        }

    monkeypatch.setattr(osm_module, "fetch_and_store_bbox_osm", fake_fetch)

    summary = materialize_route_geometry(tmp_path, workers=1, fetch_missing_osm=True)

    assert summary["generated"] == 1
    assert summary["processed_groups"] == 1
    assert summary["osm"]["required_files"] == 1
    assert summary["osm"]["fetched"] == 1
    assert summary["osm"]["valid_existing"] == 0
    assert summary["osm"]["invalid_existing"] == 1
    assert (tmp_path / "osmdata" / "Missing-City.osm").is_file()
