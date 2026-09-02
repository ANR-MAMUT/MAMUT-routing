"""The lib's CVRPLIB writer must reproduce every ``.vrp`` committed next to the
collection CVRP instances byte for byte (header order, COMMENT reconstruction,
3-decimal costs, 6-decimal ENU coordinates)."""

from __future__ import annotations

from pathlib import Path

import pytest

from mamut_routing_lib.cvrplib import export_instance_file

REPO_ROOT = Path(__file__).resolve().parents[1]
BENCHMARKS = REPO_ROOT / "benchmarks"


def _committed_vrp_files() -> list[Path]:
    if not BENCHMARKS.is_dir():
        return []
    return sorted(path for path in BENCHMARKS.rglob("*.vrp") if path.with_name(f"{path.name}.json").is_file())


@pytest.mark.skipif(not _committed_vrp_files(), reason="no committed .vrp files (benchmark satellites not checked out)")
def test_export_reproduces_every_committed_vrp_byte_for_byte(tmp_path: Path) -> None:
    mismatches: list[str] = []
    for committed in _committed_vrp_files():
        source = committed.with_name(f"{committed.name}.json")
        target = tmp_path / committed.relative_to(BENCHMARKS)
        result = export_instance_file(source, target)
        assert result.status == "written", (source, result.message)
        if target.read_bytes() != committed.read_bytes():
            mismatches.append(str(committed.relative_to(REPO_ROOT)))
    assert not mismatches, f"{len(mismatches)} committed .vrp differ from the export: {mismatches[:5]}"
