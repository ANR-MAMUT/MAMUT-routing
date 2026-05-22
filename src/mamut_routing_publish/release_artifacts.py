from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
from typing import BinaryIO
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
)


_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
DEFAULT_RELEASE_ARCHIVE_COMPRESS_LEVEL = 9
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


@dataclass(frozen=True)
class _ArchiveBuildResult:
    request: _ArchiveRequest
    path: Path
    checksum_sha256: str
    size_bytes: int


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


class _HashingBinaryWriter:
    def __init__(self, raw: BinaryIO) -> None:
        self._raw = raw
        self._digest = hashlib.sha256()
        self._bytes_written = 0

    def write(self, data: bytes) -> int:
        self._digest.update(data)
        bytes_written = self._raw.write(data)
        self._bytes_written += bytes_written
        return bytes_written

    def tell(self) -> int:
        return self._bytes_written

    def flush(self) -> None:
        self._raw.flush()

    def writable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return False

    def hexdigest(self) -> str:
        return self._digest.hexdigest()


def _deterministic_zip_write(
    source_repo_dir: Path,
    include_dirs: tuple[Path, ...],
    output_zip_path: Path,
    *,
    compresslevel: int,
) -> tuple[str, int]:
    output_zip_path.parent.mkdir(parents=True, exist_ok=True)
    seen_paths: set[Path] = set()
    with output_zip_path.open("wb") as raw_output:
        hashing_output = _HashingBinaryWriter(raw_output)
        with zipfile.ZipFile(
            hashing_output,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=compresslevel,
        ) as archive:
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
        hashing_output.flush()
        return hashing_output.hexdigest(), hashing_output.tell()


def _problem_dir(problem_type: ProblemType) -> Path:
    return Path("benchmarks") / problem_type.value


def _family_dir(problem_type: ProblemType, benchmark_name: BenchmarkName) -> Path:
    return _problem_dir(problem_type) / benchmark_name.value


def _build_archive_requests(source_repo_dir: Path, snapshot_id: str) -> list[_ArchiveRequest]:
    benchmarks_root = source_repo_dir / "benchmarks"
    discovered = discover_benchmark_instances(benchmarks_root=benchmarks_root)
    if not discovered:
        raise FileNotFoundError(f"No benchmark instances found under {benchmarks_root}")

    family_pairs = sorted(
        {(item.problem_type, BenchmarkName(item.benchmark_name)) for item in discovered},
        key=lambda pair: (pair[0].value, pair[1].value),
    )

    requests: list[_ArchiveRequest] = []
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

    return requests


def _resolve_release_archive_jobs(jobs: int | None, archive_count: int) -> int:
    if archive_count < 1:
        return 1
    if jobs is not None:
        if jobs < 1:
            raise ValueError(f"jobs must be >= 1, got {jobs}")
        return min(jobs, archive_count)
    cpu_count = os.cpu_count() or 1
    return min(max(1, cpu_count - 2), archive_count)


def _validate_compresslevel(compresslevel: int) -> None:
    if compresslevel < 0 or compresslevel > 9:
        raise ValueError(f"compresslevel must be between 0 and 9, got {compresslevel}")


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


def _build_archive(
    source_repo: Path,
    output_root: Path,
    request: _ArchiveRequest,
    compresslevel: int,
) -> _ArchiveBuildResult:
    output_zip_path = output_root / request.filename
    checksum_sha256, size_bytes = _deterministic_zip_write(
        source_repo,
        request.include_dirs,
        output_zip_path,
        compresslevel=compresslevel,
    )
    return _ArchiveBuildResult(
        request=request,
        path=output_zip_path,
        checksum_sha256=checksum_sha256,
        size_bytes=size_bytes,
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
    jobs: int | None = None,
    compresslevel: int = DEFAULT_RELEASE_ARCHIVE_COMPRESS_LEVEL,
) -> ReleaseArtifactGenerationSummary:
    _validate_compresslevel(compresslevel)
    source_repo = Path(source_repo_dir)
    output_root = Path(output_dir)
    published_at_value = published_at or _now_utc_iso()
    snapshot_id_value = snapshot_id or _infer_snapshot_id(published_at_value, source_commit)
    archive_requests = _build_archive_requests(source_repo, snapshot_id_value)
    resolved_jobs = _resolve_release_archive_jobs(jobs, len(archive_requests))

    assets: list[ReleaseArchiveAsset] = []
    archive_paths: list[Path] = []

    if resolved_jobs == 1:
        build_results = [
            _build_archive(source_repo, output_root, request, compresslevel)
            for request in archive_requests
        ]
    else:
        with ProcessPoolExecutor(max_workers=resolved_jobs) as executor:
            build_results = list(
                executor.map(
                    _build_archive,
                    [source_repo] * len(archive_requests),
                    [output_root] * len(archive_requests),
                    archive_requests,
                    [compresslevel] * len(archive_requests),
                )
            )

    for result in build_results:
        request = result.request
        archive_paths.append(result.path)
        _validate_release_asset_size(request.filename, result.size_bytes)

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
                checksum_sha256=result.checksum_sha256,
                size_bytes=result.size_bytes,
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
