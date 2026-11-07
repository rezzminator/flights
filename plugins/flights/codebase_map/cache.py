"""The per-commit cache: a repository's entries keyed by its top level and HEAD, under
${XDG_CACHE_HOME:-$HOME/.cache}/flights/map/. A hit runs no build. A miss starts the build as a
detached background process and waits for it up to the hook's deadline; past it, the hook says the
map is still building and the build finishes into the cache for the next start.
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

# Bumped when the entry format or what the readers report changes, so an older cache is never read.
FORMAT = 1
# How often a waiting hook looks for the build's result.
POLL_SECONDS = 0.05


def cache_root(env: dict[str, str]) -> str:
    """${XDG_CACHE_HOME:-$HOME/.cache}/flights, holding the map cache (map/) and the read heat (heat/)."""
    base = env.get("XDG_CACHE_HOME") or (os.path.join(env["HOME"], ".cache") if env.get("HOME") else "")
    if not base:
        raise Unavailable("neither XDG_CACHE_HOME nor HOME is set, so there is no cache directory")
    return os.path.join(base, "flights")


def cache_dir(env: dict[str, str]) -> str:
    return os.path.join(cache_root(env), "map")


def cache_path(env: dict[str, str], top: str, head: str) -> str:
    key = hashlib.sha256(f"{FORMAT}\0{top}\0{head}".encode()).hexdigest()[:40]
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


def load(path: str, top: str, head: str) -> list[tuple[str, str]] | None:
    """The cached entries, or None when there is no usable entry for this top level and HEAD."""
    try:
        with open(path, encoding="utf-8") as handle:
            stored = json.load(handle)
    except (FileNotFoundError, ValueError):
        return None
    if not isinstance(stored, dict) or stored.get("toplevel") != top or stored.get("head") != head:
        return None
    try:
        return [(folder, synopsis) for folder, synopsis in stored["entries"]]
    except (KeyError, TypeError, ValueError):
        return None  # a file of another shape is no usable entry: the miss rebuilds it in place


def run_build(top: str, head: str, env: dict[str, str], log: PluginLog) -> None:
    """The background build: the entries into the cache, or the reason it failed into the .error file beside it."""
    path = cache_path(env, top, head)
    try:
        # Imported here: only the background build reads front doors, and the Read recorder's every call skips the readers.
        from . import build

        started = time.monotonic()
        entries = build.entries(top, env)
        # Logged before the cache file lands, so the row precedes every hit it makes possible.
        log.record("debug", "map-built", f"built the map of {top} at {head[:12]}", "cache.py#run_build", None,
                   {"toplevel": top, "head": head, "folders": len(entries), "seconds": round(time.monotonic() - started, 3)})
        write_file(path, json.dumps({"toplevel": top, "head": head, "entries": entries}))
    except Exception as error:
        reason = str(error) if isinstance(error, Unavailable) else f"building the map failed: {type(error).__name__}: {error}"
        # Logged here: a build failing after its hook answered has no other reader.
        log.record("error", "map-build-failed", reason, "cache.py#run_build", None, {"toplevel": top, "head": head})
        write_file(_error_path(path), reason)


def _reap(build_process: subprocess.Popen, deadline: float) -> None:
    # Its result is written, so it is exiting; a build that lingers past the hook's deadline is left to finish on its own.
    try:
        build_process.wait(timeout=max(0.0, deadline - time.monotonic()))
        STARTED.remove(build_process)
    except subprocess.TimeoutExpired:
        pass


def entries(top: str, head: str, env: dict[str, str], deadline: float, log: PluginLog) -> list[tuple[str, str]]:
    """The entries for top at head: from the cache, else built in the background and waited for until deadline."""
    path = cache_path(env, top, head)
    hit = load(path, top, head)
    detail = {"toplevel": top, "head": head, "path": path}
    if hit is not None:
        log.record("debug", "cache-hit", f"map of {top} at {head[:12]} read from the cache", "cache.py#entries", None, detail)
        return hit
    log.record("debug", "cache-miss", f"map of {top} at {head[:12]} not cached; building it", "cache.py#entries", None, detail)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        os.unlink(_error_path(path))
    except FileNotFoundError:
        pass
    except OSError as error:
        raise Unavailable(f"the cache directory {os.path.dirname(path)} is unusable: {error}") from None
    build_process = start_background(["build", top, head], env, "map build")
    while True:
        hit = load(path, top, head)
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
