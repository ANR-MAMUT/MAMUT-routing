"""Explicit publication roots for site builds.

Historically every build path hung off ``<repo>/dist``: the site output, the
build-time caches (``atf-cache``, ``route-geometry-cache``), and the
persistent history state all shared one tree. That breaks release-style
staging builds (``site build --site-output-dir <fresh-dir>``): cache writes
leaked through the active ``dist`` (a symlink to the live release on
deployments), the fresh release shipped without the caches the payloads
reference, and the history ledger reset to "initial snapshot" on every
deploy because each release directory starts empty.

This module names the roots explicitly:

- ``source_repo``: read-only build inputs (``benchmarks/``, ``instances_v2/``,
  committed assets).
- ``site_output``: the only tree a build writes published bytes into
  (default ``<source_repo>/dist``).
- ``state_dir``: persistent publication state that must survive fresh site
  outputs: the history ledger and per-snapshot inventories (default
  ``<source_repo>/publish-state``, git-ignored).

During a staging build the active ``<source_repo>/dist`` tree may be READ
(it seeds the staging caches via hardlinks) but never written.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

DEFAULT_STATE_DIR_NAME = "publish-state"


def _resolve_under(repo: Path, candidate: str | Path | None, default: Path) -> Path:
    if candidate is None:
        return default
    path = Path(candidate)
    return path if path.is_absolute() else repo / path


@dataclass(frozen=True)
class PublishRoots:
    source_repo: Path
    site_output: Path
    state_dir: Path

    @classmethod
    def resolve(
        cls,
        source_repo: str | Path,
        site_output_dir: str | Path | None = None,
        state_dir: str | Path | None = None,
    ) -> "PublishRoots":
        repo = Path(source_repo)
        return cls(
            source_repo=repo,
            site_output=_resolve_under(repo, site_output_dir, repo / "dist"),
            state_dir=_resolve_under(repo, state_dir, repo / DEFAULT_STATE_DIR_NAME),
        )

    @property
    def active_dist(self) -> Path:
        return self.source_repo / "dist"

    @property
    def in_place(self) -> bool:
        """True when the build writes the repo's own ``dist`` tree directly."""
        try:
            return self.site_output.resolve() == self.active_dist.resolve()
        except OSError:
            return self.site_output == self.active_dist

    @property
    def history_path(self) -> Path:
        return self.state_dir / "history.json"

    @property
    def snapshots_dir(self) -> Path:
        return self.state_dir / "snapshots"

    @property
    def atf_cache_dir(self) -> Path:
        """Cache dir the CURRENT build materializes into and reads from."""
        return self.site_output / "atf-cache"

    @property
    def route_geometry_publish_dir(self) -> Path:
        return self.site_output / "route-geometry-cache"


def migrate_legacy_state(roots: PublishRoots) -> bool:
    """Seed ``state_dir`` from the pre-roots layout (``<dist>/site/``) once.

    Earlier builds kept the history ledger and snapshot inventories inside
    the site output itself. Copy them into the persistent state dir the
    first time a build runs with an empty state dir, so accumulated history
    survives the layout change. Returns True when a migration ran.
    """
    if roots.history_path.exists():
        return False
    legacy_history = roots.active_dist / "site" / "history.json"
    if not legacy_history.is_file():
        return False
    roots.snapshots_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(legacy_history, roots.history_path)
    legacy_snapshots = roots.active_dist / "site" / "snapshots"
    if legacy_snapshots.is_dir():
        for path in sorted(legacy_snapshots.glob("*.inventory.json")):
            target = roots.snapshots_dir / path.name
            if not target.exists():
                shutil.copy2(path, target)
    return True


def hardlink_tree(source_dir: Path, target_dir: Path) -> int:
    """Mirror ``source_dir`` into ``target_dir`` via hardlinks (copy fallback).

    Existing target files are left untouched, so the operation is idempotent
    and safe over content-addressed caches. Returns the number of files
    linked or copied.
    """
    if not source_dir.is_dir():
        return 0
    linked = 0
    for path in sorted(source_dir.rglob("*")):
        if not path.is_file():
            continue
        target = target_dir / path.relative_to(source_dir)
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.link(path, target)
        except OSError:
            shutil.copy2(path, target)
        linked += 1
    return linked
