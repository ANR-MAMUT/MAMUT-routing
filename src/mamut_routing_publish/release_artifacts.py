from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import warnings
import zipfile

from pydantic import BaseModel, ConfigDict

from mamut_routing_lib.artifacts import discover_benchmark_instances
from mamut_routing_lib.enums import BenchmarkName, ProblemType
from mamut_routing_lib.json_utils import save_json_to_file
from mamut_routing_lib.remote import (
    DEFAULT_MANIFEST_FILENAME,
    ReleaseArchiveAsset,
    ReleaseArchiveManifest,
    ReleaseArchiveScope,
    compute_sha256,
)


_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
GITHUB_RELEASES_DOCS_URL = "https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases"
GITHUB_RELEASE_ASSET_WARNING_SIZE_BYTES = int(1.5 * 1024 * 1024 * 1024)
GITHUB_RELEASE_ASSET_MAX_SIZE_BYTES = 2 * 1024 * 1024 * 1024


@dataclass(frozen=True)
class _ArchiveRequest:
    scope: ReleaseArchiveScope
    filename: str
    archive_root: str
    include_dirs: tuple[Path, ...]
    problem_type: ProblemType | None = None
    benchmark_name: BenchmarkName | None = None


class ReleaseArtifactGenerationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_id: str
    published_at: str
    source_commit: str
    output_dir: str
    manifest_path: str
    archive_count: int
    archives: list[str]


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _infer_snapshot_id(published_at: str, source_commit: str) -> str:
    published_date = published_at.split("T", 1)[0]
    return f"{published_date}-{source_commit[:7]}"


