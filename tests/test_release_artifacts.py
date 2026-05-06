from __future__ import annotations

from pathlib import Path
import zipfile

import pytest

from mamut_routing_lib.enums import ObjectiveFunction
from mamut_routing_lib.json_utils import save_json_to_file
from mamut_routing_lib.models import BenchmarkBKS, BenchmarkInstance, BenchmarkInstanceCVRP
from mamut_routing_lib.remote import load_release_manifest
from mamut_routing_publish.release_artifacts import (
    GITHUB_RELEASE_ASSET_MAX_SIZE_BYTES,
    GITHUB_RELEASE_ASSET_WARNING_SIZE_BYTES,
    _validate_release_asset_size,
    generate_release_artifacts,
)


def make_generated_cvrp_instance() -> BenchmarkInstanceCVRP:
    return BenchmarkInstanceCVRP(
        instance_name="mamut-n2-cafe123",
        instance_origin="OsmCvrpGen",
        benchmark_name="Mamut2026",
        num_customers=2,
        vehicle_capacity=10,
        coordinates=[(0.0, 0.0), (1.0, 1.0), (2.0, 2.0)],
        demands=[0, 1, 2],
        depot=0,
        arc_costs=[[0, 1, 2], [1, 0, 3], [2, 3, 0]],
        metadata={
            "authors": "Florian Rascoussier (0nyr) and Adrien Pichon (Anzury)",
            "generated_at": "2026-04-23T10:00:00",
            "problem_type": "CVRP",
            "metric_variant": "fastest",
            "place_slug": "brest",
            "source_base_name": "brest_poi-n3-k2",
            "source_city": "Brest",
            "source_seed": 123,
            "source_folder": "instances_v2/osm/brest/n3",
            "num_vehicles_lb": 2,
            "generator_version": "fixture",
            "artifact_paths": {
                "vrp_json": "benchmarks/CVRP/Mamut2026/fastest/brest/n=2/mamut-n2-cafe123/mamut-n2-cafe123.vrp.json",
                "vrp": "benchmarks/CVRP/Mamut2026/fastest/brest/n=2/mamut-n2-cafe123/mamut-n2-cafe123.vrp",
                "meta": "benchmarks/CVRP/Mamut2026/sidecars/brest/n=2/mamut-n2-cafe123/mamut-n2-cafe123.meta.json",
                "manifest": "benchmarks/CVRP/Mamut2026/sidecars/brest/n=2/mamut-n2-cafe123/mamut-n2-cafe123.manifest.json",
            },
        },
    )


def make_generated_vrptw_instance() -> BenchmarkInstance:
    return BenchmarkInstance(
        instance_name="mamut-n2-beef456",
        instance_origin="OsmCvrpGen",
        benchmark_name="Mamut2026",
        num_customers=2,
        vehicle_capacity=10,
        coordinates=[(0.0, 0.0), (1.0, 1.0), (2.0, 2.0)],
        demands=[0, 1, 2],
        service_times=[0, 10, 10],
        time_windows=[(0, 1000), (10, 500), (10, 500)],
        depot=0,
        arc_costs=[[0, 1, 2], [1, 0, 3], [2, 3, 0]],
        metadata={
            "authors": "Florian Rascoussier (0nyr) and Adrien Pichon (Anzury)",
            "generated_at": "2026-04-23T10:00:00",
            "problem_type": "VRPTW",
            "metric_variant": "fastest",
            "place_slug": "brest",
            "source_base_name": "brest_poi-n3-k2",
            "source_city": "Brest",
            "source_seed": 123,
            "source_folder": "instances_v2/osm/brest/n3",
            "num_vehicles_lb": 2,
            "generator_version": "fixture",
            "artifact_paths": {
                "vrp_json": "benchmarks/VRPTW/Mamut2026/fastest/brest/n=2/mamut-n2-beef456/mamut-n2-beef456.vrp.json",
                "vrp": "benchmarks/VRPTW/Mamut2026/fastest/brest/n=2/mamut-n2-beef456/mamut-n2-beef456.vrp",
                "meta": "benchmarks/VRPTW/Mamut2026/sidecars/brest/n=2/mamut-n2-beef456/mamut-n2-beef456.meta.json",
                "manifest": "benchmarks/VRPTW/Mamut2026/sidecars/brest/n=2/mamut-n2-beef456/mamut-n2-beef456.manifest.json",
            },
        },
    )


