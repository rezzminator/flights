"""The per-commit cache: a repository's map, as its folder lines, keyed by HEAD alone under
${XDG_CACHE_HOME:-$HOME/.cache}/flights/map/, so every work tree at one commit reads one build. A hit runs no build. A
miss starts the build as a detached background process and waits for it up to the hook's deadline; past it, the hook
says the map is still building and the build finishes into the cache for the next start. Each build that lands prunes
the cache files older than a week.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import time

from .command import STARTED, Unavailable, start_background
from .plugin_log import PluginLog

# Bumped when the entry format changes, so an older cache is never read: 1 was 0.2.0's (folder, synopsis) pairs, 2 the
# names-only tree's (name, children), 3 ponytail's map text per top level and HEAD, 4 its folder lines per HEAD. It is
# part of the key and stored in the entry, which load checks.
FORMAT = 4
# How often a waiting hook looks for the build's result.
POLL_SECONDS = 0.05
# A cache file last written longer ago than this goes at the next build: an entry of a commit long left or of an older
# format, a failure's reason, a temp file a killed build left behind.
PRUNE_SECONDS = 7 * 24 * 3600


def cache_dir(env: dict[str, str]) -> str:
    """${XDG_CACHE_HOME:-$HOME/.cache}/flights/map, holding the map cache."""
    base = env.get("XDG_CACHE_HOME") or (os.path.join(env["HOME"], ".cache") if env.get("HOME") else "")
    if not base:
        raise Unavailable("neither XDG_CACHE_HOME nor HOME is set, so there is no cache directory")
    return os.path.join(base, "flights", "map")


def cache_path(env: dict[str, str], head: str) -> str:
    # No top level in the key: a build reads its own work tree, so another tree at the same commit can read a dirty
    # tree's names rather than the commit's, the price of one build per commit.
    key = hashlib.sha256(f"{FORMAT}\0{head}".encode()).hexdigest()[:40]
    return os.path.join(cache_dir(env), f"{key}.json")


def _error_path(path: str) -> str:
    return path[: -len(".json")] + ".error"


def write_file(path: str, text: str) -> None:
    # Written beside its final name and renamed into place, so a reader never sees half a file.
    handle, temp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".building-")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as out:
            out.write(text)
        os.replace(temp, path)
    except BaseException:
        os.unlink(temp)
        raise


def load(path: str, head: str) -> list[tuple[str, str]] | None:
    """The cached folder lines, or None when there is no usable entry for this format and HEAD; the entry's toplevel
    records which tree built it and is not checked."""
    try:
        with open(path, encoding="utf-8") as handle:
            stored = json.load(handle)
    except (FileNotFoundError, ValueError):
        return None
    if not isinstance(stored, dict) or (stored.get("format"), stored.get("head")) != (FORMAT, head):
        return None
    folders = stored.get("folders")
    # A file of another shape is no usable entry: the miss rebuilds it in place.
    if not isinstance(folders, list) or not all(
            isinstance(pair, list) and len(pair) == 2 and all(isinstance(part, str) for part in pair) for pair in folders):
        return None
    return [(folder, line) for folder, line in folders]


def run_build(top: str, head: str, env: dict[str, str], log: PluginLog) -> None:
    """The background build: the folder lines into the cache, then the cache pruned; or the reason it failed into the
    .error file beside it."""
    path = cache_path(env, head)
    try:
        # Imported here: only the background build lists the repository's paths and reads its files.
        from . import build

        started = time.monotonic()
        lines = build.map_lines(top, env)
        # Logged before the cache file lands, so the row precedes every hit it makes possible.
        log.record("debug", "map-built", f"built the map of {top} at {head[:12]}", "cache.py#run_build", None,
                   {"toplevel": top, "head": head, "folders": len(lines), "seconds": round(time.monotonic() - started, 3)})
        write_file(path, json.dumps({"format": FORMAT, "toplevel": top, "head": head, "folders": lines}))
    except Exception as error:
        reason = str(error) if isinstance(error, Unavailable) else f"building the map failed: {type(error).__name__}: {error}"
        # Logged here: a build failing after its hook answered has no other reader.
        log.record("error", "map-build-failed", reason, "cache.py#run_build", None, {"toplevel": top, "head": head})
        write_file(_error_path(path), reason)
        return
    prune(os.path.dirname(path), time.time(), log)


def prune(directory: str, now: float, log: PluginLog) -> None:
    """Remove directory's cache files (*.json, *.error, .building-*) last written more than PRUNE_SECONDS before now. A
    failure is a warning row, never raised: the build it follows has landed."""
    removed = 0
    try:
        with os.scandir(directory) as entries:
            for entry in entries:
                if not (entry.name.endswith((".json", ".error")) or entry.name.startswith(".building-")):
                    continue
                try:
                    if entry.is_file(follow_symlinks=False) and now - entry.stat(follow_symlinks=False).st_mtime > PRUNE_SECONDS:
                        os.unlink(entry.path)
                        removed += 1
                except FileNotFoundError:
                    pass  # another build's prune took it first
    except OSError as error:
        log.record("warning", "cache-prune-failed", f"pruning the map cache {directory} failed: {error}", "cache.py#prune",
                   None, {"directory": directory, "removed": removed})
        return
    if removed:
        log.record("debug", "cache-pruned", f"removed {removed} map cache files older than 7 days from {directory}",
                   "cache.py#prune", None, {"directory": directory, "removed": removed})


def _reap(build_process: subprocess.Popen, deadline: float) -> None:
    # Its result is written, so it is exiting; a build that lingers past the hook's deadline is left to finish on its own.
    try:
        build_process.wait(timeout=max(0.0, deadline - time.monotonic()))
        STARTED.remove(build_process)
    except subprocess.TimeoutExpired:
        pass


def map_for(top: str, head: str, env: dict[str, str], deadline: float, log: PluginLog) -> list[tuple[str, str]]:
    """The folder lines at head, [] when no file names anything: from the cache, whichever tree built it, else built from
    top in the background and waited for until deadline."""
    path = cache_path(env, head)
    hit = load(path, head)
    detail = {"toplevel": top, "head": head, "path": path}
    if hit is not None:
        log.record("debug", "cache-hit", f"map of {top} at {head[:12]} read from the cache", "cache.py#map_for", None, detail)
        return hit
    log.record("debug", "cache-miss", f"map of {top} at {head[:12]} not cached; building it", "cache.py#map_for", None, detail)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        os.unlink(_error_path(path))
    except FileNotFoundError:
        pass
    except OSError as error:
        raise Unavailable(f"the cache directory {os.path.dirname(path)} is unusable: {error}") from None
    build_process = start_background(["build", top, head], env, "map build")
    while True:
        hit = load(path, head)
        if hit is not None:
            _reap(build_process, deadline)
            return hit
        try:
            # Left in place: every hook waiting on this commit reads it; the next miss removes it before its build.
            with open(_error_path(path), encoding="utf-8") as handle:
                reason = handle.read()
        except FileNotFoundError:
            pass
        else:
            _reap(build_process, deadline)
            raise Unavailable(reason)
        if time.monotonic() >= deadline:
            raise Unavailable(
                f"the map for commit {head[:12]} is still building; it goes on in the background and is ready at the next start"
            )
        time.sleep(POLL_SECONDS)
