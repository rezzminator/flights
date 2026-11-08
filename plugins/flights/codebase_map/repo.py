"""The git questions the map asks: the repository's top level, its HEAD commit, and the paths it lists."""

from __future__ import annotations

import os

from .command import Unavailable, run


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


def listed_paths(top: str, env: dict[str, str], timeout: float) -> list[tuple[str, bool]]:
    """(path relative to top, whether it is a folder) for every path git lists: tracked files and untracked ones not
    ignored, each present in the work tree. git lists a submodule (a gitlink) and an untracked nested repository as one
    path: the work tree holds a folder there, so it reads as a folder."""
    result = run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], top, _git_env(env), timeout)
    if result.code != 0:
        raise Unavailable(f"git ls-files failed (exit {result.code}): {result.last_error_line()}")
    listed = []
    for path in result.stdout.split("\0"):
        if not path:
            continue
        # An untracked nested repository is listed with a trailing /.
        bare = path.rstrip("/")
        full = os.path.join(top, bare)
        if not os.path.lexists(full):
            continue  # a tracked file the work tree no longer has
        listed.append((bare, path.endswith("/") or (os.path.isdir(full) and not os.path.islink(full))))
    return listed
