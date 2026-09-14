"""Generated documentation pages: single-sourcing, satellite fallback, nav stability."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mamut_routing_publish.docs_pages import (
    GITHUB_ORG_URL,
    MAIN_REPO_URL,
    PROJECT_PAGE_DOC_PATHS,
    family_pages,
    generate_docs_pages,
    github_bases_for_path,
    github_https_url,
    package_readme_pages,
    parse_gitmodules,
    project_pages,
    reports_pages,
    rewrite_relative_links,
    shift_headings,
)
from mamut_routing_publish.site_payloads import PROJECT_PAGE_SOURCES

def _fixture_repo(tmp_path: Path, *, families_markdown: str) -> Path:
    repo = tmp_path / "MAMUT-routing"
    (repo / "src" / "mamut_routing_publish" / "site_assets" / "texts").mkdir(parents=True)
    (repo / ".gitmodules").write_text(
        """[submodule "benchmarks/TDVRPTW/Ari2018"]
\tpath = benchmarks/TDVRPTW/Ari2018
\turl = git@github.com:ANR-MAMUT/MAMUT-routing-TDVRPTW-Ari2018.git
[submodule "benchmarks/Poryos2026"]
\tpath = benchmarks/Poryos2026
\turl = git@github.com:ANR-MAMUT/MAMUT-routing-Poryos2026.git
[submodule "MAMUT-routing-tools"]
\tpath = MAMUT-routing-tools
\turl = ../MAMUT-routing-tools.git
""",
        encoding="utf-8",
    )
    (repo / "AUTHORS.md").write_text("# Authors\n\nSomeone.\n", encoding="utf-8")
    (repo / "benchmarks" / "VRPTW" / "Sintef2008").mkdir(parents=True)
    (repo / "benchmarks" / "VRPTW" / "Sintef2008" / "README.md").write_text(
        "# Sintef2008\n\nSee [LICENSE](LICENSE) and ![plot](img/plot.png).\n\n## Format\n\n```text\n# not a heading\n```\n",
        encoding="utf-8",
    )
    (repo / "benchmarks" / "TDVRPTW" / "Ari2018").mkdir(parents=True)  # empty: uninitialised satellite
    (repo / "benchmarks" / "Poryos2026").mkdir(parents=True)
    (repo / "benchmarks" / "Poryos2026" / "README.md").write_text(
        "# Poryos2026 collection\n\nLayout in [CVRP](CVRP/).\n", encoding="utf-8"
    )
    (repo / "docs" / "reports").mkdir(parents=True)
    (repo / "docs" / "reports" / "2026-01-05-older.md").write_text("# Older report\n", encoding="utf-8")
    (repo / "docs" / "reports" / "2026-03-01-newer.md").write_text("# Newer report\n\ntext\n", encoding="utf-8")
    (repo / "docs" / "reports" / "notes.md").write_text("# Not dated\n", encoding="utf-8")
    return repo


@pytest.fixture()
def families_report(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    report = tmp_path / "families.md"
    report.write_text(
        """# Benchmark families

### `Sintef2008` (VRPTW)

SINTEF context paragraph.

#### Sub-heading

Detail.

### `Ari2018` (TDVRPTW)

Ari context paragraph.

### `Poryos2026` (CVRP)

Collection CVRP layer.

### `Poryos2026` (VRPTW)

