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
    """Materialize igp-profile ATF sidecars into dist/atf-cache (git-ignored).

    Run before `site build` so the arc-click viewer and BKS schedule tables
    have sidecars for igp-profile families (Lera2026). Incremental: existing
    cache files are reused; TDVRPTW/TDVRP twins share one file.
    """
    from mamut_routing_publish.atf_cache import materialize_atf_cache

    repo_dir = _resolve_repo_dir(output_repo_dir)
    summary = materialize_atf_cache(repo_dir, max_customers=max_n, jobs=jobs)
    typer.echo(json.dumps(summary.as_dict(), indent=1))


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


def _find_base_meta(repo_dir: Path, city_slug: str, base_name: str) -> Path:
    matches = sorted((repo_dir / "instances_v2" / "osm" / city_slug).glob(f"*/{base_name}_meta.json"))
    if not matches:
        raise typer.BadParameter(
            f"no stage-1 meta found for base '{base_name}' under instances_v2/osm/{city_slug}/ "
            "(run 'workbench generate-base' first)"
        )
    return matches[0]


def _build_one_td_cell(
    repo_dir: Path,
    city_slug: str,
    base_name: str,
    model: str,
    intensity: str,
    out_root: Path,
    *,
    sample_step: float,
    tolerance: float,
    generated_at: Optional[str],
    force: bool,
):
    from mamut_routing_publish.td_generation import (
        build_td_instance_pair,
        load_bridge_graph,
        load_bridge_nodes,
        load_bridge_speeds,
    )

    bridge_dir = repo_dir / "instances_v2" / "td-bridge" / city_slug
    nodes_path = bridge_dir / f"nodes-{base_name}.json"
    speeds_path = bridge_dir / f"speeds-{model}-{intensity}.json"
    for required in (bridge_dir / "graph.json", speeds_path, nodes_path):
        if not required.exists():
            raise typer.BadParameter(
                f"missing bridge file {required} (run 'workbench traffic-sim' with the right options first)"
            )
    meta_path = _find_base_meta(repo_dir, city_slug, base_name)
    meta = json.loads(meta_path.read_text())
    manifest = json.loads((meta_path.parent / f"{base_name}_manifest.json").read_text())
    method_tag = METHOD_TAGS.get(str(meta.get("method", "")), "gen")

    graph = load_bridge_graph(bridge_dir / "graph.json")
    speeds = load_bridge_speeds(speeds_path, graph)
    nodes = load_bridge_nodes(nodes_path)
    return build_td_instance_pair(
        graph=graph,
        speeds=speeds,
        nodes=nodes,
        meta=meta,
        vehicle_capacity=int(manifest["capacity"]),
        place=city_slug,
        method=method_tag,
        out_root=out_root,
        sample_step=sample_step,
        simplify_tolerance=tolerance,
        generated_at=generated_at,
        force=force,
    )


