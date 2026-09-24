"""A published release, fetched by the lib CLI, is the tree the site was built from.

Before lib 0.12, ``remote fetch`` extracted every archive under
``<benchmarks-dir>/<archive stem>/benchmarks/...``, so discovery on a fetched
dir raised or produced other IDs than the site. This builds the release
assets with the publisher, serves them over ``file://`` to the real CLI and
checks that the fetched tree discovers, lists, hydrates and verifies exactly
like the source, for a September-shaped repo (family-first collection) and a
May-shaped one (problem-type-first Poryos2026), with and without
``archive_root`` in the manifest.
"""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

import pytest
from mamut_routing_lib import discover_benchmark_instances
from mamut_routing_lib.artifacts import (
    hydrate_collection_instance,
    load_benchmark_instance,
)
from mamut_routing_lib.cli import app
from mamut_routing_lib.json_utils import save_json_to_file
from mamut_routing_lib.remote import GitHubReleaseClient
from mamut_routing_lib.sidecars import find_collection_root
from test_release_artifacts import _write_fixture_tree
from typer.testing import CliRunner

from mamut_routing_publish.release_artifacts import generate_release_artifacts

LIB_TESTS = Path(__file__).resolve().parents[1] / "MAMUT-routing-lib" / "tests"
SNAPSHOT_ID = "2026-09-24-abcdef1"


def _write_september_tree(source: Path) -> None:
    sys.path.insert(0, str(LIB_TESTS))
    try:
        from collection_utils import write_toy_collection
    finally:
        sys.path.remove(str(LIB_TESTS))
    write_toy_collection(source)


def _ids(benchmarks_dir: Path) -> dict[str, str]:
    return {
        item.instance_id: item.instance_path.relative_to(benchmarks_dir).as_posix()
        for item in discover_benchmark_instances(benchmarks_dir)
    }


@pytest.fixture
def serve_releases(monkeypatch: pytest.MonkeyPatch):
    """Point the release client's manifest URL at a local assets dir."""

    def serve(assets_dir: Path) -> None:
        monkeypatch.setattr(
            GitHubReleaseClient, "_build_release_asset_url", lambda self, tag, name: (assets_dir / name).as_uri()
        )

    return serve


def _remote(benchmarks_dir: Path, *args: str):
    result = CliRunner().invoke(app, ["--benchmarks-dir", str(benchmarks_dir), "remote", "--tag", "t", *args])
    return result


@pytest.mark.parametrize("shape", ["september", "may"])
@pytest.mark.parametrize("with_archive_root", [True, False], ids=["archive_root", "legacy-manifest"])
def test_fetched_release_is_the_source_tree(tmp_path: Path, serve_releases, shape: str, with_archive_root: bool) -> None:
    source = tmp_path / "source"
    if shape == "september":
        _write_september_tree(source)
    else:
        _write_fixture_tree(source)
    # Local state a maintainer's tree may hold must not ship.
    family_dir = next(path for path in (source / "benchmarks").glob("*/*") if path.is_dir())
    (family_dir / ".mamut-release.json").write_text("{}", encoding="utf-8")
    (source / "benchmarks" / ".mamut-staging" / "x").mkdir(parents=True)
    (source / "benchmarks" / ".mamut-staging" / "x" / "leftover.vrp.json").write_text("{}", encoding="utf-8")

    assets_dir = tmp_path / "assets"
    generate_release_artifacts(
        source_repo_dir=source,
        output_dir=assets_dir,
        source_commit="abcdef123456",
        published_at="2026-09-24T12:00:00+00:00",
        snapshot_id=SNAPSHOT_ID,
        download_base_url=assets_dir.as_uri(),
    )
    manifest_path = assets_dir / "snapshot-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for asset in manifest["assets"]:
        with zipfile.ZipFile(assets_dir / asset["filename"]) as archive:
            assert not [name for name in archive.namelist() if ".mamut-" in name]
        if not with_archive_root:
            asset.pop("archive_root")
    save_json_to_file(manifest, manifest_path, sort_keys=True)
    serve_releases(assets_dir)

    fetched = tmp_path / "fetched"
    result = _remote(fetched, "fetch", "--all")
    assert result.exit_code == 0, result.output
    assert not (fetched / ".mamut-staging").exists()
    expected = _ids(source / "benchmarks")
    assert _ids(fetched) == expected

    listed = CliRunner().invoke(app, ["--benchmarks-dir", str(fetched), "list", "--show-path", "--no-summary"])
    assert listed.exit_code == 0, listed.output
    for instance_id in expected:
        assert instance_id in listed.output

    for relative in expected.values():
        path = fetched / relative
        instance = load_benchmark_instance(path)
        if find_collection_root(path) is not None and getattr(instance, "td", None) is None:
            assert hydrate_collection_instance(instance, path).arc_costs is not None

    verified = _remote(fetched, "verify")
    assert verified.exit_code == 0, verified.output
    assert "MISSING" not in verified.output and "STALE" not in verified.output

    # Re-fetching replaces the stamped trees in place.
    again = _remote(fetched, "fetch", "--all")
    assert again.exit_code == 0, again.output
    assert _ids(fetched) == expected
