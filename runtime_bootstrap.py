"""Runtime bootstrap helpers for local entrypoints."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _is_site_packages(entry: str) -> bool:
    resolved = Path(entry).resolve()
    return "site-packages" in resolved.parts or "dist-packages" in resolved.parts


def _is_repo_root_entry(entry: str, *, repo_root: Path, cwd: Path) -> bool:
    target = cwd if entry == "" else Path(entry).resolve()
    return target == repo_root


def _reorder_repo_root_after_site_packages(
    paths: list[str],
    *,
    repo_root: Path,
    cwd: Path,
) -> list[str]:
    repo_entries = [
        entry for entry in paths if _is_repo_root_entry(entry, repo_root=repo_root, cwd=cwd)
    ]
    if not repo_entries:
        return paths

    remaining = [
        entry for entry in paths if not _is_repo_root_entry(entry, repo_root=repo_root, cwd=cwd)
    ]
    insert_at = max(
        (index for index, entry in enumerate(remaining) if _is_site_packages(entry)),
        default=-1,
    )
    if insert_at < 0:
        return paths
    return remaining[: insert_at + 1] + repo_entries + remaining[insert_at + 1 :]


def prefer_installed_packages() -> None:
    repo_root = Path(__file__).resolve().parent
    cwd = Path(os.getcwd()).resolve()
    sys.path[:] = _reorder_repo_root_after_site_packages(
        list(sys.path),
        repo_root=repo_root,
        cwd=cwd,
    )


__all__ = ["prefer_installed_packages", "_reorder_repo_root_after_site_packages"]
