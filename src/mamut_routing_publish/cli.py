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
import sys
import subprocess
import time
import tomllib
from importlib import metadata
from pathlib import Path
from typing import Annotated, Optional

try:
    import resource
except ImportError:  # pragma: no cover - unavailable on non-Unix platforms
    resource = None

import typer

from mamut_routing_lib.artifacts import DEFAULT_MAMUT_ROUTING_ROOT_ENV

from mamut_routing_publish.progress import SUPPORTED_PROGRESS_FORMATS, make_progress_reporter
from mamut_routing_publish.release_artifacts import (
    DEFAULT_RELEASE_ARCHIVE_COMPRESS_LEVEL,
    generate_release_artifacts,
)
from mamut_routing_publish.site_payloads import (
    DEFAULT_SITE_OUTPUT_DIR,
    DEFAULT_SITE_PAYLOAD_ROOT_DIR,
    SITE_PAYLOAD_SCHEMA_VERSION,
    generate_site_payloads,
    resolve_site_build_jobs,
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
    help="Generate site payload JSON files and the static HTML shell of the published website.",
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
    typer.echo(json.dumps(summary_obj.model_dump(mode="json", exclude_none=True), indent=2))


def _validate_progress_format(progress_format: str) -> None:
    if progress_format not in SUPPORTED_PROGRESS_FORMATS:
        allowed = ", ".join(sorted(SUPPORTED_PROGRESS_FORMATS))
        typer.echo(f"--progress-format must be one of: {allowed}", err=True)
        raise typer.Exit(code=1)


def _validate_jobs(jobs: str) -> None:
    try:
        resolve_site_build_jobs(jobs)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc


def _parse_worker_jobs(jobs: str) -> int | str:
    """Parse an 'auto'-or-integer worker option into materialize workers."""
    value = jobs.strip().lower()
    if value == "auto":
        return "auto"
    try:
        parsed = int(value)
        if parsed < 1:
            raise ValueError
    except ValueError:
        typer.echo(f"jobs must be 'auto' or an integer >= 1, got: {jobs!r}", err=True)
        raise typer.Exit(code=1) from None
    return parsed


def _ru_maxrss_to_gib(ru_maxrss: int) -> float:
    # Linux reports KiB; macOS reports bytes.
    bytes_value = ru_maxrss if sys.platform == "darwin" else ru_maxrss * 1024
    return bytes_value / (1024**3)


def _max_memory_gib() -> float | None:
    if resource is None:
        return None
    usages = [
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
    ]
    return round(max(_ru_maxrss_to_gib(value) for value in usages), 3)


def _format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.2f}s"
    minutes, remaining = divmod(seconds, 60)
    if minutes < 60:
        return f"{int(minutes)}m {remaining:.1f}s"
    hours, minutes = divmod(minutes, 60)
    return f"{int(hours)}h {int(minutes)}m {remaining:.1f}s"


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


@app.command("serve")
def serve_cmd(
    host: Annotated[
        str,
        typer.Option("--host", help="Bind address. Use 0.0.0.0 behind a reverse proxy."),
    ] = "127.0.0.1",
    port: Annotated[
        int,
        typer.Option(
            "--port",
            help="Bind port. Defaults to 8082 so a legacy Julia server on 8081 can keep running side by side; deployments pass their proxy target explicitly.",
        ),
    ] = 8082,
    repo_root: Annotated[
        Optional[Path],
        typer.Option("--repo-root", help="MAMUT-routing repo root to serve. Defaults to $MAMUT_ROUTING_ROOT or the current directory."),
    ] = None,
    log_level: Annotated[
        str,
        typer.Option("--log-level", help="uvicorn log level."),
    ] = "info",
) -> None:
    """Serve the built static website (dist/ plus repo artifact roots)."""
    import uvicorn

    from mamut_routing_publish.server import create_app

    resolved_root = _resolve_repo_dir(repo_root)
    uvicorn.run(create_app(resolved_root), host=host, port=port, log_level=log_level)


# ---------------------------------------------------------------------------
# site sub-commands
# ---------------------------------------------------------------------------


_OUTPUT_REPO_DIR_HELP = (
    f"Path to the MAMUT-routing repo root. Defaults to "
    f"${DEFAULT_MAMUT_ROUTING_ROOT_ENV} or the current working directory."
)


