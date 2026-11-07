"""The read heat: per repository, how often each file is read, recent reads weighing more. Each Read a loop makes adds
one to its file's decayed score; the map orders its package folders by the sum over the files each one holds.

The store is one JSON file per repository top level under ${XDG_CACHE_HOME:-$HOME/.cache}/flights/heat/, kept across
commits. Writers update it under an flock and rename it into place, so a reader needs no lock.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from typing import Callable

from . import cache, repo
from .command import Unavailable
from .plugin_log import PluginLog

# Bumped when the store's shape changes; a store of another format is rebuilt empty.
FORMAT = 1
# A read's weight halves every this many seconds.
HALF_LIFE_SECONDS = 14 * 86400
# A file whose decayed score falls below this is dropped at the next write.
PRUNE_BELOW = 0.01


def wall_clock() -> float:
    """The one read of wall-clock time for the heat: every score's age is measured against it."""
    return time.time()


@dataclass
class Store:
    created: float
    seeded: bool = False
    # Repository-relative file path -> [score at ts, ts].
    files: dict[str, list[float]] = field(default_factory=dict)
    # The tool use id of the Read whose recording created the store: its transcript stamp precedes created, so the seed
    # skips it rather than count it a second time.
    first_read: str = ""


def store_path(env: dict[str, str], top: str) -> str:
    key = hashlib.sha256(top.encode()).hexdigest()[:40]
    return os.path.join(cache.cache_root(env), "heat", f"{key}.json")


def decayed(score: float, ts: float, now: float) -> float:
    """score as of now: halved for every HALF_LIFE_SECONDS since ts; a ts in the future does not grow it."""
    return score * 0.5 ** (max(0.0, now - ts) / HALF_LIFE_SECONDS)


def relative(top: str, cwd: str, file_path: str) -> str | None:
    """file_path (absolute, or relative to cwd) relative to top; None when it resolves outside top, inside a work tree
    nested below top (a submodule, a linked worktree, a nested repository: that tree's file, not top's), or is no path."""
    try:
        real = os.path.realpath(os.path.join(cwd, file_path))
    except ValueError:
        return None  # an embedded NUL byte: no file of any repository
    if real == top or os.path.commonpath([real, top]) != top or repo.work_tree(os.path.dirname(real)) != top:
        return None
    return os.path.relpath(real, top)


def load(path: str, top: str, log: PluginLog) -> Store | None:
    """The store at path; None when there is none. An unusable one is logged and counts as none: the next write rebuilds
    it empty. OSError when it cannot be read."""
    try:
        with open(path, "rb") as handle:
            raw = handle.read()
    except FileNotFoundError:
        return None
    try:
        # Bytes: a store that is not UTF-8 fails inside this try, as unusable, never as a crash of every later Read.
        stored = json.loads(raw)
        if not isinstance(stored, dict) or stored.get("format") != FORMAT or stored.get("toplevel") != top:
            raise ValueError(f"not a format-{FORMAT} store of {top}")
        files = {str(rel): [float(score), float(ts)] for rel, (score, ts) in stored["files"].items()}
        return Store(float(stored["created"]), stored["seeded"] is True, files, str(stored.get("first_read", "")))
    except (ValueError, TypeError, KeyError, AttributeError) as error:
        log.record("warning", "heat-store-unusable", f"the read heat store {path} is unusable and is rebuilt empty: {error}",
                   "heat.py#load", None, {"path": path, "toplevel": top})
        return None


def update(path: str, top: str, now: float, log: PluginLog, change: Callable[[Store], None], first_read: str = "") -> Store:
    """Apply change to the store under its lock, prune what decayed below PRUNE_BELOW, and rename the result into place.
    first_read is the tool use id a store created here records."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path[: -len(".json")] + ".lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        store = load(path, top, log) or Store(created=now, first_read=first_read)
        change(store)
        store.files = {rel: kept for rel, kept in store.files.items() if decayed(kept[0], kept[1], now) >= PRUNE_BELOW}
        stored = {"format": FORMAT, "toplevel": top, "created": store.created, "seeded": store.seeded, "files": store.files}
        if store.first_read:
            stored["first_read"] = store.first_read
        cache.write_file(path, json.dumps(stored))
    return store


def add(store: Store, rel: str, score: float, now: float) -> None:
    """score more reads of rel as of now, on top of its earlier score decayed to now."""
    earlier, ts = store.files.get(rel, [0.0, now])
    store.files[rel] = [decayed(earlier, ts, now) + score, now]


def record_read(payload: dict, env: dict[str, str], log: PluginLog, now: float) -> None:
    """A PostToolUse Read payload: one more read of its file in the store of the session's repository. A file outside
    that repository, or a session in none, is no read of it and is passed over."""
    tool_input = payload.get("tool_input")
    file_path = tool_input.get("file_path") if isinstance(tool_input, dict) else None
    if payload.get("tool_name") != "Read":
        return
    if not isinstance(file_path, str) or not file_path:
        log.record("warning", "heat-read-unrecognized", "a Read's PostToolUse payload carries no tool_input.file_path",
                   "heat.py#record_read", payload.get("session_id"), {"toolInput": str(tool_input)[:500]})
        return
    cwd = payload.get("cwd") or os.getcwd()
    top = repo.work_tree(cwd)
    rel = None if top is None else relative(top, cwd, file_path)
    if rel is None:
        return
    try:
        update(store_path(env, top), top, now, log, lambda store: add(store, rel, 1.0, now), str(payload.get("tool_use_id") or ""))
    except (OSError, Unavailable) as error:
        log.record("error", "heat-record-failed", f"the read of {rel} in {top} was not recorded: {error}",
                   "heat.py#record_read", payload.get("session_id"), {"toplevel": top, "file": rel})


def current(top: str, env: dict[str, str], log: PluginLog) -> Store | None:
    """The store for top as the map reads it: None when there is none yet or it cannot be read (logged)."""
    try:
        return load(store_path(env, top), top, log)
    except (OSError, Unavailable) as error:
        log.record("error", "heat-unreadable", f"the read heat of {top} could not be read; the map is ordered without it: {error}",
                   "heat.py#current", None, {"toplevel": top})
        return None


def package_heat(folders: list[str], store: Store, now: float) -> dict[str, float]:
    """Each folder's heat: the decayed scores of the files whose longest enclosing folder among folders it is ("." the top)."""
    wanted = set(folders)
    heat: dict[str, float] = {}
    for rel, (score, ts) in store.files.items():
        folder = os.path.dirname(rel)
        while folder and folder not in wanted:
            folder = os.path.dirname(folder)
        folder = folder or "."
        if folder in wanted:
            heat[folder] = heat.get(folder, 0.0) + decayed(score, ts, now)
    return heat
