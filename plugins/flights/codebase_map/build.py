"""A repository's map entries: every front-door reader over its tracked files, one entry per folder."""

from __future__ import annotations

from . import comment_doors, go_packages, py_packages, repo

# A background build's own bound for each git or go command it runs.
BUILD_TIMEOUT = 120.0


def entries(top: str, env: dict[str, str]) -> list[tuple[str, str]]:
    """(folder, synopsis) sorted by folder; a folder two readers claim keeps the first: Go, Python, then comment doors."""
    files = repo.tracked_files(top, env, BUILD_TIMEOUT)
    found: dict[str, str] = {}
    readers = (
        go_packages.entries(top, files, env, BUILD_TIMEOUT),
        py_packages.entries(top, files),
        comment_doors.entries(top, files),
    )
    for reader in readers:
        for folder, synopsis in reader:
            found.setdefault(folder, synopsis)
    return sorted(found.items())