Collection VRPTW layer.
""",
        encoding="utf-8",
    )
    import mamut_routing_publish.site_payloads as site_payloads

    monkeypatch.setattr(site_payloads, "DEFAULT_FAMILY_CONTEXT_REPORT_PATH", report)
    return report


def test_shift_headings_skips_fenced_code() -> None:
    text = "# A\n\n```md\n# not\n```\n\n### C\n"
    assert shift_headings(text, 1) == "## A\n\n```md\n# not\n```\n\n#### C\n"
    assert shift_headings(text, -2) == "# A\n\n```md\n# not\n```\n\n# C\n"


def test_rewrite_relative_links_targets_github_and_keeps_absolute() -> None:
    text = "[a](docs/x.md) [b](./y.md) ![c](img.png) [d](https://e.org) [e](#anchor) [f](/site/) [g](mailto:x@y.z)"
    out = rewrite_relative_links(text, blob_base="https://g/blob/main", raw_base="https://r/main")
    assert "[a](https://g/blob/main/docs/x.md)" in out
    assert "[b](https://g/blob/main/y.md)" in out
    assert "![c](https://r/main/img.png)" in out
    assert "[d](https://e.org)" in out and "[e](#anchor)" in out and "[f](/site/)" in out and "[g](mailto:x@y.z)" in out


def test_github_url_forms() -> None:
    assert github_https_url("git@github.com:ANR-MAMUT/X.git") == "https://github.com/ANR-MAMUT/X"
    assert github_https_url("../MAMUT-routing-tools.git") == f"{GITHUB_ORG_URL}/MAMUT-routing-tools"
    assert github_https_url("https://github.com/ANR-MAMUT/Y") == "https://github.com/ANR-MAMUT/Y"


def test_github_bases_for_submodule_and_in_repo_paths(tmp_path: Path, families_report: Path) -> None:
    repo = _fixture_repo(tmp_path, families_markdown="")
    assert parse_gitmodules(repo)["benchmarks/TDVRPTW/Ari2018"] == f"{GITHUB_ORG_URL}/MAMUT-routing-TDVRPTW-Ari2018"
    browse, blob, raw = github_bases_for_path(repo, "benchmarks/TDVRPTW/Ari2018")
    assert browse == f"{GITHUB_ORG_URL}/MAMUT-routing-TDVRPTW-Ari2018"
    assert blob == f"{GITHUB_ORG_URL}/MAMUT-routing-TDVRPTW-Ari2018/blob/main"
    assert raw == "https://raw.githubusercontent.com/ANR-MAMUT/MAMUT-routing-TDVRPTW-Ari2018/main"
    browse, blob, _raw = github_bases_for_path(repo, "benchmarks/VRPTW/Sintef2008")
    assert browse == f"{MAIN_REPO_URL}/tree/main/benchmarks/VRPTW/Sintef2008"
    assert blob == f"{MAIN_REPO_URL}/blob/main/benchmarks/VRPTW/Sintef2008"


def test_family_pages_embed_readme_stub_absent_and_collection(tmp_path: Path, families_report: Path) -> None:
    repo = _fixture_repo(tmp_path, families_markdown="")
    pages = {page.path: page.markdown for page in family_pages(repo)}

    sintef = pages["benchmarks/families/vrptw/sintef2008.md"]
    assert sintef.startswith("# Sintef2008 (VRPTW)\n")
    assert "\n## Sub-heading\n" in sintef  # #### demoted to ##
    assert "## Repository README" in sintef
    assert f"[LICENSE]({MAIN_REPO_URL}/blob/main/benchmarks/VRPTW/Sintef2008/LICENSE)" in sintef
    assert "![plot](https://raw.githubusercontent.com/ANR-MAMUT/MAMUT-routing/main/benchmarks/VRPTW/Sintef2008/img/plot.png)" in sintef
    assert "[/benchmarks/vrptw/sintef2008/](/benchmarks/vrptw/sintef2008/)" in sintef

    ari = pages["benchmarks/families/tdvrptw/ari2018.md"]
    assert "Not checked out in this build" in ari
    assert f"{GITHUB_ORG_URL}/MAMUT-routing-TDVRPTW-Ari2018" in ari

    cvrp = pages["benchmarks/families/cvrp/poryos2026.md"]
    assert "[collection page](../collections/poryos2026.md)" in cvrp
    assert "Repository README" not in cvrp
    collection = pages["benchmarks/families/collections/poryos2026.md"]
    assert collection.startswith("# Poryos2026 collection\n")
    assert f"[CVRP]({GITHUB_ORG_URL}/MAMUT-routing-Poryos2026/blob/main/CVRP/)" in collection

    summary = pages["benchmarks/families/SUMMARY.md"]
    for rel in ("vrptw/sintef2008.md", "tdvrptw/ari2018.md", "cvrp/poryos2026.md", "collections/poryos2026.md"):
        assert f"({rel})" in summary
        assert f"benchmarks/families/{rel}" in pages
    assert summary.splitlines()[0] == "* [Overview](index.md)"


def test_reports_index_newest_first_titles_from_heading(tmp_path: Path, families_report: Path) -> None:
    repo = _fixture_repo(tmp_path, families_markdown="")
    pages = {page.path: page.markdown for page in reports_pages(repo / "docs" / "reports")}
    index = pages["reports/index.md"]
    assert index.index("Newer report") < index.index("Older report")
    assert "2026-03-01-newer.md" in index and "notes.md" not in index
    summary = pages["reports/SUMMARY.md"]
    assert summary.splitlines()[1] == "* [2026-03-01 — Newer report](2026-03-01-newer.md)"


def test_reports_index_with_missing_dir(tmp_path: Path) -> None:
    pages = {page.path: page.markdown for page in reports_pages(tmp_path / "nope")}
    assert "No report yet." in pages["reports/index.md"]


def test_project_pages_mirror_website_sources(tmp_path: Path, families_report: Path) -> None:
    repo = _fixture_repo(tmp_path, families_markdown="")
    pages = {page.path: page.markdown for page in project_pages(repo)}
    assert set(pages) == {PROJECT_PAGE_DOC_PATHS[source.slug] for source in PROJECT_PAGE_SOURCES}
    assert pages["about/authors.md"].startswith("# Authors\n\nSomeone.")
    assert "[/project/authors/](/project/authors/)" in pages["about/authors.md"]
    assert pages["user-guide/faq.md"].startswith("# FAQ")  # the packaged website text


def test_package_readme_pages_stub_when_absent(tmp_path: Path, families_report: Path) -> None:
    repo = _fixture_repo(tmp_path, families_markdown="")
    pages = {page.path: page.markdown for page in package_readme_pages(repo)}
    assert "Not checked out in this build" in pages["developer-guide/packages/mamut-routing-lib.md"]
    assert f"{GITHUB_ORG_URL}/MAMUT-routing-tools" in pages["developer-guide/packages/mamut-routing-tools.md"]


def test_real_repo_every_summary_entry_is_generated() -> None:
    repo = Path(__file__).resolve().parents[1]
    pages = {page.path: page.markdown for page in generate_docs_pages(repo)}
    for summary_path, markdown in pages.items():
        if not summary_path.endswith("SUMMARY.md"):
            continue
        base = Path(summary_path).parent
        for line in markdown.splitlines():
            if "](" not in line:
                continue
            target = line.split("](", 1)[1].rstrip(")")
            generated = str(base / target) in pages
            on_disk = (repo / "docs" / base / target).is_file()  # e.g. the dated reports
            assert generated or on_disk, f"{summary_path} references missing {target}"
    # Every family section of the website has a documentation page.
    families = sum(1 for path in pages if path.startswith("benchmarks/families/") and "/" in path[len("benchmarks/families/"):] and not path.startswith("benchmarks/families/collections/"))
    assert families >= 19


def test_site_build_fails_fast_without_mkdocs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from mamut_routing_publish.cli import app

    (tmp_path / "mkdocs.yml").write_text("site_name: fixture\n", encoding="utf-8")
    monkeypatch.setitem(sys.modules, "mkdocs", None)
    result = CliRunner().invoke(
        app,
        ["site", "build", "--output-repo-dir", str(tmp_path), "--skip-atf-cache", "--skip-route-geometry", "--quiet"],
    )
    assert result.exit_code == 1
    assert "--skip-docs" in result.output
    assert not (tmp_path / "dist").exists()


def test_site_build_skips_docs_phase_without_mkdocs_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # A checkout without a documentation site (benchmark-only mirrors, test
    # fixtures) must build without the docs toolchain being consulted at all.
    from mamut_routing_publish.cli import app

    monkeypatch.setitem(sys.modules, "mkdocs", None)
    result = CliRunner().invoke(
        app,
        ["site", "build", "--output-repo-dir", str(tmp_path), "--skip-atf-cache", "--skip-route-geometry", "--quiet"],
    )
    assert "--skip-docs" not in result.output
    assert "MkDocs" not in result.output
