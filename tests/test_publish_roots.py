"""Publication-root separation: staging builds must not write the active dist,
and persistent state (history ledger, inventories) must survive fresh release
directories."""

from __future__ import annotations

import json
import os
from pathlib import Path

from mamut_routing_publish.publish_roots import PublishRoots, hardlink_tree, migrate_legacy_state
from mamut_routing_publish.site_payloads import generate_site_payloads

from test_site_payloads import build_fixture_site_inputs


def _tree_signature(root: Path) -> dict[str, tuple[int, int]]:
    """Map of relative path -> (size, mtime_ns) for every file under root."""
    signature: dict[str, tuple[int, int]] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            stat = path.stat()
            signature[path.relative_to(root).as_posix()] = (stat.st_size, stat.st_mtime_ns)
    return signature


def test_publish_roots_defaults_and_in_place(tmp_path: Path) -> None:
    roots = PublishRoots.resolve(tmp_path)
    assert roots.site_output == tmp_path / "dist"
    assert roots.state_dir == tmp_path / "publish-state"
    assert roots.in_place is True

    staged = PublishRoots.resolve(tmp_path, site_output_dir=tmp_path / "releases" / "dist-1")
    assert staged.in_place is False
    assert staged.active_dist == tmp_path / "dist"


def test_hardlink_tree_is_idempotent_and_preserves_existing(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    (source / "sub").mkdir(parents=True)
    (source / "a.json").write_text("alpha")
    (source / "sub" / "b.json").write_text("beta")
    (target / "sub").mkdir(parents=True)
    (target / "sub" / "b.json").write_text("already-there")

    linked = hardlink_tree(source, target)
    assert linked == 1
    assert (target / "a.json").read_text() == "alpha"
    assert (target / "sub" / "b.json").read_text() == "already-there"
    assert hardlink_tree(source, target) == 0


def test_staging_build_never_writes_active_dist(tmp_path: Path) -> None:
    output_repo_dir = tmp_path / "MAMUT-routing"
    build_fixture_site_inputs(output_repo_dir)

    generate_site_payloads(
        output_repo_dir=output_repo_dir,
        source_commit="inplacecommit",
        published_at="2026-04-23T12:00:00",
        snapshot_id="2026-04-23-inplace1",
    )
    active_dist = output_repo_dir / "dist"
    # Simulate previously materialized caches the payloads may reference.
    fake_atf = active_dist / "atf-cache" / "Mamut2026" / "fake.atf.json.gz"
    fake_atf.parent.mkdir(parents=True, exist_ok=True)
    fake_atf.write_bytes(b"gzipped-bytes")
    fake_geometry = active_dist / "route-geometry-cache" / "ab" / "abcdef.json"
    fake_geometry.parent.mkdir(parents=True, exist_ok=True)
    fake_geometry.write_text("{}")
    before = _tree_signature(active_dist)

    staging_dir = tmp_path / "releases" / "dist-20260718"
    generate_site_payloads(
        output_repo_dir=output_repo_dir,
        source_commit="stagingcommit",
        published_at="2026-04-30T12:00:00",
        snapshot_id="2026-04-30-staging1",
        site_output_dir=staging_dir,
    )

    assert _tree_signature(active_dist) == before
    assert (staging_dir / "site" / "history.json").is_file()
    assert (staging_dir / "site-payloads" / "index.json").is_file()
    # Caches are seeded into the staging output (hardlink or copy).
    assert (staging_dir / "atf-cache" / "Mamut2026" / "fake.atf.json.gz").is_file()
    assert (staging_dir / "route-geometry-cache" / "ab" / "abcdef.json").is_file()


def test_history_survives_fresh_release_dirs(tmp_path: Path) -> None:
    output_repo_dir = tmp_path / "MAMUT-routing"
    build_fixture_site_inputs(output_repo_dir)

    first_release = tmp_path / "releases" / "dist-1"
    generate_site_payloads(
        output_repo_dir=output_repo_dir,
        source_commit="firstcommit01",
        published_at="2026-04-23T12:00:00",
        snapshot_id="2026-04-23-firstcom",
        site_output_dir=first_release,
    )
    second_release = tmp_path / "releases" / "dist-2"
    generate_site_payloads(
        output_repo_dir=output_repo_dir,
        source_commit="secondcommit2",
        published_at="2026-04-30T12:00:00",
        snapshot_id="2026-04-30-secondc",
        site_output_dir=second_release,
    )

    ledger = json.loads((second_release / "site" / "history.json").read_text(encoding="utf-8"))
    assert [entry["snapshot"]["snapshot_id"] for entry in ledger["entries"]] == [
        "2026-04-30-secondc",
        "2026-04-23-firstcom",
    ]
    second_detail = json.loads(
        (second_release / "site-payloads" / "history" / "2026-04-30-secondc" / "index.json").read_text(
            encoding="utf-8"
        )
    )
    assert second_detail["change_log"]["is_initial"] is False
    # State lives outside the release directories.
    state_dir = output_repo_dir / "publish-state"
    assert (state_dir / "history.json").is_file()
    assert (state_dir / "snapshots" / "2026-04-23-firstcom.inventory.json").is_file()
    assert (state_dir / "snapshots" / "2026-04-30-secondc.inventory.json").is_file()


def test_legacy_state_migrates_from_dist_site(tmp_path: Path) -> None:
    output_repo_dir = tmp_path / "MAMUT-routing"
    build_fixture_site_inputs(output_repo_dir)

    # A pre-roots build kept the ledger and inventories inside dist/site/.
    generate_site_payloads(
        output_repo_dir=output_repo_dir,
        source_commit="firstcommit01",
        published_at="2026-04-23T12:00:00",
        snapshot_id="2026-04-23-firstcom",
    )
    state_dir = output_repo_dir / "publish-state"
    legacy_site = output_repo_dir / "dist" / "site"
    (legacy_site / "snapshots").mkdir(parents=True, exist_ok=True)
    os.rename(state_dir / "history.json", legacy_site / "history.json")
    os.rename(
        state_dir / "snapshots" / "2026-04-23-firstcom.inventory.json",
        legacy_site / "snapshots" / "2026-04-23-firstcom.inventory.json",
    )
    (state_dir / "snapshots").rmdir()
    state_dir.rmdir()

    roots = PublishRoots.resolve(output_repo_dir)
    assert migrate_legacy_state(roots) is True
    assert roots.history_path.is_file()
    assert (roots.snapshots_dir / "2026-04-23-firstcom.inventory.json").is_file()
    # Second call is a no-op once state exists.
    assert migrate_legacy_state(roots) is False

    generate_site_payloads(
        output_repo_dir=output_repo_dir,
        source_commit="secondcommit2",
        published_at="2026-04-30T12:00:00",
        snapshot_id="2026-04-30-secondc",
    )
    ledger = json.loads(roots.history_path.read_text(encoding="utf-8"))
    assert [entry["snapshot"]["snapshot_id"] for entry in ledger["entries"]] == [
        "2026-04-30-secondc",
        "2026-04-23-firstcom",
    ]
