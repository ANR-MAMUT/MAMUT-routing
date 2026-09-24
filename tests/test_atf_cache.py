"""The build-time ATF cache reuses an entry only when it holds the pinned functions.

Before: any file at the entry's path was trusted, so a stale entry (the family
was regenerated, the pin moved) or a truncated one (a killed build) was served
forever, and a staging build seeded by hard links truncated the live cache in
place when it rewrote an entry. Now reused entries are hashed against the
instance's ``atf_sha256``, writes are atomic, and ``*.partial`` leftovers are
removed and never seeded.
"""

from __future__ import annotations

import gzip
import json
import random
import warnings
from pathlib import Path

import pytest
from mamut_routing_lib.json_utils import save_json_to_file
from mamut_routing_lib.td import (
    InstanceCategories,
    compute_atf_sha256,
    compute_categories_sha256,
    materialize_instance_atfs,
    save_instance_categories,
    td_instance_from_payload,
)
from mamut_routing_lib.td.artifacts import atf_file_sha256

from mamut_routing_publish import site_payloads
from mamut_routing_publish.atf_cache import atf_cache_file, materialize_atf_cache

PERIODS = [[0.0, 100.0], [100.0, 200.0], [200.0, 300.0]]
SPEEDS = [[0.33, 0.67, 0.33], [0.67, 1.33, 0.67], [1.33, 2.67, 1.33]]


def _categories() -> InstanceCategories:
    rng = random.Random(42)
    rows = [["0"] * 4 for _ in range(4)]
    for i in range(4):
        for j in range(i + 1, 4):
            rows[i][j] = rows[j][i] = str(rng.getrandbits(32) % 3)
    return InstanceCategories(
        base_name="Lera-TOY",
        benchmark_name="Lera2026",
        num_customers=3,
        num_categories=3,
        categories=["".join(row) for row in rows],
        generator={"name": "test-fixture", "seed": 42},
    )


def _write_twins(repo: Path) -> str:
    """A TDVRPTW/TDVRP igp-profile pair under ``repo/benchmarks``; returns the shared pin."""
    categories = _categories()
    pin = None
    for problem_type in ("TDVRPTW", "TDVRP"):
        directory = repo / "benchmarks" / problem_type / "Lera2026" / "n=3"
        directory.mkdir(parents=True)
        save_instance_categories(categories, directory / "Lera-TOY.igp.json")
        payload = {
            "instance_name": "Lera-TOY-S2",
            "instance_origin": "GehHom1999",
            "benchmark_name": "Lera2026",
            "num_customers": 3,
            "num_vehicles": 2,
            "vehicle_capacity": 10,
            "coordinates": [[0, 0], [40, 0], [40, 30], [0, 30]],
            "demands": [0, 4, 4, 2],
            "service_times": [0, 10, 10, 10],
            "depot": 0,
            "horizon": [0.0, 300.0],
            "td": {
                "model": "igp-profile",
                "time_periods": PERIODS,
                "speeds": SPEEDS,
                "categories_path": "Lera-TOY.igp.json",
                "categories_sha256": compute_categories_sha256(categories),
            },
            "metadata": {},
        }
        if problem_type == "TDVRPTW":
            payload["time_windows"] = [[0, 300]] * 4
        pin = compute_atf_sha256(materialize_instance_atfs(td_instance_from_payload(payload), categories))
        payload["td"]["atf_sha256"] = pin
        save_json_to_file(payload, directory / "Lera-TOY-S2.vrp.json")
    return pin


def _entry(cache_dir: Path) -> Path:
    return atf_cache_file(cache_dir, "Lera2026", "Lera-TOY-S2")


def _build(repo: Path, **kwargs):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        summary = materialize_atf_cache(repo, jobs=1, **kwargs)
    return summary, [str(w.message) for w in caught]


def test_twins_share_one_verified_entry_and_rebuilds_reuse_it(tmp_path: Path) -> None:
    pin = _write_twins(tmp_path)
    cache_dir = tmp_path / "dist" / "atf-cache"
    summary, _ = _build(tmp_path)
    assert summary.as_dict() == {
        "materialized": 1,
        "reused": 0,
        "invalidated": 0,
        "skipped_over_cap": 0,
        "removed_partials": 0,
    }
    assert atf_file_sha256(_entry(cache_dir)) == pin
    again, messages = _build(tmp_path)
    assert (len(again.materialized), len(again.reused), len(again.invalidated)) == (0, 1, 0)
    assert messages == []


@pytest.mark.parametrize("damage", ["truncated", "stale"])
def test_a_damaged_entry_is_regenerated(tmp_path: Path, damage: str) -> None:
    pin = _write_twins(tmp_path)
    _build(tmp_path)
    entry = _entry(tmp_path / "dist" / "atf-cache")
    if damage == "truncated":
        entry.write_bytes(entry.read_bytes()[:-40])
    else:
        # Valid gzip, other functions: what a pin move after a family rebuild leaves behind.
        content = json.loads(gzip.decompress(entry.read_bytes()))
        content["generator"] = {"name": "an older build"}
        entry.write_bytes(gzip.compress(json.dumps(content).encode(), mtime=0))
    summary, messages = _build(tmp_path)
    assert summary.invalidated == [str(entry)]
    assert summary.materialized == [str(entry)]
    assert summary.reused == []
    assert any("Regenerating ATF cache entry" in message for message in messages)
    assert atf_file_sha256(entry) == pin


def test_a_staging_rebuild_never_touches_the_live_cache(tmp_path: Path) -> None:
    _write_twins(tmp_path)
    live = tmp_path / "dist" / "atf-cache"
    _build(tmp_path)
    live_entry = _entry(live)
    live_entry.write_bytes(live_entry.read_bytes()[:-40])  # a damaged live entry
    damaged = live_entry.read_bytes()
    (live_entry.parent / "Lera-TOY-S2.atf.json.gz.123.456.partial").write_bytes(b"half")

    staging = tmp_path / "staging" / "atf-cache"
    summary, _ = _build(tmp_path, cache_dir=staging, seed_from=live)
    assert summary.invalidated == [str(_entry(staging))]
    assert live_entry.read_bytes() == damaged
    assert not list(staging.rglob("*.partial"))


def test_partial_leftovers_are_removed(tmp_path: Path) -> None:
    _write_twins(tmp_path)
    cache_dir = tmp_path / "dist" / "atf-cache"
    leftover = _entry(cache_dir).with_name("Lera-TOY-S2.atf.json.gz.99.1.partial")
    leftover.parent.mkdir(parents=True)
    leftover.write_bytes(b"half")
    summary, _ = _build(tmp_path)
    assert summary.removed_partials == 1
    assert not leftover.exists()


def test_pages_ignore_a_sidecar_that_misses_its_pin(tmp_path: Path) -> None:
    pin = _write_twins(tmp_path)
    _build(tmp_path)
    entry = _entry(tmp_path / "dist" / "atf-cache")
    site_payloads._reset_resolution_memos()
    assert site_payloads._load_td_atfs(entry, pin) is not None
    site_payloads._reset_resolution_memos()
    with pytest.warns(UserWarning, match="without the BKS schedule table"):
        assert site_payloads._load_td_atfs(entry, "0" * 64) is None
    assert site_payloads._TD_ATFS_MEMO == {}
    entry.write_bytes(entry.read_bytes()[:-40])
    with pytest.warns(UserWarning, match="corrupt or truncated gzip"):
        assert site_payloads._load_td_atfs(entry, pin) is None
