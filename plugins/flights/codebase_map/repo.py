"""The git questions the map asks: the repository's top level, its HEAD commit, the tracked files it reads; and the read of a tracked front door."""

from __future__ import annotations

import os

from .command import Unavailable, run

# Path components whose folders are never part of the map: hidden folders, vendored and fixture trees.
SKIPPED_COMPONENTS = frozenset({"vendor", "node_modules", "testdata"})


def _git_env(env: dict[str, str]) -> dict[str, str]:
    # git's messages are read below; the C locale keeps them untranslated.
    return {**env, "LC_ALL": "C"}


def toplevel(cwd: str, env: dict[str, str], timeout: float) -> str | None:
    """The real path of the work tree holding cwd; None when cwd is in no git repository."""
    result = run(["git", "rev-parse", "--show-toplevel"], cwd, _git_env(env), timeout)
    if result.code == 128 and "not a git repository" in result.stderr:
        return None
    if result.code != 0:
        raise Unavailable(f"git rev-parse --show-toplevel failed (exit {result.code}): {result.last_error_line()}")
    return os.path.realpath(result.stdout.strip())


def head(top: str, env: dict[str, str], timeout: float) -> str:
    """The commit HEAD names: the cache key."""
    result = run(["git", "rev-parse", "--verify", "-q", "HEAD"], top, _git_env(env), timeout)
    if result.code == 1 and not result.stdout.strip():
        raise Unavailable("the repository has no commit yet, and the map is kept per commit")
    if result.code != 0:
        raise Unavailable(f"git rev-parse HEAD failed (exit {result.code}): {result.last_error_line()}")
    return result.stdout.strip()


def skipped(path: str) -> bool:
    """True for a path inside a hidden, vendored or fixture folder."""
    parts = path.split("/")[:-1]
    return any(part.startswith(".") or part in SKIPPED_COMPONENTS for part in parts)


def tracked_files(top: str, env: dict[str, str], timeout: float) -> list[str]:
    """Every tracked file the map may read, relative to top, outside skipped folders."""
    result = run(["git", "ls-files", "-z"], top, _git_env(env), timeout)
    if result.code != 0:
        raise Unavailable(f"git ls-files failed (exit {result.code}): {result.last_error_line()}")
    return [path for path in result.stdout.split("\0") if path and not skipped(path)]


def front_door(top: str, path: str) -> bytes | None:
    """A tracked front door's bytes; None when the work tree no longer has it. OSError when it is no regular file inside
    top: a tracked symlink to a FIFO or a device would block or never end the read, and one leaving top is no package doc."""
    full = os.path.join(top, path)
    if not os.path.lexists(full):
        return None
    real = os.path.realpath(full)
    if os.path.commonpath([real, top]) != top:
        raise OSError(f"{path} points outside the repository")
    if not os.path.isfile(real):
        raise OSError(f"{path} is not a regular file")
    with open(real, "rb") as handle:
        return handle.read()