def _deterministic_zip_write(
    source_repo_dir: Path,
    include_dirs: tuple[Path, ...],
    output_zip_path: Path,
) -> None:
    output_zip_path.parent.mkdir(parents=True, exist_ok=True)
    seen_paths: set[Path] = set()
    with zipfile.ZipFile(output_zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for include_dir in include_dirs:
            absolute_dir = source_repo_dir / include_dir
            if not absolute_dir.exists():
                raise FileNotFoundError(f"Archive source directory does not exist: {absolute_dir}")
            for file_path in sorted(path for path in absolute_dir.rglob("*") if path.is_file()):
                relative_path = file_path.relative_to(source_repo_dir)
                if relative_path in seen_paths:
                    continue
                seen_paths.add(relative_path)
                zip_info = zipfile.ZipInfo(relative_path.as_posix(), date_time=_ZIP_TIMESTAMP)
                zip_info.compress_type = zipfile.ZIP_DEFLATED
                zip_info.external_attr = 0o644 << 16
                archive.writestr(zip_info, file_path.read_bytes())


def _problem_dir(problem_type: ProblemType) -> Path:
    return Path("benchmarks") / problem_type.value


def _family_dir(problem_type: ProblemType, benchmark_name: BenchmarkName) -> Path:
    return _problem_dir(problem_type) / benchmark_name.value


def _build_archive_requests(source_repo_dir: Path, snapshot_id: str) -> list[_ArchiveRequest]:
    benchmarks_root = source_repo_dir / "benchmarks"
    discovered = discover_benchmark_instances(benchmarks_root=benchmarks_root)
    if not discovered:
        raise FileNotFoundError(f"No benchmark instances found under {benchmarks_root}")

    problem_types = sorted({item.problem_type for item in discovered}, key=lambda item: item.value)
    family_pairs = sorted(
        {(item.problem_type, BenchmarkName(item.benchmark_name)) for item in discovered},
        key=lambda pair: (pair[0].value, pair[1].value),
    )
    family_counts = Counter(BenchmarkName(item.benchmark_name) for item in discovered)
    multi_problem_families = sorted(
        {
            benchmark_name
            for benchmark_name in family_counts
            if len({item.problem_type for item in discovered if item.benchmark_name == benchmark_name.value}) > 1
        },
        key=lambda item: item.value,
    )

    requests: list[_ArchiveRequest] = []
    for problem_type in problem_types:
        requests.append(
            _ArchiveRequest(
                scope=ReleaseArchiveScope.PROBLEM,
                filename=f"{problem_type.value}-snapshot-{snapshot_id}.zip",
                archive_root=_problem_dir(problem_type).as_posix(),
                include_dirs=(_problem_dir(problem_type),),
                problem_type=problem_type,
            )
        )

    for problem_type, benchmark_name in family_pairs:
        requests.append(
            _ArchiveRequest(
                scope=ReleaseArchiveScope.PROBLEM_FAMILY,
                filename=f"{problem_type.value}-{benchmark_name.value}-snapshot-{snapshot_id}.zip",
                archive_root=_family_dir(problem_type, benchmark_name).as_posix(),
                include_dirs=(_family_dir(problem_type, benchmark_name),),
                problem_type=problem_type,
                benchmark_name=benchmark_name,
            )
        )

    for benchmark_name in multi_problem_families:
        include_dirs = tuple(
            _family_dir(problem_type, benchmark_name)
            for problem_type in problem_types
            if (source_repo_dir / _family_dir(problem_type, benchmark_name)).exists()
        )
        requests.append(
            _ArchiveRequest(
                scope=ReleaseArchiveScope.FAMILY,
                filename=f"{benchmark_name.value}-snapshot-{snapshot_id}.zip",
                archive_root="benchmarks",
                include_dirs=include_dirs,
                benchmark_name=benchmark_name,
            )
        )

    return requests


def _validate_release_asset_size(filename: str, size_bytes: int) -> None:
    if size_bytes >= GITHUB_RELEASE_ASSET_MAX_SIZE_BYTES:
        raise ValueError(
            f"Release asset {filename} is {size_bytes} bytes, which reaches or exceeds GitHub's "
            f"2 GiB per-asset limit for Releases. See {GITHUB_RELEASES_DOCS_URL}"
        )
    if size_bytes >= GITHUB_RELEASE_ASSET_WARNING_SIZE_BYTES:
        warnings.warn(
            f"Release asset {filename} is {size_bytes} bytes, which exceeds the 1.5 GiB warning threshold "
            f"and is getting close to GitHub's 2 GiB per-asset Releases limit. "
            f"See {GITHUB_RELEASES_DOCS_URL}",
            stacklevel=2,
        )


def generate_release_artifacts(
    source_repo_dir: str | Path,
    output_dir: str | Path,
    *,
    source_commit: str,
    published_at: str | None = None,
    snapshot_id: str | None = None,
    source_branch: str | None = None,
    release_tag: str | None = None,
    manifest_filename: str = DEFAULT_MANIFEST_FILENAME,
    download_base_url: str | None = None,
) -> ReleaseArtifactGenerationSummary:
    source_repo = Path(source_repo_dir)
    output_root = Path(output_dir)
    published_at_value = published_at or _now_utc_iso()
    snapshot_id_value = snapshot_id or _infer_snapshot_id(published_at_value, source_commit)
    archive_requests = _build_archive_requests(source_repo, snapshot_id_value)

    assets: list[ReleaseArchiveAsset] = []
    archive_paths: list[Path] = []

    for request in archive_requests:
        output_zip_path = output_root / request.filename
        _deterministic_zip_write(source_repo, request.include_dirs, output_zip_path)
        archive_paths.append(output_zip_path)
        size_bytes = output_zip_path.stat().st_size
        _validate_release_asset_size(request.filename, size_bytes)

        if download_base_url is None:
            download_url = request.filename
        else:
            download_url = f"{download_base_url.rstrip('/')}/{request.filename}"

        assets.append(
            ReleaseArchiveAsset(
                scope=request.scope,
                filename=request.filename,
                download_url=download_url,
                problem_type=request.problem_type,
                benchmark_name=request.benchmark_name,
                checksum_sha256=compute_sha256(output_zip_path),
                size_bytes=size_bytes,
                archive_root=request.archive_root,
            )
        )

    manifest = ReleaseArchiveManifest(
        snapshot_id=snapshot_id_value,
        published_at=published_at_value,
        source_commit=source_commit,
        source_branch=source_branch,
        release_tag=release_tag,
        assets=assets,
    )
    manifest_path = output_root / manifest_filename
    save_json_to_file(manifest.model_dump(mode="json"), manifest_path, sort_keys=True)

    return ReleaseArtifactGenerationSummary(
        snapshot_id=snapshot_id_value,
        published_at=published_at_value,
        source_commit=source_commit,
        output_dir=output_root.as_posix(),
        manifest_path=manifest_path.as_posix(),
        archive_count=len(archive_paths),
        archives=[path.as_posix() for path in archive_paths],
    )
