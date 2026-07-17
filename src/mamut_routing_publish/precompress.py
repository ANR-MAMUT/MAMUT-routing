"""Build-time precompression of the static site tree.

Writes ``.gz`` and ``.br`` sidecars next to compressible text assets so the
server can negotiate them per request (see ``server.py``) without any
on-the-fly compression. Files that are already gzip content (``*.gz``) are
never touched. Sidecars carry the source file's mtime, so a rebuilt source
invalidates its sidecars and unchanged ones are skipped incrementally.
"""

from __future__ import annotations

import gzip
import os
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import brotli

PRECOMPRESS_EXTENSIONS = frozenset({".html", ".css", ".js", ".json", ".svg", ".txt", ".xml"})
PRECOMPRESS_MIN_BYTES = 1024


@dataclass
class PrecompressSummary:
    written: int = 0
    skipped_fresh: int = 0
    considered: int = 0
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "written": self.written,
            "skipped_fresh": self.skipped_fresh,
            "considered": self.considered,
            "errors": len(self.errors),
        }


def _is_compressible(path: Path) -> bool:
    name = path.name
    if name.endswith((".gz", ".br")):
        return False
    return path.suffix.lower() in PRECOMPRESS_EXTENSIONS


def _sidecars_fresh(path: Path, source_mtime: float) -> bool:
    for suffix in (".gz", ".br"):
        sidecar = path.with_name(path.name + suffix)
        if not sidecar.is_file() or sidecar.stat().st_mtime < source_mtime:
            return False
    return True


def _compress_one(path_str: str) -> str | None:
    """Worker: write both sidecars for one file. Returns an error string or None."""
    path = Path(path_str)
    try:
        data = path.read_bytes()
        source_mtime = path.stat().st_mtime
        gz_target = path.with_name(path.name + ".gz")
        with gz_target.open("wb") as raw:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0) as compressed:
                compressed.write(data)
        os.utime(gz_target, (source_mtime, source_mtime))
        br_target = path.with_name(path.name + ".br")
        br_target.write_bytes(brotli.compress(data, quality=11))
        os.utime(br_target, (source_mtime, source_mtime))
        return None
    except OSError as error:
        return f"{path}: {error}"


def precompress_tree(root: Path, *, jobs: int | None = None) -> PrecompressSummary:
    summary = PrecompressSummary()
    pending: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or not _is_compressible(path):
            continue
        stat = path.stat()
        if stat.st_size < PRECOMPRESS_MIN_BYTES:
            continue
        summary.considered += 1
        if _sidecars_fresh(path, stat.st_mtime):
            summary.skipped_fresh += 1
            continue
        pending.append(str(path))

    if pending:
        workers = jobs or max(1, (os.cpu_count() or 4) - 2)
        with ProcessPoolExecutor(max_workers=workers) as pool:
            for error in pool.map(_compress_one, pending, chunksize=16):
                if error is None:
                    summary.written += 1
                else:
                    summary.errors.append(error)
    return summary
