"""Typer CLI for ``mamut-routing-publish``.

Modeled on ``mamut_routing_lib.cli`` (Typer + sub-typers + ``--version`` callback).

Two top-level command groups:

- ``site``    — payload + static-webapp generation
- ``release`` — release ``.zip`` archives + manifest generation

Repository root resolution order, for arguments that default to "the
MAMUT-routing repo root":

1. The explicit CLI flag (``--source-repo-dir`` / ``--output-repo-dir``)
2. The ``MAMUT_ROUTING_ROOT`` environment variable (shared with
   ``mamut-routing-lib``)
3. The current working directory
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tomllib
from importlib import metadata
from pathlib import Path
from typing import Annotated, Optional

import typer

from mamut_routing_lib.artifacts import DEFAULT_MAMUT_ROUTING_ROOT_ENV

from mamut_routing_publish.release_artifacts import generate_release_artifacts
from mamut_routing_publish.site_payloads import (
    DEFAULT_SITE_OUTPUT_DIR,
    DEFAULT_SITE_PAYLOAD_ROOT_DIR,
    SITE_PAYLOAD_SCHEMA_VERSION,
    generate_site_payloads,
)
from mamut_routing_publish.site_webapp import generate_site_webapp


app = typer.Typer(
    name="mamut-routing-publish",
    help=(
        "Snapshot, site, and release-archive generation toolkit for the "
        "MAMUT-routing benchmark repository."
    ),
    no_args_is_help=True,
    add_completion=False,
)

site_app = typer.Typer(
    help="Generate site payload JSON files and the static HTML shell consumed by the Julia webapp.",
    no_args_is_help=True,
)
release_app = typer.Typer(
    help="Generate release .zip archives and the release manifest for MAMUT-routing benchmarks.",
    no_args_is_help=True,
)
app.add_typer(site_app, name="site")
app.add_typer(release_app, name="release")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_package_version() -> str:
    package_name = "mamut-routing-publish"
    try:
        return metadata.version(package_name)
    except metadata.PackageNotFoundError:
        pass
    try:
        pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
        pyproject_data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
        return str(pyproject_data["project"]["version"])
    except (OSError, KeyError, tomllib.TOMLDecodeError):
        return "unknown"


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"mamut-routing-publish {_get_package_version()}")
        raise typer.Exit()


def _resolve_default_repo_dir() -> Path:
    env_value = os.getenv(DEFAULT_MAMUT_ROUTING_ROOT_ENV)
    if env_value:
        return Path(env_value).expanduser().resolve()
    return Path.cwd().resolve()


def _resolve_repo_dir(explicit: Optional[Path]) -> Path:
    if explicit is not None:
        return explicit.expanduser().resolve()
    return _resolve_default_repo_dir()


def _resolve_git_value(repo_dir: Path, *args: str) -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_dir), *args],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    value = result.stdout.strip()
    return value or None


def _emit_summary(summary_obj) -> None:
    typer.echo(json.dumps(summary_obj.model_dump(mode="json"), indent=2))


# ---------------------------------------------------------------------------
# Top-level callback (--version)
# ---------------------------------------------------------------------------


@app.callback()
def main_callback(
    version: Annotated[
        Optional[bool],
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Print the installed mamut-routing-publish version and exit.",
        ),
    ] = None,
) -> None:
    """Top-level ``mamut-routing-publish`` callback."""


# ---------------------------------------------------------------------------
# site sub-commands
# ---------------------------------------------------------------------------


_OUTPUT_REPO_DIR_HELP = (
    f"Path to the MAMUT-routing repo root. Defaults to "
    f"${DEFAULT_MAMUT_ROUTING_ROOT_ENV} or the current working directory."
)


@site_app.command("payloads")
def site_payloads_cmd(
    output_repo_dir: Annotated[
        Optional[Path],
        typer.Option("--output-repo-dir", help=_OUTPUT_REPO_DIR_HELP),
    ] = None,
    source_commit: Annotated[
        Optional[str],
        typer.Option(
            "--source-commit",
            help="Git commit hash to embed in the snapshot. Defaults to MAMUT-routing HEAD.",
        ),
    ] = None,
    source_branch: Annotated[
        Optional[str],
        typer.Option("--source-branch", help="Optional branch name to embed alongside the source commit."),
    ] = None,
    published_at: Annotated[
        Optional[str],
        typer.Option("--published-at", help="Optional publication timestamp in ISO-8601 format."),
    ] = None,
    snapshot_id: Annotated[
        Optional[str],
        typer.Option("--snapshot-id", help="Optional explicit snapshot identifier."),
    ] = None,
    history_summary: Annotated[
        str,
        typer.Option("--history-summary", help="Human-readable summary recorded in the history ledger."),
    ] = "Generated site payload snapshot.",
    schema_version: Annotated[
        str,
        typer.Option("--schema-version", help="Schema version string for the generated site payloads."),
    ] = SITE_PAYLOAD_SCHEMA_VERSION,
    payload_root_dir: Annotated[
        Path,
        typer.Option(
            "--payload-root-dir",
            help="Directory (relative to the site output root) where route payload JSON files are written.",
        ),
    ] = DEFAULT_SITE_PAYLOAD_ROOT_DIR,
    site_output_dir: Annotated[
        Path,
        typer.Option(
            "--site-output-dir",
            help="Directory where generated website files are written. Relative paths resolve under --output-repo-dir.",
        ),
    ] = DEFAULT_SITE_OUTPUT_DIR,
) -> None:
    """Generate site payload JSON files only."""
    repo_dir = _resolve_repo_dir(output_repo_dir)
    resolved_commit = source_commit or _resolve_git_value(repo_dir, "rev-parse", "--short=12", "HEAD")
    if resolved_commit is None:
        typer.echo("Unable to determine a source commit. Pass --source-commit explicitly.", err=True)
        raise typer.Exit(code=1)
    resolved_branch = source_branch or _resolve_git_value(repo_dir, "rev-parse", "--abbrev-ref", "HEAD")

    summary = generate_site_payloads(
        output_repo_dir=repo_dir,
        source_commit=resolved_commit,
        published_at=published_at,
        snapshot_id=snapshot_id,
        history_summary=history_summary,
        source_branch=resolved_branch,
        schema_version=schema_version,
        payload_root_dir=payload_root_dir,
        site_output_dir=site_output_dir,
    )
    _emit_summary(summary)


@site_app.command("webapp")
def site_webapp_cmd(
    output_repo_dir: Annotated[
        Optional[Path],
        typer.Option("--output-repo-dir", help=_OUTPUT_REPO_DIR_HELP),
    ] = None,
    payload_mode: Annotated[
        str,
        typer.Option(
            "--payload-mode",
            help="How generated HTML shells should fetch route payloads ('static' or 'api').",
        ),
    ] = "static",
    payload_api_prefix: Annotated[
        str,
        typer.Option(
            "--payload-api-prefix",
            help="API prefix embedded into generated HTML shells when --payload-mode is 'api'.",
        ),
    ] = "/api/site-payload",
    payload_root_dir: Annotated[
        Path,
        typer.Option("--payload-root-dir", help="Directory under the site output root for route payload JSON files."),
    ] = DEFAULT_SITE_PAYLOAD_ROOT_DIR,
    site_output_dir: Annotated[
        Path,
        typer.Option(
            "--site-output-dir",
            help="Directory where generated website files are written. Relative paths resolve under --output-repo-dir.",
        ),
    ] = DEFAULT_SITE_OUTPUT_DIR,
) -> None:
    """Generate the static HTML shell only (assumes payloads already exist)."""
    if payload_mode not in {"static", "api"}:
        typer.echo("--payload-mode must be one of: static, api", err=True)
        raise typer.Exit(code=1)
    repo_dir = _resolve_repo_dir(output_repo_dir)

    summary = generate_site_webapp(
        repo_dir,
        payload_mode=payload_mode,
        payload_api_prefix=payload_api_prefix,
        payload_root_dir=payload_root_dir,
        site_output_dir=site_output_dir,
    )
    _emit_summary(summary)


@site_app.command("build")
def site_build_cmd(
    output_repo_dir: Annotated[
        Optional[Path],
        typer.Option("--output-repo-dir", help=_OUTPUT_REPO_DIR_HELP),
    ] = None,
    source_commit: Annotated[
        Optional[str],
        typer.Option(
            "--source-commit",
            help="Git commit hash to embed in the snapshot. Defaults to MAMUT-routing HEAD.",
        ),
    ] = None,
    source_branch: Annotated[
        Optional[str],
        typer.Option("--source-branch", help="Optional branch name to embed alongside the source commit."),
    ] = None,
    published_at: Annotated[
        Optional[str],
        typer.Option("--published-at", help="Optional publication timestamp in ISO-8601 format."),
    ] = None,
    snapshot_id: Annotated[
        Optional[str],
        typer.Option("--snapshot-id", help="Optional explicit snapshot identifier."),
    ] = None,
    history_summary: Annotated[
        str,
        typer.Option("--history-summary", help="Human-readable summary recorded in the history ledger."),
    ] = "Built static site snapshot.",
    schema_version: Annotated[
        str,
        typer.Option("--schema-version", help="Schema version string for the generated site payloads."),
    ] = SITE_PAYLOAD_SCHEMA_VERSION,
    payload_mode: Annotated[
        str,
        typer.Option(
            "--payload-mode",
            help="How generated HTML shells should fetch route payloads ('static' or 'api').",
        ),
    ] = "static",
    payload_api_prefix: Annotated[
        str,
        typer.Option(
            "--payload-api-prefix",
            help="API prefix embedded into generated HTML shells when --payload-mode is 'api'.",
        ),
    ] = "/api/site-payload",
    payload_root_dir: Annotated[
        Path,
        typer.Option("--payload-root-dir", help="Directory under the site output root for route payload JSON files."),
    ] = DEFAULT_SITE_PAYLOAD_ROOT_DIR,
    site_output_dir: Annotated[
        Path,
        typer.Option(
            "--site-output-dir",
            help="Directory where generated website files are written. Relative paths resolve under --output-repo-dir.",
        ),
    ] = DEFAULT_SITE_OUTPUT_DIR,
) -> None:
    """Generate site payloads AND the static HTML shell in one step."""
    if payload_mode not in {"static", "api"}:
        typer.echo("--payload-mode must be one of: static, api", err=True)
        raise typer.Exit(code=1)
    repo_dir = _resolve_repo_dir(output_repo_dir)
    resolved_commit = source_commit or _resolve_git_value(repo_dir, "rev-parse", "--short=12", "HEAD")
    if resolved_commit is None:
        typer.echo("Unable to determine a source commit. Pass --source-commit explicitly.", err=True)
        raise typer.Exit(code=1)
    resolved_branch = source_branch or _resolve_git_value(repo_dir, "rev-parse", "--abbrev-ref", "HEAD")

    payload_summary = generate_site_payloads(
        output_repo_dir=repo_dir,
        source_commit=resolved_commit,
        published_at=published_at,
        snapshot_id=snapshot_id,
        history_summary=history_summary,
        source_branch=resolved_branch,
        schema_version=schema_version,
        payload_root_dir=payload_root_dir,
        site_output_dir=site_output_dir,
    )
    webapp_summary = generate_site_webapp(
        repo_dir,
        payload_mode=payload_mode,
        payload_api_prefix=payload_api_prefix,
        payload_root_dir=payload_root_dir,
        site_output_dir=site_output_dir,
    )
    typer.echo(
        json.dumps(
            {
                "payload_summary": payload_summary.model_dump(mode="json"),
                "webapp_summary": webapp_summary.model_dump(mode="json"),
            },
            indent=2,
        )
    )


# ---------------------------------------------------------------------------
# release sub-commands
# ---------------------------------------------------------------------------


@release_app.command("build")
def release_build_cmd(
    source_repo_dir: Annotated[
        Optional[Path],
        typer.Option(
            "--source-repo-dir",
            help=(
                "Path to the source MAMUT-routing repo root containing the benchmark tree. "
                f"Defaults to ${DEFAULT_MAMUT_ROUTING_ROOT_ENV} or the current working directory."
            ),
        ),
    ] = None,
    output_dir: Annotated[
        Optional[Path],
        typer.Option(
            "--output-dir",
            help=(
                "Directory where zip archives and the release manifest are written. "
                "Defaults to <source-repo-dir>/dist-release."
            ),
        ),
    ] = None,
    source_commit: Annotated[
        Optional[str],
        typer.Option(
            "--source-commit",
            help="Git commit hash to embed in the manifest. Defaults to MAMUT-routing HEAD.",
        ),
    ] = None,
    source_branch: Annotated[
        Optional[str],
        typer.Option("--source-branch", help="Optional branch name to embed alongside the source commit."),
    ] = None,
    published_at: Annotated[
        Optional[str],
        typer.Option("--published-at", help="Optional publication timestamp in ISO-8601 format."),
    ] = None,
    snapshot_id: Annotated[
        Optional[str],
        typer.Option("--snapshot-id", help="Optional explicit snapshot identifier."),
    ] = None,
    release_tag: Annotated[
        Optional[str],
        typer.Option("--release-tag", help="Optional release tag stored in the manifest."),
    ] = None,
    download_base_url: Annotated[
        Optional[str],
        typer.Option(
            "--download-base-url",
            help="Optional base URL used to populate manifest download URLs.",
        ),
    ] = None,
) -> None:
    """Generate release .zip archives + manifest.

    GitHub Releases currently allows up to 1000 assets per release and requires each
    asset to stay under 2 GiB. This generator warns at 1.5 GiB and fails at 2 GiB or
    above. See https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases
    """
    repo_dir = _resolve_repo_dir(source_repo_dir)
    resolved_output_dir = (
        output_dir.expanduser().resolve() if output_dir is not None else (repo_dir / "dist-release")
    )
    resolved_commit = source_commit or _resolve_git_value(repo_dir, "rev-parse", "--short=12", "HEAD")
    if resolved_commit is None:
        typer.echo("Unable to determine a source commit. Pass --source-commit explicitly.", err=True)
        raise typer.Exit(code=1)
    resolved_branch = source_branch or _resolve_git_value(repo_dir, "rev-parse", "--abbrev-ref", "HEAD")

    summary = generate_release_artifacts(
        source_repo_dir=repo_dir,
        output_dir=resolved_output_dir,
        source_commit=resolved_commit,
        published_at=published_at,
        snapshot_id=snapshot_id,
        source_branch=resolved_branch,
        release_tag=release_tag,
        download_base_url=download_base_url,
    )
    _emit_summary(summary)


def _entrypoint() -> None:  # pragma: no cover - thin wrapper
    app()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(app())