def make_historical_instance() -> BenchmarkInstance:
    return BenchmarkInstance(
        instance_name="C101",
        instance_origin="Solomon1987",
        benchmark_name="Sintef2008",
        num_customers=2,
        num_vehicles=2,
        vehicle_capacity=10,
        coordinates=[(0, 0), (1, 1), (2, 2)],
        demands=[0, 1, 2],
        service_times=[0, 10, 10],
        time_windows=[(0, 100), (0, 100), (0, 100)],
        depot=0,
        arc_costs=[[0, 1, 2], [1, 0, 3], [2, 3, 0]],
    )


def make_bks(instance_name: str, objective_function: ObjectiveFunction, method: str) -> BenchmarkBKS:
    return BenchmarkBKS(
        instance_name=instance_name,
        objective_function=objective_function,
        routes=[[1, 2]],
        cost=12,
        metadata={
            "authors": "Florian Rascoussier (0nyr) and Adrien Pichon (Anzury)",
            "source": "fixture",
            "method": method,
            "validated_num_routes": 1,
        },
    )


def _write_fixture_tree(source_repo_dir: Path) -> None:
    generated_cvrp = make_generated_cvrp_instance()
    generated_vrptw = make_generated_vrptw_instance()
    historical = make_historical_instance()

    generated_cvrp_path = (
        source_repo_dir
        / "benchmarks"
        / "CVRP"
        / "Mamut2026"
        / "fastest"
        / "brest"
        / "n=2"
        / generated_cvrp.instance_name
        / f"{generated_cvrp.instance_name}.vrp.json"
    )
    generated_vrptw_path = (
        source_repo_dir
        / "benchmarks"
        / "VRPTW"
        / "Mamut2026"
        / "fastest"
        / "brest"
        / "n=2"
        / generated_vrptw.instance_name
        / f"{generated_vrptw.instance_name}.vrp.json"
    )
    historical_path = (
        source_repo_dir
        / "benchmarks"
        / "VRPTW"
        / "Sintef2008"
        / "n=2"
        / "C101.vrp.json"
    )

    save_json_to_file(generated_cvrp.model_dump(mode="json"), generated_cvrp_path)
    save_json_to_file(generated_vrptw.model_dump(mode="json"), generated_vrptw_path)
    save_json_to_file(historical.model_dump(mode="json"), historical_path)

    generated_cvrp_path.with_suffix("").write_text("NAME : fixture\n", encoding="utf-8")
    generated_vrptw_path.with_suffix("").write_text("NAME : fixture\n", encoding="utf-8")
    save_json_to_file(
        make_bks(generated_cvrp.instance_name, ObjectiveFunction.MONO_COST, "hgs-v1").model_dump(mode="json"),
        generated_cvrp_path.with_name(f"{generated_cvrp.instance_name}.bks.MonoCost.json"),
    )
    save_json_to_file(
        make_bks(generated_vrptw.instance_name, ObjectiveFunction.MONO_COST, "hgs-v3").model_dump(mode="json"),
        generated_vrptw_path.with_name(f"{generated_vrptw.instance_name}.bks.MonoCost.json"),
    )
    save_json_to_file(
        make_bks("C101", ObjectiveFunction.HIERARCHICAL_VEHICLE_COST, "fixture-historical").model_dump(mode="json"),
        historical_path.with_name("C101.bks.HierarchicalVehicleCost.json"),
    )


