"""The git questions the map asks: the repository's top level, its HEAD commit, and the paths it tracks."""

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


def tracked_paths(top: str, env: dict[str, str], timeout: float) -> list[str]:
    """The lines `git ls-files` prints, the paths git tracks relative to top, quoted as git quotes them; the work tree may
    no longer hold some."""
    result = run(["git", "ls-files"], top, _git_env(env), timeout)
    if result.code != 0:
        raise Unavailable(f"git ls-files failed (exit {result.code}): {result.last_error_line()}")
    return [line for line in result.stdout.split("\n") if line]
