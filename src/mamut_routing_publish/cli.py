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

``site build`` / ``site webapp`` also read ``MAMUT_BASEMAP_API_KEY`` as the
default for ``--basemap-api-key`` (the CARTO basemaps key embedded in the
workbench page; never commit its value).
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


def _parse_optional_jobs(jobs: str) -> int | None:
    """Parse an 'auto'-or-integer worker option; 'auto' becomes None (phase default)."""
    parsed = _parse_worker_jobs(jobs)
    return None if parsed == "auto" else int(parsed)


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
    igp-profile, Poryos2026 TD road-graph) so the arc-click viewer and BKS
    schedule tables work. `site build` runs this phase automatically; this
    standalone command exists to pre-warm the cache or use a custom cap.
    Incremental: existing cache files are reused; TDVRPTW/TDVRP twins share
    one file.
    """
    from mamut_routing_publish.atf_cache import materialize_atf_cache

    if jobs is not None and jobs < 1:
        typer.echo(f"--jobs must be an integer >= 1, got: {jobs}", err=True)
        raise typer.Exit(code=1)
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
            help="Materialize BKS route geometry for Poryos2026 instances with at least this many customers (default: all sizes).",
        ),
    ] = 1,
    jobs: Annotated[
        str,
        typer.Option(
            "--jobs",
            help="Parallel per-city materialization workers: 'auto' (1, memory-safe) or an integer >= 1.",
        ),
    ] = "auto",
    fetch_missing_osm: Annotated[
        bool,
        typer.Option(
            "--fetch-missing-osm/--no-fetch-missing-osm",
            help="Fetch and validate missing source road extracts from benchmark sidecar bounds before materializing.",
        ),
    ] = False,
) -> None:
    """Materialize hash-addressed BKS road geometry into dist/.

    The cache is publication-only and incremental by exact BKS bytes. A
    changed BKS receives a new sidecar; unchanged BKS reuse their existing
    hash-addressed artifact.
    """
    from mamut_routing_publish.route_geometry import materialize_route_geometry

    repo_dir = _resolve_repo_dir(output_repo_dir)

    def report_osm_progress(event: str, fields: dict[str, Any]) -> None:
        typer.echo(
            f"[route geometry] {event} "
            + " ".join(f"{key}={value}" for key, value in fields.items()),
            err=True,
        )

    summary = materialize_route_geometry(
        repo_dir,
        min_customers=min_n,
        workers=_parse_worker_jobs(jobs),
        fetch_missing_osm=fetch_missing_osm,
        osm_progress=report_osm_progress if fetch_missing_osm else None,
    )
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
    basemap_api_key: Annotated[
        Optional[str],
        typer.Option(
            "--basemap-api-key",
            envvar="MAMUT_BASEMAP_API_KEY",
            show_envvar=True,
            help=(
                "CARTO basemaps API key written into the workbench page so the map can use the "
                "CARTO Positron / Dark Matter vector basemaps. Without it the workbench map falls "
                "back to OpenStreetMap tiles."
            ),
        ),
    ] = None,
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
        basemap_api_key=basemap_api_key,
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
    atf_jobs: Annotated[
        str,
        typer.Option(
            "--atf-jobs",
            help="Parallel ATF sidecar materialization workers: 'auto' (cores - 2) or an integer >= 1. Each worker holds one full ATF set at a time, so this caps the phase's memory as well as its speed.",
        ),
    ] = "auto",
    skip_atf_cache: Annotated[
        bool,
        typer.Option(
            "--skip-atf-cache",
            help="Skip the ATF sidecar cache materialization phase. Instance pages of materialized-td-model families (Lera2026, Poryos2026 TD) then lose their schedule tables and arc-click viewer unless dist/atf-cache is already populated.",
        ),
    ] = False,
    skip_route_geometry: Annotated[
        bool,
        typer.Option(
            "--skip-route-geometry",
            help="Skip BKS route-geometry materialization (route-geometry-cache). Pages whose BKS geometry is not already cached then fall back to straight lines. Staging builds materialize into the staging cache after seeding it from the active dist.",
        ),
    ] = False,
    fetch_missing_osm: Annotated[
        bool,
        typer.Option(
            "--fetch-missing-osm/--no-fetch-missing-osm",
            help="Automatically fetch and validate missing Poryos2026 source road extracts before route-geometry materialization.",
        ),
    ] = True,
    route_geometry_jobs: Annotated[
        str,
        typer.Option(
            "--route-geometry-jobs",
            help="Parallel per-city route-geometry workers: 'auto' (1, memory-safe) or an integer >= 1. Each worker can hold a 15+ GiB city road graph.",
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
    basemap_api_key: Annotated[
        Optional[str],
        typer.Option(
            "--basemap-api-key",
            envvar="MAMUT_BASEMAP_API_KEY",
            show_envvar=True,
            help=(
                "CARTO basemaps API key written into the workbench page so the map can use the "
                "CARTO Positron / Dark Matter vector basemaps. Without it the workbench map falls "
                "back to OpenStreetMap tiles."
            ),
        ),
    ] = None,
) -> None:
    """Generate site payloads AND the static HTML shell in one step."""
    if payload_mode not in {"static", "api"}:
        typer.echo("--payload-mode must be one of: static, api", err=True)
        raise typer.Exit(code=1)
    _validate_progress_format(progress_format)
    _validate_jobs(jobs)
    # Parsed up front so a bad value fails before any work, even when the
    # phase it belongs to is skipped.
    atf_jobs_requested = _parse_optional_jobs(atf_jobs)
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
    geometry_summary: dict[str, Any] | None = None

    if not skip_atf_cache:
        # Materialized-td-model families (Lera2026 igp-profile, Poryos2026 TD
        # road-graph) ship no committed ATF sidecar; without this phase a fresh
        # checkout silently builds their instance pages without schedule tables
        # or the arc-click viewer. Incremental: existing cache files are reused.
        from mamut_routing_publish.atf_cache import materialize_atf_cache, resolve_atf_jobs
        from mamut_routing_publish.publish_roots import PublishRoots

        roots = PublishRoots.resolve(repo_dir, site_output_dir, state_dir)
        resolved_atf_jobs = resolve_atf_jobs(atf_jobs_requested)
        reporter.phase(
            "materializing ATF sidecar cache",
            max_n=atf_max_n,
            jobs=resolved_atf_jobs,
            cache_dir=roots.atf_cache_dir,
        )
        atf_summary = materialize_atf_cache(
            repo_dir,
            max_customers=atf_max_n,
            jobs=resolved_atf_jobs,
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

        def report_osm_progress(event: str, fields: dict[str, Any]) -> None:
            reporter.phase(f"{event} route-geometry OSM", **fields)

        geometry_summary = materialize_route_geometry(
            repo_dir,
            cache_dir=geometry_roots.route_geometry_publish_dir,
            workers=_parse_worker_jobs(route_geometry_jobs),
            fetch_missing_osm=fetch_missing_osm,
            skip_missing_osm=not fetch_missing_osm,
            osm_progress=report_osm_progress,
        )
        reporter.phase(
            "materialized BKS route geometry",
            generated=geometry_summary["generated"],
            reused=geometry_summary["reused"],
            osm_fetched=geometry_summary["osm"]["fetched"],
            osm_valid_existing=geometry_summary["osm"]["valid_existing"],
            skipped_missing_osm_groups=geometry_summary["skipped_missing_osm_groups"],
            skipped_missing_osm_bks=geometry_summary["skipped_missing_osm_bks"],
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
        basemap_api_key=basemap_api_key,
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
    if geometry_summary is not None:
        build_summary["route_geometry"] = {
            key: value for key, value in geometry_summary.items() if key != "paths"
        }
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


def _entrypoint() -> None:  # pragma: no cover - thin wrapper
    app()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(app())