@site_app.command("materialize-atf")
def site_materialize_atf_cmd(
    output_repo_dir: Annotated[
        Optional[Path],
        typer.Option("--output-repo-dir", help=_OUTPUT_REPO_DIR_HELP),
    ] = None,
    max_n: Annotated[
        int,
        typer.Option(
            "--max-n",
            help="Materialize ATF sidecars only for igp-profile instances with at most this many customers (an n=1000 sidecar weighs ~82 MB gzipped).",
        ),
    ] = 400,
    jobs: Annotated[
        Optional[int],
        typer.Option("--jobs", help="Parallel materialization workers (default: cores - 2)."),
    ] = None,
) -> None:
    """Materialize ATF sidecars into dist/atf-cache (git-ignored).

    Covers materialized-td-model families with no committed sidecar (Lera2026
    igp-profile, Mamut2026 TD road-graph) so the arc-click viewer and BKS
    schedule tables work. `site build` runs this phase automatically; this
    standalone command exists to pre-warm the cache or use a custom cap.
    Incremental: existing cache files are reused; TDVRPTW/TDVRP twins share
    one file.
    """
    from mamut_routing_publish.atf_cache import materialize_atf_cache

    repo_dir = _resolve_repo_dir(output_repo_dir)
    summary = materialize_atf_cache(repo_dir, max_customers=max_n, jobs=jobs)
    typer.echo(json.dumps(summary.as_dict(), indent=1))


@site_app.command("precompress")
def site_precompress_cmd(
    output_repo_dir: Annotated[
        Optional[Path],
        typer.Option("--output-repo-dir", help=_OUTPUT_REPO_DIR_HELP),
    ] = None,
    site_output_dir: Annotated[
        Path,
        typer.Option(
            "--site-output-dir",
            help="Site tree to precompress. Relative paths resolve under --output-repo-dir.",
        ),
    ] = DEFAULT_SITE_OUTPUT_DIR,
    jobs: Annotated[
        Optional[int],
        typer.Option("--jobs", help="Parallel compression workers (default: cores - 2)."),
    ] = None,
) -> None:
    """Write .gz + .br sidecars for compressible site files (incremental)."""
    from mamut_routing_publish.precompress import precompress_tree
    from mamut_routing_publish.publish_roots import PublishRoots

    repo_dir = _resolve_repo_dir(output_repo_dir)
    root = PublishRoots.resolve(repo_dir, site_output_dir).site_output
    summary = precompress_tree(root, jobs=jobs)
    typer.echo(json.dumps(summary.as_dict(), indent=1))


