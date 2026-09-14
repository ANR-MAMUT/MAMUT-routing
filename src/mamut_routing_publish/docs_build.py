"""Build the MkDocs documentation site into the published static tree.

The documentation (``docs/`` + ``mkdocs.yml`` at the repository root) is a
phase of ``site build``: it renders into ``<site-output>/docs/`` so the
website serves it under ``/docs/`` from the same tree as everything else,
staging builds (``--site-output-dir``) never touch the live ``dist/docs``,
and the precompress phase covers the rendered HTML like any other asset.

MkDocs is an optional dependency group (``uv sync --group docs``; installed
by default through ``[tool.uv] default-groups``). The publisher imports it
lazily so the rest of the CLI works without it and ``site build`` can fail
fast, before the multi-hour cache phases, when the toolchain is missing.
"""

from __future__ import annotations

import contextlib
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

DOCS_OUTPUT_DIR_NAME = "docs"
DEFAULT_MKDOCS_CONFIG_NAME = "mkdocs.yml"
_MKDOCS_ADVISORY_ENV = "DISABLE_MKDOCS_2_WARNING"

_REQUIRED_MODULES = (
    "mkdocs",
    "material",
    "mkdocstrings",
    "mkdocs_click",
    "mkdocs_gen_files",
    "mkdocs_literate_nav",
)


class DocsToolingUnavailable(RuntimeError):
    """The MkDocs toolchain is not importable in this environment."""


class DocsBuildError(RuntimeError):
    """The MkDocs build failed (configuration error or strict-mode warnings)."""


@dataclass
class DocsBuildSummary:
    site_dir: Path
    html_files_written: int
    wall_time_seconds: float
    strict: bool

    def as_dict(self) -> dict:
        return {
            "site_dir": str(self.site_dir),
            "html_files_written": self.html_files_written,
            "wall_time_seconds": round(self.wall_time_seconds, 3),
            "strict": self.strict,
        }


def ensure_docs_tooling_available() -> None:
    """Raise :class:`DocsToolingUnavailable` unless every docs plugin imports."""
    import importlib

    missing: list[str] = []
    for module_name in _REQUIRED_MODULES:
        try:
            importlib.import_module(module_name)
        except ImportError:
            missing.append(module_name)
    if missing:
        raise DocsToolingUnavailable(
            "The MkDocs documentation toolchain is not installed "
            f"(missing: {', '.join(missing)}). Run `uv sync --group docs`, "
            "or pass --skip-docs to `site build`."
        )


def docs_output_dir(site_output: Path) -> Path:
    return site_output / DOCS_OUTPUT_DIR_NAME


def has_docs_config(repo_root: Path) -> bool:
    """True when the checkout carries a documentation site to build."""
    return (repo_root / DEFAULT_MKDOCS_CONFIG_NAME).is_file()


@contextlib.contextmanager
def _working_directory(path: Path) -> Iterator[None]:
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def build_docs_site(
    repo_root: Path,
    site_dir: Path,
    *,
    strict: bool = True,
    quiet: bool = False,
    config_file: Path | None = None,
) -> DocsBuildSummary:
    """Render ``mkdocs.yml`` into ``site_dir`` (cleaned first by MkDocs itself).

    Runs with the repository root as the working directory: the gen-files
    script, the mkdocstrings source paths and the snippet base path in
    ``mkdocs.yml`` are all relative to it. Strict mode turns every MkDocs
    warning (missing nav target, broken link, unresolved reference) into a
    :class:`DocsBuildError`, which is what CI and the publisher want.
    """
    ensure_docs_tooling_available()
    from mkdocs.commands.build import build
    from mkdocs.config import load_config
    from mkdocs.exceptions import MkDocsException

    config_path = config_file or (repo_root / DEFAULT_MKDOCS_CONFIG_NAME)
    if not config_path.is_file():
        raise DocsBuildError(f"MkDocs configuration not found: {config_path}")
    site_dir = site_dir if site_dir.is_absolute() else repo_root / site_dir
    site_dir.parent.mkdir(parents=True, exist_ok=True)

    mkdocs_logger = logging.getLogger("mkdocs")
    previous_level = mkdocs_logger.level
    mkdocs_logger.setLevel(logging.ERROR if quiet else logging.WARNING)
    # A plugin in the toolchain prints a long advisory about the MkDocs 2.0
    # transition on every build; it is noise for a pinned, tested toolchain.
    previous_advisory = os.environ.get(_MKDOCS_ADVISORY_ENV)
    os.environ[_MKDOCS_ADVISORY_ENV] = "true"
    started_at = time.perf_counter()
    try:
        with _working_directory(repo_root):
            config = load_config(config_file=str(config_path), site_dir=str(site_dir), strict=strict)
            build(config)
    except MkDocsException as error:
        raise DocsBuildError(f"mkdocs build failed: {error}") from error
    finally:
        mkdocs_logger.setLevel(previous_level)
        if previous_advisory is None:
            os.environ.pop(_MKDOCS_ADVISORY_ENV, None)
        else:
            os.environ[_MKDOCS_ADVISORY_ENV] = previous_advisory

    html_files_written = sum(1 for path in site_dir.rglob("*.html") if path.is_file())
    return DocsBuildSummary(
        site_dir=site_dir,
        html_files_written=html_files_written,
        wall_time_seconds=time.perf_counter() - started_at,
        strict=strict,
    )
