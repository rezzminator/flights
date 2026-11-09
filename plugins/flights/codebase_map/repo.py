"""The git questions the map asks: the repository's top level, its HEAD commit, and the paths it tracks; and, for a
linked worktree, its base and the paths it changed since."""

from __future__ import annotations

import os

from .command import Unavailable, run


def _git_env(env: dict[str, str]) -> dict[str, str]:
    # git's messages are read below; the C locale keeps them untranslated. No optional lock: a read never holds the
    # index lock against the session's own git.
    return {**env, "LC_ALL": "C", "GIT_OPTIONAL_LOCKS": "0"}


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
    return _lines(["git", "ls-files"], top, env, timeout)


def _lines(argv: list[str], top: str, env: dict[str, str], timeout: float, end: str = "\n") -> list[str]:
    """The non-empty lines git prints for argv, each ended by end, run in top; a failure is an Unavailable naming the
    command."""
    result = run(argv, top, _git_env(env), timeout)
    if result.code != 0:
        raise Unavailable(f"git {' '.join(argv[1:3])} failed (exit {result.code}): {result.last_error_line()}")
    return [line for line in result.stdout.split(end) if line]


def linked_worktree(top: str, env: dict[str, str], timeout: float) -> bool:
    """Whether top is a linked worktree: its git directory is not the repository's common one."""
    dirs = _lines(["git", "rev-parse", "--git-dir", "--git-common-dir"], top, env, timeout)
    if len(dirs) != 2:
        raise Unavailable(f"git rev-parse --git-dir --git-common-dir printed {len(dirs)} lines, not 2")
    git_dir, common_dir = (os.path.realpath(os.path.join(top, line)) for line in dirs)
    return git_dir != common_dir


def main_worktree_head(top: str, env: dict[str, str], timeout: float) -> str:
    """The commit the main worktree's HEAD names: the first entry `git worktree list --porcelain` prints."""
    first: list[str] = []
    for line in _lines(["git", "worktree", "list", "--porcelain"], top, env, timeout):
        if line.startswith("worktree ") and first:
            break
        first.append(line)
    for line in first:
        if line.startswith("HEAD "):
            return line[len("HEAD "):]
    raise Unavailable("git worktree list names no HEAD for the main worktree (a bare repository has none)")


def merge_base(top: str, other: str, env: dict[str, str], timeout: float) -> str:
    """The best common ancestor of HEAD and other."""
    result = run(["git", "merge-base", "HEAD", other], top, _git_env(env), timeout)
    if result.code == 1 and not result.stdout.strip():
        raise Unavailable(f"HEAD and the main worktree's {other[:12]} share no commit")
    if result.code != 0:
        raise Unavailable(f"git merge-base failed (exit {result.code}): {result.last_error_line()}")
    return result.stdout.strip()


def changed_paths(top: str, base: str, env: dict[str, str], timeout: float) -> list[str]:
    """The tracked paths whose work tree content differs from base, committed or not, unquoted: NUL-ended, so a name git
    would quote still names its own folder."""
    return _lines(["git", "diff", "--name-only", "--no-renames", "-z", base], top, env, timeout, "\0")


def untracked_paths(top: str, env: dict[str, str], timeout: float) -> list[str]:
    """The untracked paths git does not ignore, unquoted as changed_paths prints them."""
    return _lines(["git", "ls-files", "--others", "--exclude-standard", "-z"], top, env, timeout, "\0")