@site_app.command("materialize-route-geometry")
def site_materialize_route_geometry_cmd(
    output_repo_dir: Annotated[
        Optional[Path],
        typer.Option("--output-repo-dir", help=_OUTPUT_REPO_DIR_HELP),
    ] = None,
    min_n: Annotated[
        int,
        typer.Option(
            "--min-n",
            help="Materialize BKS route geometry for Mamut2026 instances with at least this many customers (default: all sizes).",
        ),
    ] = 1,
    jobs: Annotated[
        str,
        typer.Option("--jobs", help="Parallel per-city materialization workers: 'auto' or an integer >= 1."),
    ] = "auto",
) -> None:
    """Materialize hash-addressed BKS road geometry into dist/.

    The cache is publication-only and incremental by exact BKS bytes. A
    changed BKS receives a new sidecar; unchanged BKS reuse their existing
    hash-addressed artifact.
    """
    from mamut_routing_publish.route_geometry import materialize_route_geometry

    repo_dir = _resolve_repo_dir(output_repo_dir)
    summary = materialize_route_geometry(repo_dir, min_customers=min_n, workers=_parse_worker_jobs(jobs))
    typer.echo(json.dumps(summary, indent=1))


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
    state_dir: Annotated[
        Optional[Path],
        typer.Option(
            "--state-dir",
            help="Persistent publication state dir (history ledger, snapshot inventories). Defaults to <repo>/publish-state. Relative paths resolve under --output-repo-dir.",
        ),
    ] = None,
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
        state_dir=state_dir,
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
    atf_max_n: Annotated[
        int,
        typer.Option(
            "--atf-max-n",
            help="Materialize ATF sidecars for materialized-td-model instances with at most this many customers before generating payloads (see `site materialize-atf`).",
        ),
    ] = 400,
    skip_atf_cache: Annotated[
        bool,
        typer.Option(
            "--skip-atf-cache",
            help="Skip the ATF sidecar cache materialization phase. Instance pages of materialized-td-model families (Lera2026, Mamut2026 TD) then lose their schedule tables and arc-click viewer unless dist/atf-cache is already populated.",
        ),
    ] = False,
    skip_route_geometry: Annotated[
        bool,
        typer.Option(
            "--skip-route-geometry",
            help="Skip BKS route-geometry materialization (route-geometry-cache). Pages whose BKS geometry is not already cached then fall back to straight lines. Staging builds materialize into the staging cache after seeding it from the active dist.",
        ),
    ] = False,
    route_geometry_jobs: Annotated[
        str,
        typer.Option(
            "--route-geometry-jobs",
            help="Parallel per-city route-geometry workers: 'auto' or an integer >= 1. Each worker holds one city road graph at a time.",
        ),
    ] = "auto",
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
    state_dir: Annotated[
        Optional[Path],
        typer.Option(
            "--state-dir",
            help="Persistent publication state dir (history ledger, snapshot inventories). Defaults to <repo>/publish-state. Relative paths resolve under --output-repo-dir.",
        ),
    ] = None,
    precompress: Annotated[
        bool,
        typer.Option(
            "--precompress",
            help="Write .gz + .br sidecars for compressible site files after the build, so `serve` can negotiate precompressed responses.",
        ),
    ] = False,
    progress_format: Annotated[
        str,
        typer.Option(
            "--progress-format",
            help="Progress output format: auto, text, json, or off.",
        ),
    ] = "auto",
    quiet: Annotated[
        bool,
        typer.Option("--quiet", help="Disable progress and status reporting."),
    ] = False,
    list_files: Annotated[
        bool,
        typer.Option("--list-files", help="Include generated file paths in the final JSON summary."),
    ] = False,
    jobs: Annotated[
        str,
        typer.Option("--jobs", help="Parallel instance-resolution workers: 'auto' or an integer >= 1."),
    ] = "auto",
) -> None:
    """Generate site payloads AND the static HTML shell in one step."""
    if payload_mode not in {"static", "api"}:
        typer.echo("--payload-mode must be one of: static, api", err=True)
        raise typer.Exit(code=1)
    _validate_progress_format(progress_format)
    _validate_jobs(jobs)
    build_started_at = time.perf_counter()
    reporter = make_progress_reporter(progress_format=progress_format, quiet=quiet)
    repo_dir = _resolve_repo_dir(output_repo_dir)
    reporter.phase("resolved repository", repo=repo_dir)
    reporter.phase("resolving source snapshot")
    resolved_commit = source_commit or _resolve_git_value(repo_dir, "rev-parse", "--short=12", "HEAD")
    if resolved_commit is None:
        typer.echo("Unable to determine a source commit. Pass --source-commit explicitly.", err=True)
        raise typer.Exit(code=1)
    resolved_branch = source_branch or _resolve_git_value(repo_dir, "rev-parse", "--abbrev-ref", "HEAD")
    reporter.phase("resolved source snapshot", commit=resolved_commit, branch=resolved_branch)

    if not skip_atf_cache:
        # Materialized-td-model families (Lera2026 igp-profile, Mamut2026 TD
        # road-graph) ship no committed ATF sidecar; without this phase a fresh
        # checkout silently builds their instance pages without schedule tables
        # or the arc-click viewer. Incremental: existing cache files are reused.
        from mamut_routing_publish.atf_cache import materialize_atf_cache
        from mamut_routing_publish.publish_roots import PublishRoots

        roots = PublishRoots.resolve(repo_dir, site_output_dir, state_dir)
        reporter.phase("materializing ATF sidecar cache", max_n=atf_max_n, cache_dir=roots.atf_cache_dir)
        atf_summary = materialize_atf_cache(
            repo_dir,
            max_customers=atf_max_n,
            cache_dir=roots.atf_cache_dir,
            seed_from=(roots.active_dist / "atf-cache") if not roots.in_place else None,
        )
        reporter.phase("materialized ATF sidecar cache", **atf_summary.as_dict())

    if not skip_route_geometry:
        from mamut_routing_publish.publish_roots import PublishRoots, hardlink_tree
        from mamut_routing_publish.route_geometry import materialize_route_geometry

        geometry_roots = PublishRoots.resolve(repo_dir, site_output_dir, state_dir)
        if not geometry_roots.in_place:
            # Seed the staging cache before the reuse check so unchanged BKS
            # artifacts are found instead of regenerated; payload generation
            # repeats this seeding, which is idempotent.
            hardlink_tree(geometry_roots.active_dist / "route-geometry-cache", geometry_roots.route_geometry_publish_dir)
        reporter.phase("materializing BKS route geometry", cache_dir=geometry_roots.route_geometry_publish_dir)
        geometry_summary = materialize_route_geometry(
            repo_dir,
            cache_dir=geometry_roots.route_geometry_publish_dir,
            workers=_parse_worker_jobs(route_geometry_jobs),
        )
        reporter.phase(
            "materialized BKS route geometry",
            generated=geometry_summary["generated"],
            reused=geometry_summary["reused"],
            workers=geometry_summary["workers"],
        )

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
        state_dir=state_dir,
        reporter=reporter,
        jobs=jobs,
        list_files=list_files,
    )
    webapp_summary = generate_site_webapp(
        repo_dir,
        payload_mode=payload_mode,
        payload_api_prefix=payload_api_prefix,
        payload_root_dir=payload_root_dir,
        site_output_dir=site_output_dir,
        reporter=reporter,
        list_files=list_files,
    )
    precompress_summary = None
    if precompress:
        from mamut_routing_publish.precompress import precompress_tree
        from mamut_routing_publish.publish_roots import PublishRoots

        precompress_root = PublishRoots.resolve(repo_dir, site_output_dir, state_dir).site_output
        reporter.phase("precompressing site tree", root=precompress_root)
        precompress_summary = precompress_tree(precompress_root)
        reporter.phase("precompressed site tree", **precompress_summary.as_dict())

    elapsed_seconds = time.perf_counter() - build_started_at
    generated_files_written = (
        payload_summary.payload_files_written
        + webapp_summary.html_files_written
        + webapp_summary.asset_files_written
    )
    build_summary = {
        "wall_time_seconds": round(elapsed_seconds, 3),
        "wall_time": _format_duration(elapsed_seconds),
        "generated_files_written": generated_files_written,
        "payload_files_written": payload_summary.payload_files_written,
        "html_files_written": webapp_summary.html_files_written,
        "asset_files_written": webapp_summary.asset_files_written,
        "benchmark_pages_written": payload_summary.benchmark_pages_written,
        "instance_pages_written": payload_summary.instance_pages_written,
        "jobs_requested": jobs,
        "jobs_resolved": resolve_site_build_jobs(jobs, payload_summary.instance_pages_written),
        "max_memory_gib": _max_memory_gib(),
    }
    if precompress_summary is not None:
        build_summary["precompress"] = precompress_summary.as_dict()
    reporter.phase(
        "build summary",
        wall_time=build_summary["wall_time"],
        generated_files=generated_files_written,
        max_memory_gib=build_summary["max_memory_gib"],
    )
    typer.echo(
        json.dumps(
            {
                "build_summary": build_summary,
                "payload_summary": payload_summary.model_dump(mode="json", exclude_none=True),
                "webapp_summary": webapp_summary.model_dump(mode="json", exclude_none=True),
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
    jobs: Annotated[
        Optional[int],
        typer.Option(
            "--jobs",
            min=1,
            help="Number of release archives to compress in parallel. Defaults to auto.",
        ),
    ] = None,
    compresslevel: Annotated[
        int,
        typer.Option(
            "--compresslevel",
            min=0,
            max=9,
            help="ZIP deflate compression level. Defaults to high compression for release size.",
        ),
    ] = DEFAULT_RELEASE_ARCHIVE_COMPRESS_LEVEL,
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
        jobs=jobs,
        compresslevel=compresslevel,
    )
    _emit_summary(summary)


# ---------------------------------------------------------------------------
# workbench — generation stages (OSM → CVRP base → TD bridge → TDVRP/TDVRPTW)
# ---------------------------------------------------------------------------

METHOD_TAGS = {"poi_categories": "poi", "parametric_attach": "par", "hybrid": "hyb"}
DEFAULT_SIZES = [10, 25, 50, 100, 500, 1000]
DEFAULT_METHODS = ["poi_categories", "hybrid"]


def _city_slug(city: str) -> str:
    return city.strip().lower().replace(" ", "_").replace("-", "_")


def _method_tag(method: str) -> str:
    if method not in METHOD_TAGS:
        raise typer.BadParameter(f"unknown sampling method {method!r}; known: {sorted(METHOD_TAGS)}")
    return METHOD_TAGS[method]


def _find_stage1_meta(repo_dir: Path, city_slug: str, n: int, method: str, seed: int) -> Path | None:
    """Locate the stage-1 meta of a (city, n, method, seed) sampling run.

    Metas being written by concurrent sampling tasks (Julia writes them
    non-atomically) parse as partial JSON; they are skipped: a concurrent
    writer is never writing the meta this call is looking for.
    """
    from mamut_routing_publish.td_generation.julia_driver import avg_route_size_for_n

    expected_route_size = avg_route_size_for_n(n)
    for meta_path in sorted((repo_dir / "instances_v2" / "osm" / city_slug).glob("*/*_meta.json")):
        try:
            params = json.loads(meta_path.read_text()).get("generation_params", {})
        except (ValueError, OSError):
            continue
        if (
            int(params.get("n_customers", -1)) == n
            and str(params.get("method", "")) == method
            and int(params.get("seed", -1)) == seed
            and int(params.get("avg_route_size", -1)) == expected_route_size
        ):
            return meta_path
    return None


def _bridge_dir(repo_dir: Path, city_slug: str) -> Path:
    return repo_dir / "instances_v2" / "td-bridge" / city_slug


def _resolve_out_root(repo_dir: Path, out_root: Path) -> Path:
    return out_root if out_root.is_absolute() else repo_dir / out_root


def _stage1_and_bridge_for_base(
    repo_dir: Path, city: str, n: int, method: str, *, osm_path: Optional[str], force_stage1: bool
) -> Path:
    """Ensure the Julia stage-1 sampling + graph/node bridge export exist for
    one base; returns the stage-1 meta path. Julia writes intermediates only."""
    from mamut_routing_publish.td_generation import base_instance_name, julia_driver, sampling_seed

    city_slug = _city_slug(city)
    tag = _method_tag(method)
    base = base_instance_name(city_slug, n, tag)
    seed = sampling_seed(base)
    meta_path = _find_stage1_meta(repo_dir, city_slug, n, method, seed)
    if meta_path is None or force_stage1:
        result = julia_driver.generate_base(
            repo_dir, city=city, n_customers=n, method=method, seed=seed, osm_path=osm_path
        )
        typer.echo(f"stage-1 sampled {result['base_name']} (seed {seed})")
        meta_path = _find_stage1_meta(repo_dir, city_slug, n, method, seed)
        if meta_path is None:
            raise RuntimeError(f"stage-1 meta not found after sampling for {base}")
    return meta_path


def _export_graph_and_nodes(
    repo_dir: Path, city: str, meta_paths: list[Path], *, osm_path: Optional[str], seed: int
) -> None:
    """Bridge export without speed files: graph.json + node maps only."""
    from mamut_routing_publish.td_generation import julia_driver

    julia_driver.export_bridge(
        repo_dir,
        osm_path=osm_path or f"osmdata/{city}.osm",
        city_slug=_city_slug(city),
        models=[],
        seed=seed,
        meta_paths=[str(path.relative_to(repo_dir)) for path in meta_paths],
    )


def _load_bridge_for_base(repo_dir: Path, city_slug: str, stage1_base: str):
    from mamut_routing_publish.td_generation import load_bridge_graph, load_bridge_nodes

    bridge_dir = _bridge_dir(repo_dir, city_slug)
    graph_path = bridge_dir / "graph.json"
    nodes_path = bridge_dir / f"nodes-{stage1_base}.json"
    for required in (graph_path, nodes_path):
        if not required.exists():
            raise typer.BadParameter(f"missing bridge file {required}")
    graph = load_bridge_graph(graph_path)
    nodes = load_bridge_nodes(nodes_path)
    return graph, nodes


def _publish_base(
    repo_dir: Path,
    city: str,
    n: int,
    method: str,
    out_root: Path,
    *,
    generated_at: Optional[str],
    force: bool,
):
    from mamut_routing_publish.td_generation import build_base

    city_slug = _city_slug(city)
    meta_path = _find_stage1_meta(
        repo_dir, city_slug, n, method,
        _stage1_seed(city_slug, n, method),
    )
    if meta_path is None:
        raise typer.BadParameter(f"stage-1 meta missing for {city_slug} n={n} {method}")
    meta = json.loads(meta_path.read_text())
    manifest = json.loads(
        (meta_path.parent / meta_path.name.replace("_meta.json", "_manifest.json")).read_text()
    )
    graph, nodes = _load_bridge_for_base(repo_dir, city_slug, str(meta["instance_name"]))
    return build_base(
        graph=graph,
        nodes=nodes,
        meta=meta,
        manifest=manifest,
        city=city_slug,
        method_tag=_method_tag(method),
        collection_root=out_root,
        generated_at=generated_at,
        force=force,
    )


def _stage1_seed(city_slug: str, n: int, method: str) -> int:
    from mamut_routing_publish.td_generation import base_instance_name, sampling_seed

    return sampling_seed(base_instance_name(city_slug, n, _method_tag(method)))


workbench_app = typer.Typer(
    help=(
        "Mamut2026 collection generation stages: fetch a city OSM extract, publish the "
        "CVRP base layer (generate-base), derive the VRPTW layer, run the traffic "
        "simulation, and build the TDVRP/TDVRPTW twins (road-graph v2 td model)."
    ),
    no_args_is_help=True,
)
app.add_typer(workbench_app, name="workbench")


@workbench_app.command("fetch-city")
def workbench_fetch_city_cmd(
    city: Annotated[str, typer.Argument(help="City name for Nominatim geocoding.")],
    country: Annotated[str, typer.Option(help="Optional country qualifier.")] = "",
    max_radius_km: Annotated[float, typer.Option(help="Clamp the bbox to this radius around its center (0 = no clamp; use for megacities like Tokyo).")] = 0.0,
    padding_km: Annotated[float, typer.Option(help="Expand the bbox by this margin.")] = 0.0,
    source_repo_dir: Annotated[Optional[Path], typer.Option(help="MAMUT-routing repo root.")] = None,
) -> None:
    """Download a city OSM extract into osmdata/ via Overpass."""
    from mamut_routing_tools.osm.fetch import fetch_and_store_city_osm

    repo_dir = _resolve_repo_dir(source_repo_dir)
    result = fetch_and_store_city_osm(
        city, country=country, osm_dir=repo_dir / "osmdata", max_radius_km=max_radius_km, padding_km=padding_km
    )
    typer.echo(json.dumps(result, indent=2))


@workbench_app.command("generate-base")
def workbench_generate_base_cmd(
    city: Annotated[str, typer.Argument(help="City name (osmdata/<City>.osm must exist).")],
    n: Annotated[Optional[list[int]], typer.Option(help="Customer counts (repeatable; default: the family grid).")] = None,
    method: Annotated[Optional[list[str]], typer.Option(help="Sampling methods (repeatable; default: poi_categories and hybrid).")] = None,
    out_root: Annotated[Path, typer.Option(help="Collection root (marker written if missing).")] = Path("benchmarks/Mamut2026"),
    osm_path: Annotated[Optional[str], typer.Option(help="Explicit OSM file path (default osmdata/<City>.osm).")] = None,
    generated_at: Annotated[Optional[str], typer.Option(help="ISO date stamped in metadata (default: today).")] = None,
    force: Annotated[bool, typer.Option(help="Republish bases whose files already exist.")] = False,
    force_stage1: Annotated[bool, typer.Option(help="Resample the Julia stage-1 intermediates.")] = False,
    source_repo_dir: Annotated[Optional[Path], typer.Option(help="MAMUT-routing repo root.")] = None,
) -> None:
    """Publish the base layer: 3 slim CVRP metric instances + geo/road/distances sidecars.

    Julia samples the base and exports the graph/node bridge (intermediates
    only); the Python builder canonicalizes and publishes every artifact.
    """
    repo_dir = _resolve_repo_dir(source_repo_dir)
    sizes = n or DEFAULT_SIZES
    methods = method or DEFAULT_METHODS
    out = _resolve_out_root(repo_dir, out_root)
    meta_paths = [
        _stage1_and_bridge_for_base(repo_dir, city, size, sampling, osm_path=osm_path, force_stage1=force_stage1)
        for size in sizes
        for sampling in methods
    ]
    _export_graph_and_nodes(repo_dir, city, meta_paths, osm_path=osm_path, seed=42)
    for size in sizes:
        for sampling in methods:
            result = _publish_base(repo_dir, city, size, sampling, out, generated_at=generated_at, force=force)
            if result is None:
                typer.echo(f"kept {_city_slug(city)} n={size} {sampling} (already published)")
                continue
            typer.echo(
                f"published {result.base}: road {result.num_road_vertices}v/{result.num_road_edges}e, "
                f"3 CVRP + geo + 2 distances, {result.build_seconds:.1f}s"
            )


@workbench_app.command("derive-vrptw")
def workbench_derive_vrptw_cmd(
    city: Annotated[str, typer.Argument(help="City name or slug.")],
    n: Annotated[Optional[list[int]], typer.Option(help="Customer counts (repeatable; default: the family grid).")] = None,
    method: Annotated[Optional[list[str]], typer.Option(help="Sampling methods (repeatable).")] = None,
    tw_set: Annotated[Optional[list[str]], typer.Option(help="TW sets (repeatable; default: td-shared, tight, spread).")] = None,
    out_root: Annotated[Path, typer.Option(help="Collection root.")] = Path("benchmarks/Mamut2026"),
    generated_at: Annotated[Optional[str], typer.Option(help="ISO date stamped in metadata.")] = None,
    force: Annotated[bool, typer.Option(help="Re-derive even if the VRPTW instance exists.")] = False,
    source_repo_dir: Annotated[Optional[Path], typer.Option(help="MAMUT-routing repo root.")] = None,
) -> None:
    """Derive the VRPTW layer: the td-shared candidate (base-name-seeded TWs
    over free-flow fastest, finalized by build-td) plus the static-only TW
    sets (tight, spread; final as written)."""
    from mamut_routing_publish.td_generation import ALL_TW_SETS, derive_vrptw

    repo_dir = _resolve_repo_dir(source_repo_dir)
    out = _resolve_out_root(repo_dir, out_root)
    for size in n or DEFAULT_SIZES:
        for sampling in method or DEFAULT_METHODS:
            for set_name in tw_set or ALL_TW_SETS:
                action, target = derive_vrptw(
                    collection_root=out,
                    city=_city_slug(city),
                    num_customers=size,
                    method_tag=_method_tag(sampling),
                    tw_set=set_name,
                    generated_at=generated_at,
                    force=force,
                )
                typer.echo(
                    f"kept {_city_slug(city)} n={size} {sampling} [{set_name}] (already derived)"
                    if action == "kept"
                    else f"{action} {target}"
                )


@workbench_app.command("traffic-sim")
def workbench_traffic_sim_cmd(
    city: Annotated[str, typer.Argument(help="City name (osmdata/<City>.osm must exist).")],
    model: Annotated[Optional[list[str]], typer.Option(help="Traffic models (default: bpr and wave).")] = None,
    intensity: Annotated[Optional[list[str]], typer.Option(help="Intensities (default: light, moderate, heavy).")] = None,
    seed: Annotated[int, typer.Option(help="Traffic simulation seed.")] = 42,
    force: Annotated[bool, typer.Option(help="Recompute speed files even if present.")] = False,
    osm_path: Annotated[Optional[str], typer.Option(help="Explicit OSM file path.")] = None,
    source_repo_dir: Annotated[Optional[Path], typer.Option(help="MAMUT-routing repo root.")] = None,
) -> None:
    """Run the traffic stage: citywide per-edge hourly speed fields (bridge export)."""
    from mamut_routing_publish.td_generation import julia_driver

    repo_dir = _resolve_repo_dir(source_repo_dir)
    result = julia_driver.export_bridge(
        repo_dir,
        osm_path=osm_path or f"osmdata/{city}.osm",
        city_slug=_city_slug(city),
        models=model,
        intensities=intensity,
        seed=seed,
        meta_paths=[],
        force=force,
    )
    typer.echo(json.dumps({"bridge_dir": result}, indent=2))


@workbench_app.command("build-td")
def workbench_build_td_cmd(
    city: Annotated[str, typer.Argument(help="City name or slug (bridge under instances_v2/td-bridge/<slug>).")],
    n: Annotated[Optional[list[int]], typer.Option(help="Customer counts (repeatable; default: the family grid).")] = None,
    method: Annotated[Optional[list[str]], typer.Option(help="Sampling methods (repeatable).")] = None,
    out_root: Annotated[Path, typer.Option(help="Collection root.")] = Path("benchmarks/Mamut2026"),
    generated_at: Annotated[Optional[str], typer.Option(help="ISO date stamped in metadata.")] = None,
    force: Annotated[bool, typer.Option(help="Rebuild twins whose instance files already exist.")] = False,
    verify: Annotated[bool, typer.Option(help="Full sha-verified reload of every written twin.")] = True,
    tdvrptw_only: Annotated[bool, typer.Option(help="Rewrite only TDVRPTW twins and preserve existing TDVRP/traffic artifacts.")] = False,
    reuse_traffic: Annotated[bool, typer.Option(help="Reuse existing traffic overlays and ATF hashes instead of rebuilding traffic artifacts.")] = False,
    source_repo_dir: Annotated[Optional[Path], typer.Option(help="MAMUT-routing repo root.")] = None,
) -> None:
    """Build the TD layer of each base: 6 traffic overlays, the shared TW lift
    (finalizing the VRPTW instance) and the 12 slim TDVRP/TDVRPTW twins."""
    from mamut_routing_publish.td_generation import (
        TD_INTENSITIES,
        TD_MODELS,
        build_td,
        load_bridge_graph,
        load_bridge_speeds,
    )

    repo_dir = _resolve_repo_dir(source_repo_dir)
    city_slug = _city_slug(city)
    out = _resolve_out_root(repo_dir, out_root)
    bridge_dir = _bridge_dir(repo_dir, city_slug)
    graph = load_bridge_graph(bridge_dir / "graph.json")
    speeds_by_combo = {}
    if not (reuse_traffic or tdvrptw_only):
        for combo_model in TD_MODELS:
            for combo_intensity in TD_INTENSITIES:
                speeds_path = bridge_dir / f"speeds-{combo_model}-{combo_intensity}.json"
                if not speeds_path.exists():
                    raise typer.BadParameter(f"missing {speeds_path} (run 'workbench traffic-sim' first)")
                speeds_by_combo[(combo_model, combo_intensity)] = load_bridge_speeds(speeds_path, graph)

    started = time.perf_counter()
    built = skipped = 0
    for size in n or DEFAULT_SIZES:
        for sampling in method or DEFAULT_METHODS:
            result = build_td(
                collection_root=out,
                graph=graph,
                speeds_by_combo=speeds_by_combo,
                city=city_slug,
                num_customers=size,
                method_tag=_method_tag(sampling),
                generated_at=generated_at,
                force=force,
                verify=verify,
                tdvrptw_only=tdvrptw_only,
                reuse_traffic=reuse_traffic,
            )
            if result is None:
                skipped += 1
                continue
            built += 1
            typer.echo(
                f"built {result.base}: 12 twins, {result.lifted_customers} TW lifts "
                f"(max {result.max_lift_seconds}s), {result.reduced_customers} TW reductions "
                f"(max {result.max_reduction_seconds}s), {result.build_seconds:.1f}s"
            )
    typer.echo(f"done: {built} bases built, {skipped} kept in {_format_duration(time.perf_counter() - started)}")


@workbench_app.command("build-family")
def workbench_build_family_cmd(
    city: Annotated[str, typer.Argument(help="City name.")],
    n: Annotated[Optional[list[int]], typer.Option(help="Customer counts (repeatable; default: the family grid).")] = None,
    method: Annotated[Optional[list[str]], typer.Option(help="Sampling methods (repeatable; default: poi_categories and hybrid).")] = None,
    out_root: Annotated[Path, typer.Option(help="Collection root.")] = Path("benchmarks/Mamut2026"),
    max_radius_km: Annotated[float, typer.Option(help="Bbox clamp for fetch-city (0 = no clamp).")] = 0.0,
    traffic_seed: Annotated[int, typer.Option(help="Traffic simulation seed.")] = 42,
    generated_at: Annotated[Optional[str], typer.Option(help="ISO date stamped in metadata.")] = None,
    validate: Annotated[bool, typer.Option(help="Run the full validation sweep at the end.")] = False,
    force: Annotated[bool, typer.Option(help="Republish artifacts that already exist.")] = False,
    source_repo_dir: Annotated[Optional[Path], typer.Option(help="MAMUT-routing repo root.")] = None,
) -> None:
    """Run the whole pipeline for one city: fetch-city (if needed), generate-base,
    derive-vrptw, traffic-sim, build-td (and optionally the validation sweep)."""
    from mamut_routing_publish.td_generation import julia_driver

    repo_dir = _resolve_repo_dir(source_repo_dir)
    osm_file = repo_dir / "osmdata" / f"{city}.osm"
    if not osm_file.exists():
        from mamut_routing_tools.osm.fetch import fetch_and_store_city_osm

        typer.echo(f"fetching {city} OSM extract...")
        fetch_and_store_city_osm(city, osm_dir=repo_dir / "osmdata", max_radius_km=max_radius_km)
    ctx_args = dict(n=n, method=method, out_root=out_root, source_repo_dir=source_repo_dir)
    workbench_generate_base_cmd(city, generated_at=generated_at, force=force, force_stage1=False, osm_path=None, **ctx_args)
    workbench_derive_vrptw_cmd(city, generated_at=generated_at, force=force, **ctx_args)
    workbench_traffic_sim_cmd(city, model=None, intensity=None, seed=traffic_seed, force=False, osm_path=None, source_repo_dir=source_repo_dir)
    workbench_build_td_cmd(
        city,
        generated_at=generated_at,
        force=force,
        verify=True,
        tdvrptw_only=False,
        reuse_traffic=False,
        **ctx_args,
    )
    if validate:
        out = _resolve_out_root(repo_dir, out_root)
        workbench_validate_cmd(out, verify_sha256=True)


@workbench_app.command("td-validate")
def workbench_validate_cmd(
    root: Annotated[Path, typer.Argument(help="Directory tree holding instances (*.vrp.json).")],
    verify_sha256: Annotated[bool, typer.Option(help="Verify sidecar and materialized-ATF digests.")] = True,
) -> None:
    """Full-load validation sweep: TD instances (sha-verified materialization)
    plus, inside a collection, the slim CVRP/VRPTW instances (matrix
    hydration + geo sidecar digests)."""
    from mamut_routing_lib import load_benchmark_instance, resolve_arc_costs
    from mamut_routing_lib.geo import compute_geo_sha256, load_instance_geo
    from mamut_routing_lib.sidecars import find_collection_root
    from mamut_routing_lib.td import load_td_instance

    paths = sorted(root.rglob("*.vrp.json"))
    if not paths:
        raise typer.BadParameter(f"no *.vrp.json under {root}")
    failures = 0
    started = time.perf_counter()
    geo_checked: set[str] = set()
    base_attributes: dict[str, tuple[tuple[int, ...], int]] = {}
    min_lb_cap: int | None = None
    zero_width_windows = 0
    for path in paths:
        try:
            payload = json.loads(path.read_text())
            demands = tuple(int(value) for value in payload["demands"])
            capacity = int(payload["vehicle_capacity"])
            from mamut_routing_publish.td_generation.family import capacity_lower_bound

            lb_cap = capacity_lower_bound(list(demands), capacity)
            min_lb_cap = lb_cap if min_lb_cap is None else min(min_lb_cap, lb_cap)
            if lb_cap < 2:
                raise ValueError(f"LB_cap={lb_cap}; Mamut2026 requires at least two routes")
            if max(demands[1:], default=0) > capacity:
                raise ValueError("customer demand exceeds vehicle capacity")
            base_name = str(payload.get("metadata", {}).get("base_instance_name", payload["instance_name"]))
            attributes = (demands, capacity)
            previous = base_attributes.setdefault(base_name, attributes)
            if previous != attributes:
                raise ValueError(f"base attributes disagree across variants of {base_name}")
            windows = payload.get("time_windows")
            if windows is not None:
                collapsed = [index for index, (earliest, latest) in enumerate(windows[1:], 1) if earliest >= latest]
                zero_width_windows += len(collapsed)
                if collapsed:
                    raise ValueError(
                        f"{len(collapsed)} non-positive-width client windows; first customers {collapsed[:10]}"
                    )
            if "td" in payload:
                load_td_instance(path, verify_sha256=verify_sha256)
            else:
                instance = load_benchmark_instance(path)
                if hasattr(instance, "arc_costs_source"):
                    resolve_arc_costs(instance, path)
            if verify_sha256:
                geo_ref = payload.get("metadata", {}).get("sidecars", {}).get("geo")
                if geo_ref and geo_ref.get("sha256") and geo_ref["path"] not in geo_checked:
                    geo_checked.add(geo_ref["path"])
                    collection_root = find_collection_root(path)
                    if collection_root is None:
                        raise ValueError("geo sidecar reference outside a collection")
                    digest = compute_geo_sha256(load_instance_geo(collection_root / geo_ref["path"]))
                    if digest != geo_ref["sha256"]:
                        raise ValueError(f"geo sha256 mismatch for {geo_ref['path']}")
        except Exception as error:  # noqa: BLE001 - report and continue the sweep
            failures += 1
            typer.echo(f"FAIL {path}: {error}", err=True)
    typer.echo(
        f"validated {len(paths) - failures}/{len(paths)} instances "
        f"({len(geo_checked)} geo sidecars, min LB_cap={min_lb_cap}, "
        f"zero-width windows={zero_width_windows}) in {_format_duration(time.perf_counter() - started)}"
    )
    if failures:
        raise typer.Exit(code=1)


def _entrypoint() -> None:  # pragma: no cover - thin wrapper
    app()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(app())
