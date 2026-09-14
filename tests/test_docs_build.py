"""The MkDocs build as a publisher phase: real strict build, staging isolation, CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

mkdocs = pytest.importorskip("mkdocs")

from mamut_routing_publish.cli import app  # noqa: E402
from mamut_routing_publish.docs_build import (  # noqa: E402
    DocsBuildError,
    build_docs_site,
    docs_output_dir,
    ensure_docs_tooling_available,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_tooling_available() -> None:
    ensure_docs_tooling_available()


@pytest.fixture(scope="module")
def built_docs(tmp_path_factory: pytest.TempPathFactory) -> Path:
    site_dir = tmp_path_factory.mktemp("site") / "docs"
    summary = build_docs_site(REPO_ROOT, site_dir, strict=True, quiet=True)
    assert summary.site_dir == site_dir
    assert summary.html_files_written > 50
    return site_dir


def test_build_writes_expected_pages(built_docs: Path) -> None:
    for rel in (
        "index.html",
        "benchmarks/families/index.html",
        "benchmarks/families/vrptw/sintef2008/index.html",
        "reference/cli/mamut-routing/index.html",
        "reference/api/lib/td/checker/index.html",
        "user-guide/faq/index.html",
        "search/search_index.json",
    ):
        assert (built_docs / rel).is_file(), rel
    cli_page = (built_docs / "reference/cli/mamut-routing/index.html").read_text(encoding="utf-8")
    assert "export vrp" in cli_page or "export" in cli_page
    assert "--benchmarks-dir" in cli_page
    checker_page = (built_docs / "reference/api/lib/td/checker/index.html").read_text(encoding="utf-8")
    assert "check_td_solution" in checker_page


def test_build_only_writes_inside_site_dir(built_docs: Path) -> None:
    assert not (built_docs.parent / "index.html").exists()
    assert sorted(p.name for p in built_docs.parent.iterdir()) == ["docs"]


def test_build_missing_config_raises(tmp_path: Path) -> None:
    with pytest.raises(DocsBuildError, match="configuration not found"):
        build_docs_site(tmp_path, tmp_path / "out")


def test_site_docs_cli_builds_under_staging_dir(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    live_docs = REPO_ROOT / "dist" / "docs"
    live_mtime = live_docs.stat().st_mtime if live_docs.exists() else None
    result = CliRunner().invoke(
        app,
        ["site", "docs", "--output-repo-dir", str(REPO_ROOT), "--site-output-dir", str(staging), "--quiet"],
    )
    assert result.exit_code == 0, result.output
    summary = json.loads(result.output)
    assert Path(summary["site_dir"]) == docs_output_dir(staging)
    assert (staging / "docs" / "index.html").is_file()
    if live_mtime is not None:
        assert live_docs.stat().st_mtime == live_mtime


def _broken_docs_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "docs").mkdir(parents=True)
    (repo / "mkdocs.yml").write_text("site_name: fixture\n", encoding="utf-8")
    (repo / "docs" / "index.md").write_text("# Home\n\n[Broken](missing.md)\n", encoding="utf-8")
    return repo


@pytest.mark.parametrize("quiet", [False, True])
def test_strict_build_fails_on_broken_link_regardless_of_quiet(tmp_path: Path, quiet: bool) -> None:
    # --quiet must silence the console only; strict mode still counts the warning.
    repo = _broken_docs_repo(tmp_path)
    with pytest.raises(DocsBuildError, match="strict"):
        build_docs_site(repo, tmp_path / "out", strict=True, quiet=quiet)


def test_non_strict_build_tolerates_broken_link(tmp_path: Path) -> None:
    repo = _broken_docs_repo(tmp_path)
    summary = build_docs_site(repo, tmp_path / "out", strict=False, quiet=True)
    assert summary.html_files_written >= 1
