"""Generated pages of the documentation site.

The MkDocs site (``docs/`` + ``mkdocs.yml``) is hand-written where prose has
no other home, and *generated* wherever the text already lives somewhere
else, so nothing is duplicated:

- the website's project pages (FAQ, glossary, citing, authors, ...) come from
  ``site_assets/texts/project_pages`` and ``AUTHORS.md``, the same files the
  website renders;
- one page per benchmark family comes from the family sections of
  ``site_assets/texts/mamut-routing_benchmark_families.md`` (the website's
  family "context" pages), followed by the family's own README when its
  satellite submodule is checked out, or a stub pointing at GitHub when it
  is not (a plain clone leaves satellite directories empty; the docs build
  must never fail because of that);
- the README of the two tooling packages (lib, tools) as-is;
- an index of the dated engineering reports under ``docs/reports/``;
- one API-reference page per module for the curated package list.

Everything here is pure (paths in, markdown out) so it is unit-tested
without MkDocs; ``docs/_scripts/gen_pages.py`` is the thin ``gen-files``
driver that writes the pages.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from mamut_routing_lib.enums import BenchmarkName, ProblemType

from mamut_routing_publish.site_payloads import (
    PROJECT_PAGE_SOURCES,
    _family_route_path,
    _project_page_source_path,
    load_family_context_sections,
)

GITHUB_ORG_URL = "https://github.com/ANR-MAMUT"
MAIN_REPO_NAME = "MAMUT-routing"
MAIN_REPO_URL = f"{GITHUB_ORG_URL}/{MAIN_REPO_NAME}"
DEFAULT_BRANCH = "main"

# Where each website project page lands in the documentation tree.
PROJECT_PAGE_DOC_PATHS = {
    "faq": "user-guide/faq.md",
    "citing": "user-guide/citing.md",
    "glossary": "benchmarks/glossary.md",
    "authors": "about/authors.md",
    "funding": "about/funding.md",
    "related-projects": "about/related-projects.md",
    "legal-mentions": "about/legal-mentions.md",
}

# Package README pages: (doc path, README path relative to the repo root,
# fallback README path, GitHub repository name).
PACKAGE_README_PAGES = (
    (
        "developer-guide/packages/mamut-routing-lib.md",
        "MAMUT-routing-tools/MAMUT-routing-lib/README.md",
        "MAMUT-routing-lib/README.md",
        "MAMUT-routing-lib",
    ),
    (
        "developer-guide/packages/mamut-routing-tools.md",
        "MAMUT-routing-tools/README.md",
        None,
        "MAMUT-routing-tools",
    ),
)

# API reference: package -> (doc directory, source root relative to the repo,
# top-level modules / subpackages to document, show undocumented members).
API_REFERENCE_PACKAGES = (
    (
        "mamut_routing_lib",
        "lib",
        "MAMUT-routing-tools/MAMUT-routing-lib/src/mamut_routing_lib",
        ("models", "enums", "checker", "bks", "artifacts", "remote", "cvrplib", "sidecars", "distances", "geo", "json_utils", "td", "solvers"),
        True,
    ),
    (
        "mamut_routing_tools",
        "tools",
        "MAMUT-routing-tools/src/mamut_routing_tools",
        ("family", "generation", "roadgraph", "osm", "geometry", "conversion", "td", "campaign", "workspace", "geo"),
        False,
    ),
    (
        "mamut_routing_publish",
        "publish",
        "src/mamut_routing_publish",
        ("publish_roots", "precompress", "server", "progress", "docs_build", "docs_pages"),
        False,
    ),
)

_REPORT_FILENAME_RE = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2})-(?P<slug>.+)\.md$")
_MARKDOWN_LINK_RE = re.compile(r"(?P<bang>!?)\[(?P<text>[^\]]*)\]\((?P<target>[^)\s]+)(?P<title>\s+\"[^\"]*\")?\)")
_FENCE_RE = re.compile(r"^\s*(```|~~~)")


@dataclass(frozen=True)
class GeneratedDocPage:
    """One virtual markdown file, ``path`` relative to the MkDocs ``docs_dir``."""

    path: str
    markdown: str


# ---------------------------------------------------------------------------
# markdown helpers
# ---------------------------------------------------------------------------


def shift_headings(markdown: str, delta: int) -> str:
    """Shift every ATX heading level by ``delta`` (clamped to 1..6), skipping fenced code."""
    if delta == 0:
        return markdown
    lines: list[str] = []
    in_fence = False
    for line in markdown.splitlines():
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            lines.append(line)
            continue
        match = re.match(r"^(#{1,6})(\s+.*)$", line) if not in_fence else None
        if match is None:
            lines.append(line)
            continue
        level = min(6, max(1, len(match.group(1)) + delta))
        lines.append("#" * level + match.group(2))
    return "\n".join(lines) + ("\n" if markdown.endswith("\n") else "")


def _is_relative_target(target: str) -> bool:
    lowered = target.lower()
    return not (
        lowered.startswith(("http://", "https://", "mailto:", "#", "/", "data:", "ftp://", "//"))
        or ":" in target.split("/")[0]
    )


def rewrite_relative_links(markdown: str, *, blob_base: str, raw_base: str) -> str:
    """Point relative links at GitHub so an embedded README keeps working.

    ``blob_base`` receives plain links (files and directories), ``raw_base``
    receives images. Both are URL prefixes without a trailing slash.
    Absolute URLs, anchors, mailto and root-relative links are untouched.
    """

    def replace(match: re.Match[str]) -> str:
        target = match.group("target")
        if not _is_relative_target(target):
            return match.group(0)
        base = raw_base if match.group("bang") else blob_base
        cleaned = target[2:] if target.startswith("./") else target
        return f"{match.group('bang')}[{match.group('text')}]({base}/{cleaned}{match.group('title') or ''})"

    lines: list[str] = []
    in_fence = False
    for line in markdown.splitlines():
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            lines.append(line)
            continue
        lines.append(line if in_fence else _MARKDOWN_LINK_RE.sub(replace, line))
    return "\n".join(lines) + ("\n" if markdown.endswith("\n") else "")


def first_heading(markdown: str, fallback: str) -> str:
    for line in markdown.splitlines():
        match = re.match(r"^#\s+(.+?)\s*$", line.strip())
        if match is not None:
            return match.group(1)
    return fallback


# ---------------------------------------------------------------------------
# repository topology helpers
# ---------------------------------------------------------------------------


def parse_gitmodules(repo_root: Path) -> dict[str, str]:
    """Map submodule path -> GitHub HTTPS URL from ``<repo>/.gitmodules``."""
    gitmodules = repo_root / ".gitmodules"
    if not gitmodules.is_file():
        return {}
    entries: dict[str, str] = {}
    path: str | None = None
    url: str | None = None

    def flush() -> None:
        if path is not None and url is not None:
            entries[path] = github_https_url(url)

    for raw_line in gitmodules.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("[submodule"):
            flush()
            path = url = None
        elif line.startswith("path"):
            path = line.split("=", 1)[1].strip()
        elif line.startswith("url"):
            url = line.split("=", 1)[1].strip()
    flush()
    return entries


def github_https_url(url: str) -> str:
    """Normalise ``git@github.com:ORG/X.git`` / ``../X.git`` / https forms to a browsable URL."""
    value = url.strip()
    if value.endswith(".git"):
        value = value[: -len(".git")]
    if value.startswith("git@github.com:"):
        return "https://github.com/" + value[len("git@github.com:") :]
    if value.startswith("../"):
        return f"{GITHUB_ORG_URL}/{value[3:]}"
    if value.startswith("ssh://git@github.com/"):
        return "https://github.com/" + value[len("ssh://git@github.com/") :]
    return value


def github_bases_for_path(repo_root: Path, relative_dir: str) -> tuple[str, str, str]:
    """(browse URL, blob base, raw base) for a directory of the superproject.

    A submodule directory maps to its own repository; anything else maps to
    the same path inside the main repository.
    """
    submodules = parse_gitmodules(repo_root)
    relative_dir = relative_dir.strip("/")
    for submodule_path, repo_url in submodules.items():
        if relative_dir == submodule_path or relative_dir.startswith(submodule_path + "/"):
            inner = relative_dir[len(submodule_path) :].strip("/")
            suffix = f"/{inner}" if inner else ""
            raw_repo = repo_url.replace("https://github.com/", "https://raw.githubusercontent.com/")
            return (
                f"{repo_url}/tree/{DEFAULT_BRANCH}{suffix}" if inner else repo_url,
                f"{repo_url}/blob/{DEFAULT_BRANCH}{suffix}",
                f"{raw_repo}/{DEFAULT_BRANCH}{suffix}",
            )
    suffix = f"/{relative_dir}" if relative_dir else ""
    return (
        f"{MAIN_REPO_URL}/tree/{DEFAULT_BRANCH}{suffix}",
        f"{MAIN_REPO_URL}/blob/{DEFAULT_BRANCH}{suffix}",
        f"https://raw.githubusercontent.com/ANR-MAMUT/{MAIN_REPO_NAME}/{DEFAULT_BRANCH}{suffix}",
    )


def is_collection_family(repo_root: Path, benchmark_name: BenchmarkName) -> bool:
    """Family-first collections live at ``benchmarks/<Family>/`` (Poryos2026, Mamut2026)."""
    collection_dir = repo_root / "benchmarks" / benchmark_name.value
    if collection_dir.is_dir():
        return True
    return f"benchmarks/{benchmark_name.value}" in parse_gitmodules(repo_root)


def family_source_dir(repo_root: Path, problem_type: ProblemType, benchmark_name: BenchmarkName) -> str:
    """Repo-relative directory holding the family's README/LICENSE (mirrors the publisher's license lookup)."""
    classic = f"benchmarks/{problem_type.value}/{benchmark_name.value}"
    if (repo_root / classic).is_dir() or not is_collection_family(repo_root, benchmark_name):
        return classic
    return f"benchmarks/{benchmark_name.value}"


def embedded_readme(repo_root: Path, relative_dir: str, *, heading_delta: int = 1) -> str | None:
    """The README of ``relative_dir`` rewritten for embedding, or None when absent."""
    readme = repo_root / relative_dir / "README.md"
    if not readme.is_file():
        return None
    _browse, blob_base, raw_base = github_bases_for_path(repo_root, relative_dir)
    text = readme.read_text(encoding="utf-8")
    return shift_headings(rewrite_relative_links(text, blob_base=blob_base, raw_base=raw_base), heading_delta)


def _source_note(browse_url: str, what: str) -> str:
    return f'!!! note "Source"\n    {what} is maintained in [{browse_url}]({browse_url}).\n'


def _absent_stub(browse_url: str, what: str) -> str:
    return (
        '!!! warning "Not checked out in this build"\n'
        f"    {what} is a satellite repository that was not initialised when this documentation "
        f"was built, so its README is not embedded here. Read it on GitHub: [{browse_url}]({browse_url}).\n"
    )


# ---------------------------------------------------------------------------
# page sets
# ---------------------------------------------------------------------------


def project_pages(repo_root: Path) -> list[GeneratedDocPage]:
    pages: list[GeneratedDocPage] = []
    for source in PROJECT_PAGE_SOURCES:
        doc_path = PROJECT_PAGE_DOC_PATHS.get(source.slug, f"about/{source.slug}.md")
        source_path = _project_page_source_path(repo_root, source)
        if source_path.is_file():
            markdown = source_path.read_text(encoding="utf-8")
        else:
            title = " ".join(part.upper() if part == "faq" else part.capitalize() for part in source.slug.split("-"))
            markdown = f"# {title}\n\nThis page has no content yet.\n"
        website_url = source.route_path
        footer = (
            "\n\n---\n\n"
            f"*This page is shared with the website: [{website_url}]({website_url}).*\n"
        )
        pages.append(GeneratedDocPage(path=doc_path, markdown=markdown.rstrip("\n") + footer))
    return pages


def package_readme_pages(repo_root: Path) -> list[GeneratedDocPage]:
    pages: list[GeneratedDocPage] = []
    for doc_path, readme_rel, fallback_rel, repo_name in PACKAGE_README_PAGES:
        chosen = None
        for candidate in (readme_rel, fallback_rel):
            if candidate and (repo_root / candidate).is_file():
                chosen = candidate
                break
        repo_url = f"{GITHUB_ORG_URL}/{repo_name}"
        if chosen is None:
            body = (
                f"# {repo_name}\n\n"
                + _absent_stub(repo_url, f"The `{repo_name}` package")
            )
        else:
            readme_dir = str(Path(chosen).parent)
            embedded = embedded_readme(repo_root, readme_dir, heading_delta=0) or ""
            body = _source_note(repo_url, f"This README") + "\n" + embedded
        pages.append(GeneratedDocPage(path=doc_path, markdown=body))
    return pages


def family_pages(repo_root: Path) -> list[GeneratedDocPage]:
    sections = load_family_context_sections(repo_root)
    pages: list[GeneratedDocPage] = []
    by_problem: dict[ProblemType, list[tuple[BenchmarkName, str]]] = {}
    collections: dict[BenchmarkName, str] = {}

    for (problem_type, benchmark_name), section in sections.items():
        family_slug = benchmark_name.value.lower()
        problem_slug = problem_type.value.lower()
        doc_path = f"benchmarks/families/{problem_slug}/{family_slug}.md"
        source_dir = family_source_dir(repo_root, problem_type, benchmark_name)
        browse_url, _blob, _raw = github_bases_for_path(repo_root, source_dir)
        website_route = _family_route_path(problem_type, benchmark_name)
        collection = is_collection_family(repo_root, benchmark_name) and source_dir == f"benchmarks/{benchmark_name.value}"

        parts = [
            f"# {section.title}\n",
            shift_headings(section.markdown, -2).rstrip("\n") + "\n",
            "",
            '!!! info "Data"',
            f"    Instances and best-known solutions: [{website_route}]({website_route}) on the website. "
            f"Repository: [{browse_url}]({browse_url}).",
            "",
        ]
        if collection:
            collection_page = f"../collections/{family_slug}.md"
            parts.append(
                f"This family is one problem-type layer of the **{benchmark_name.value} collection**; "
                f"the collection README (layout, conventions, sidecars) is on the "
                f"[collection page]({collection_page}).\n"
            )
            if benchmark_name not in collections:
                readme = embedded_readme(repo_root, source_dir)
                header = f"# {benchmark_name.value} collection\n\n"
                if readme is None:
                    collections[benchmark_name] = header + _absent_stub(browse_url, f"The {benchmark_name.value} collection")
                else:
                    collections[benchmark_name] = header + _source_note(browse_url, "This README") + "\n" + readme
        else:
            readme = embedded_readme(repo_root, source_dir)
            if readme is None:
                parts.append(_absent_stub(browse_url, f"`{source_dir}`"))
            else:
                parts.append("## Repository README\n")
                parts.append(shift_headings(readme, 1))
        pages.append(GeneratedDocPage(path=doc_path, markdown="\n".join(parts).rstrip("\n") + "\n"))
        by_problem.setdefault(problem_type, []).append((benchmark_name, f"{problem_slug}/{family_slug}.md"))

    for benchmark_name, markdown in collections.items():
        pages.append(GeneratedDocPage(path=f"benchmarks/families/collections/{benchmark_name.value.lower()}.md", markdown=markdown))

    # Overview and literate-nav summary (index first for Material navigation.indexes).
    overview = ["# Benchmark families\n", "One page per family and problem type, generated from the website's family descriptions and each family's repository README.\n"]
    summary = ["* [Overview](index.md)"]
    for problem_type in ProblemType:
        entries = by_problem.get(problem_type)
        if not entries:
            continue
        overview.append(f"\n## {problem_type.value}\n")
        summary.append(f"* {problem_type.value}")
        for benchmark_name, rel in entries:
            overview.append(f"- [{benchmark_name.value}]({rel})")
            summary.append(f"    * [{benchmark_name.value}]({rel})")
    if collections:
        overview.append("\n## Collections\n")
        summary.append("* Collections")
        for benchmark_name in collections:
            rel = f"collections/{benchmark_name.value.lower()}.md"
            overview.append(f"- [{benchmark_name.value}]({rel})")
            summary.append(f"    * [{benchmark_name.value}]({rel})")
    pages.append(GeneratedDocPage(path="benchmarks/families/index.md", markdown="\n".join(overview) + "\n"))
    pages.append(GeneratedDocPage(path="benchmarks/families/SUMMARY.md", markdown="\n".join(summary) + "\n"))
    return pages


def reports_pages(reports_dir: Path) -> list[GeneratedDocPage]:
    """Index + nav of ``docs/reports/YYYY-MM-DD-<slug>.md``, newest first."""
    entries: list[tuple[str, str, str]] = []
    if reports_dir.is_dir():
        for path in sorted(reports_dir.glob("*.md"), reverse=True):
            match = _REPORT_FILENAME_RE.match(path.name)
            if match is None:
                continue
            title = first_heading(path.read_text(encoding="utf-8"), match.group("slug").replace("-", " "))
            entries.append((match.group("date"), title, path.name))
    index = [
        "# Engineering reports\n",
        "Dated design records and post-mortems, in the spirit of architecture decision records: "
        "each report states a problem, the decision taken and the evidence, and is never edited "
        "retroactively (a later report supersedes it). Add one as `docs/reports/YYYY-MM-DD-<slug>.md` "
        "with a top-level heading; this index is generated.\n",
    ]
    if entries:
        index.append("| Date | Report |\n|---|---|")
        index.extend(f"| {date} | [{title}]({name}) |" for date, title, name in entries)
    else:
        index.append("No report yet.")
    summary = ["* [Index](index.md)"]
    summary.extend(f"* [{date} — {title}]({name})" for date, title, name in entries)
    return [
        GeneratedDocPage(path="reports/index.md", markdown="\n".join(index) + "\n"),
        GeneratedDocPage(path="reports/SUMMARY.md", markdown="\n".join(summary) + "\n"),
    ]


def _module_names(source_root: Path, top_level: tuple[str, ...]) -> list[str]:
    """Dotted module names under ``source_root`` for the selected top-level entries, in source order."""
    names: list[str] = []
    for entry in top_level:
        module_file = source_root / f"{entry}.py"
        package_dir = source_root / entry
        if module_file.is_file():
            names.append(entry)
        elif package_dir.is_dir():
            names.append(entry)
            for path in sorted(package_dir.rglob("*.py")):
                if path.name.startswith("_") or any(part.startswith("_") or part == "static" for part in path.relative_to(package_dir).parts[:-1]):
                    continue
                dotted = ".".join((entry, *path.relative_to(package_dir).with_suffix("").parts))
                names.append(dotted)
    return names


def reference_pages(repo_root: Path) -> list[GeneratedDocPage]:
    pages: list[GeneratedDocPage] = []
    index = [
        "# Python API reference\n",
        "Generated from the source with [mkdocstrings](https://mkdocstrings.github.io/). "
        "Module docstrings carry the normative contracts (formats, invariants, determinism rules); "
        "the pages below are grouped by package.\n",
    ]
    summary = ["* [Overview](index.md)"]
    for package, doc_dir, source_rel, top_level, show_undocumented in API_REFERENCE_PACKAGES:
        source_root = repo_root / source_rel
        modules = _module_names(source_root, top_level) if source_root.is_dir() else []
        index.append(f"\n## `{package}`\n")
        summary.append(f"* {package}")
        if not modules:
            index.append(f"Source tree not available in this build (`{source_rel}`).")
            continue
        for module in modules:
            rel = f"{doc_dir}/{module.replace('.', '/')}.md"
            full_name = f"{package}.{module}"
            body = (
                f"# `{full_name}`\n\n"
                f"::: {full_name}\n"
                "    options:\n"
                f"      show_if_no_docstring: {'true' if show_undocumented else 'false'}\n"
            )
            pages.append(GeneratedDocPage(path=f"reference/api/{rel}", markdown=body))
            index.append(f"- [`{full_name}`]({rel})")
            depth = module.count(".")
            summary.append(f"{'    ' * (depth + 1)}* [{module.rsplit('.', 1)[-1]}]({rel})")
    pages.append(GeneratedDocPage(path="reference/api/index.md", markdown="\n".join(index) + "\n"))
    pages.append(GeneratedDocPage(path="reference/api/SUMMARY.md", markdown="\n".join(summary) + "\n"))
    return pages


def generate_docs_pages(repo_root: Path) -> list[GeneratedDocPage]:
    """Every generated page of the documentation site for ``repo_root``."""
    pages: list[GeneratedDocPage] = []
    pages += project_pages(repo_root)
    pages += package_readme_pages(repo_root)
    pages += family_pages(repo_root)
    pages += reports_pages(repo_root / "docs" / "reports")
    pages += reference_pages(repo_root)
    return pages