def test_generate_release_artifacts_writes_expected_archives_and_manifest(tmp_path: Path) -> None:
    source_repo_dir = tmp_path / "MAMUT-routing"
    output_dir = tmp_path / "release-assets"
    _write_fixture_tree(source_repo_dir)

    summary = generate_release_artifacts(
        source_repo_dir=source_repo_dir,
        output_dir=output_dir,
        source_commit="abcdef123456",
        published_at="2026-04-24T12:00:00+00:00",
        snapshot_id="2026-04-24-abcdef1",
        source_branch="main",
        release_tag="snapshot-2026-04-24",
        download_base_url="https://example.invalid/releases/download/snapshot-2026-04-24",
    )

    manifest = load_release_manifest(output_dir / "snapshot-manifest.json")

    assert summary.archive_count == 6
    assert manifest.snapshot_id == "2026-04-24-abcdef1"
    assert sorted(asset.filename for asset in manifest.assets) == [
        "CVRP-Mamut2026-snapshot-2026-04-24-abcdef1.zip",
        "CVRP-snapshot-2026-04-24-abcdef1.zip",
        "Mamut2026-snapshot-2026-04-24-abcdef1.zip",
        "VRPTW-Mamut2026-snapshot-2026-04-24-abcdef1.zip",
        "VRPTW-Sintef2008-snapshot-2026-04-24-abcdef1.zip",
        "VRPTW-snapshot-2026-04-24-abcdef1.zip",
    ]
    for asset in manifest.assets:
        assert asset.download_url.endswith(asset.filename)
        assert asset.size_bytes is not None and asset.size_bytes > 0
        assert asset.checksum_sha256 is not None

    family_archive = output_dir / "Mamut2026-snapshot-2026-04-24-abcdef1.zip"
    with zipfile.ZipFile(family_archive, "r") as archive:
        names = sorted(archive.namelist())

    assert "benchmarks/CVRP/Mamut2026/fastest/brest/n=2/mamut-n2-cafe123/mamut-n2-cafe123.vrp.json" in names
    assert "benchmarks/VRPTW/Mamut2026/fastest/brest/n=2/mamut-n2-beef456/mamut-n2-beef456.vrp.json" in names


def test_generate_release_artifacts_is_deterministic_for_same_snapshot(tmp_path: Path) -> None:
    source_repo_dir = tmp_path / "MAMUT-routing"
    first_output_dir = tmp_path / "release-assets-first"
    second_output_dir = tmp_path / "release-assets-second"
    _write_fixture_tree(source_repo_dir)

    first = generate_release_artifacts(
        source_repo_dir=source_repo_dir,
        output_dir=first_output_dir,
        source_commit="abcdef123456",
        published_at="2026-04-24T12:00:00+00:00",
        snapshot_id="2026-04-24-abcdef1",
    )
    second = generate_release_artifacts(
        source_repo_dir=source_repo_dir,
        output_dir=second_output_dir,
        source_commit="abcdef123456",
        published_at="2026-04-24T12:00:00+00:00",
        snapshot_id="2026-04-24-abcdef1",
    )

    assert first.archive_count == second.archive_count
    first_manifest = (first_output_dir / "snapshot-manifest.json").read_text(encoding="utf-8")
    second_manifest = (second_output_dir / "snapshot-manifest.json").read_text(encoding="utf-8")
    assert first_manifest == second_manifest

    for filename in [
        "CVRP-snapshot-2026-04-24-abcdef1.zip",
        "VRPTW-snapshot-2026-04-24-abcdef1.zip",
        "Mamut2026-snapshot-2026-04-24-abcdef1.zip",
    ]:
        assert (first_output_dir / filename).read_bytes() == (second_output_dir / filename).read_bytes()


def test_validate_release_asset_size_warns_at_1point5_gib() -> None:
    with pytest.warns(UserWarning, match="1.5 GiB warning threshold"):
        _validate_release_asset_size(
            "large-warning.zip",
            GITHUB_RELEASE_ASSET_WARNING_SIZE_BYTES,
        )


def test_validate_release_asset_size_raises_at_2_gib_or_above() -> None:
    with pytest.raises(ValueError, match="2 GiB per-asset limit"):
        _validate_release_asset_size(
            "too-large.zip",
            GITHUB_RELEASE_ASSET_MAX_SIZE_BYTES,
        )