workbench_app = typer.Typer(
    help=(
        "Workbench generation stages: fetch a city OSM extract, generate stage-1 CVRP "
        "bases, run the traffic stage (TD bridge), and build TDVRP/TDVRPTW instances "
        "of the road-graph td model."
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
    from mamut_routing_publish.td_generation import julia_driver

    repo_dir = _resolve_repo_dir(source_repo_dir)
    result = julia_driver.fetch_city(
        repo_dir, city=city, country=country, max_radius_km=max_radius_km, padding_km=padding_km
    )
    typer.echo(json.dumps(result, indent=2))


@workbench_app.command("generate-base")
def workbench_generate_base_cmd(
    city: Annotated[str, typer.Argument(help="City name (osmdata/<City>.osm must exist).")],
    n: Annotated[int, typer.Option(help="Number of customers.")] = 100,
    method: Annotated[str, typer.Option(help="Customer sampling: poi_categories | parametric_attach | hybrid.")] = "hybrid",
    seed: Annotated[int, typer.Option(help="Generation seed.")] = 42,
    osm_path: Annotated[Optional[str], typer.Option(help="Explicit OSM file path (default osmdata/<City>.osm).")] = None,
    source_repo_dir: Annotated[Optional[Path], typer.Option(help="MAMUT-routing repo root.")] = None,
) -> None:
    """Generate one stage-1 CVRP base instance (three metric variants + meta/manifest)."""
    from mamut_routing_publish.td_generation import julia_driver

    repo_dir = _resolve_repo_dir(source_repo_dir)
    result = julia_driver.generate_base(
        repo_dir, city=city, n_customers=n, method=method, seed=seed, osm_path=osm_path
    )
    typer.echo(json.dumps(result, indent=2))


@workbench_app.command("traffic-sim")
def workbench_traffic_sim_cmd(
    city: Annotated[str, typer.Argument(help="City name (osmdata/<City>.osm must exist).")],
    model: Annotated[Optional[list[str]], typer.Option(help="Traffic models (default: bpr and wave).")] = None,
    intensity: Annotated[Optional[list[str]], typer.Option(help="Intensities (default: light, moderate, heavy).")] = None,
    seed: Annotated[int, typer.Option(help="Traffic simulation seed.")] = 42,
    nodes_for: Annotated[Optional[list[str]], typer.Option(help="Stage-1 base names to export node maps for (repeatable).")] = None,
    all_bases: Annotated[bool, typer.Option("--all-bases", help="Export node maps for every stage-1 base of this city.")] = False,
    force: Annotated[bool, typer.Option(help="Recompute speed files even if present.")] = False,
    osm_path: Annotated[Optional[str], typer.Option(help="Explicit OSM file path.")] = None,
    source_repo_dir: Annotated[Optional[Path], typer.Option(help="MAMUT-routing repo root.")] = None,
) -> None:
    """Run the traffic stage: per-edge hourly speed profiles + TD bridge export."""
    from mamut_routing_publish.td_generation import julia_driver

    repo_dir = _resolve_repo_dir(source_repo_dir)
    city_slug = city.strip().lower().replace(" ", "_").replace("-", "_")
    resolved_osm = osm_path or f"osmdata/{city}.osm"
    meta_paths: list[str] = []
    if all_bases:
        meta_paths = [
            str(path.relative_to(repo_dir))
            for path in sorted((repo_dir / "instances_v2" / "osm" / city_slug).glob("*/*_meta.json"))
        ]
    elif nodes_for:
        meta_paths = [str(_find_base_meta(repo_dir, city_slug, base).relative_to(repo_dir)) for base in nodes_for]
    result = julia_driver.export_bridge(
        repo_dir,
        osm_path=resolved_osm,
        city_slug=city_slug,
        models=model,
        intensities=intensity,
        seed=seed,
        meta_paths=meta_paths,
        force=force,
    )
    typer.echo(json.dumps({"bridge_dir": result, "node_maps": len(meta_paths)}, indent=2))


@workbench_app.command("build-td")
def workbench_build_td_cmd(
    city: Annotated[str, typer.Argument(help="City slug (bridge under instances_v2/td-bridge/<city>).")],
    base: Annotated[Optional[list[str]], typer.Option(help="Stage-1 base names (repeatable; default: every base with a node map).")] = None,
    model: Annotated[Optional[list[str]], typer.Option(help="Traffic models (default: every model with a speeds file).")] = None,
    intensity: Annotated[Optional[list[str]], typer.Option(help="Intensities (default: every intensity with a speeds file).")] = None,
    out_root: Annotated[Path, typer.Option(help="Output benchmarks root (satellite mount or scratch).")] = Path("benchmarks"),
    sample_step: Annotated[float, typer.Option(help="Departure-grid spacing (s) of the road-graph materialization.")] = 60.0,
    tolerance: Annotated[float, typer.Option(help="Simplify tolerance (s) of the road-graph materialization.")] = 1.0,
    generated_at: Annotated[Optional[str], typer.Option(help="ISO date stamped in metadata (default: today).")] = None,
    force: Annotated[bool, typer.Option(help="Rebuild cells whose instance files already exist.")] = False,
    source_repo_dir: Annotated[Optional[Path], typer.Option(help="MAMUT-routing repo root.")] = None,
) -> None:
    """Build TDVRP + TDVRPTW twin instances for (base × model × intensity) cells."""
    repo_dir = _resolve_repo_dir(source_repo_dir)
    bridge_dir = repo_dir / "instances_v2" / "td-bridge" / city
    if not bridge_dir.exists():
        raise typer.BadParameter(f"no TD bridge at {bridge_dir}")
    bases = base or sorted(p.name[len("nodes-"):-len(".json")] for p in bridge_dir.glob("nodes-*.json"))
    combos = sorted(
        tuple(p.name[len("speeds-"):-len(".json")].split("-", 1))
        for p in bridge_dir.glob("speeds-*.json")
    )
    if model:
        combos = [c for c in combos if c[0] in set(model)]
    if intensity:
        combos = [c for c in combos if c[1] in set(intensity)]
    if not bases or not combos:
        raise typer.BadParameter("nothing to build: no node maps or no matching speed files in the bridge")

    built = skipped = 0
    started = time.perf_counter()
    for base_name in bases:
        for cell_model, cell_intensity in combos:
            result = _build_one_td_cell(
                repo_dir, city, base_name, cell_model, cell_intensity,
                out_root if out_root.is_absolute() else repo_dir / out_root,
                sample_step=sample_step, tolerance=tolerance,
                generated_at=generated_at, force=force,
            )
            if result is None:
                skipped += 1
                continue
            built += 1
            typer.echo(
                f"built {result.instance_name}: road {result.num_road_vertices}v/"
                f"{result.num_road_edges}e, sidecar {result.sidecar_bytes_gz / 1e3:.0f} KB gz, "
                f"{result.build_seconds:.1f}s"
            )
    typer.echo(f"done: {built} built, {skipped} kept (already present) in {_format_duration(time.perf_counter() - started)}")


@workbench_app.command("td-validate")
def workbench_td_validate_cmd(
    root: Annotated[Path, typer.Argument(help="Directory tree holding TD instances (*.vrp.json).")],
    verify_sha256: Annotated[bool, typer.Option(help="Verify sidecar and materialized-ATF digests.")] = True,
) -> None:
    """Full-load validation sweep over every TD instance under a directory."""
    from mamut_routing_lib.td import load_td_instance

    paths = sorted(root.rglob("*.vrp.json"))
    if not paths:
        raise typer.BadParameter(f"no *.vrp.json under {root}")
    failures = 0
    started = time.perf_counter()
    for path in paths:
        try:
            load_td_instance(path, verify_sha256=verify_sha256)
        except Exception as error:  # noqa: BLE001 - report and continue the sweep
            failures += 1
            typer.echo(f"FAIL {path}: {error}", err=True)
    typer.echo(
        f"validated {len(paths) - failures}/{len(paths)} instances in "
        f"{_format_duration(time.perf_counter() - started)}"
    )
    if failures:
        raise typer.Exit(code=1)


def _entrypoint() -> None:  # pragma: no cover - thin wrapper
    app()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(app())
