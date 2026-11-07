"""The read heat's one-time seed: a repository with no seeded store yet is seeded from this Claude config's own
transcripts of it, `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/projects/{slug}/**/*.jsonl`, counting each Read tool call of the
last WINDOW_SECONDS by its age. It runs as a detached background process the hook starts, within SEED_SECONDS.
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime

from . import heat
from .command import Unavailable, start_background
from .plugin_log import PluginLog

# Reads older than this are not counted.
WINDOW_SECONDS = 30 * 86400
# The seed's wall-clock budget; past it the seed stops, keeps what it counted and marks the store seeded.
SEED_SECONDS = 15.0
# A seed marker older than this belongs to a seed that died: the next start replaces it.
MARKER_STALE_SECONDS = 4 * SEED_SECONDS
# Claude Code names a project's transcript folder after its path: every character but [a-zA-Z0-9] becomes "-", and a
# name past SLUG_MAX characters is cut there and suffixed with a hash of the path.
SLUG_MAX = 200


def slug(path: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]", "-", path)


def _marker(env: dict[str, str], top: str) -> str:
    return heat.store_path(env, top)[: -len(".json")] + ".seeding"


def start(top: str, env: dict[str, str], log: PluginLog) -> None:
    """Start the background seed of top's store unless one is running; never fails the map, a failure is logged."""
    marker = _marker(env, top)
    try:
        os.makedirs(os.path.dirname(marker), exist_ok=True)
        try:
            if heat.wall_clock() - os.stat(marker).st_mtime < MARKER_STALE_SECONDS:
                return
            os.unlink(marker)
        except FileNotFoundError:
            pass
        os.close(os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600))
    except FileExistsError:
        return  # another hook started it between the look and the create
    except (OSError, Unavailable) as error:
        log.record("error", "heat-seed-not-started", f"the read heat seed of {top} could not start: {error}",
                   "seed.py#start", None, {"toplevel": top, "marker": marker})
        return
    try:
        start_background(["seed", top], env, "read heat seed")
    except Unavailable as error:
        log.record("error", "heat-seed-not-started", str(error), "seed.py#start", None, {"toplevel": top})
        try:
            os.unlink(marker)
        except OSError as unlink_error:
            # Left in place, the marker turns stale within MARKER_STALE_SECONDS and the next start replaces it.
            log.record("error", "heat-seed-marker", f"the seed marker of {top} could not be removed: {unlink_error}",
                       "seed.py#start", None, {"toplevel": top, "marker": marker})


def transcripts(env: dict[str, str], top: str, since: float) -> list[str]:
    """The transcripts of top and of the folders under it changed since since, newest first."""
    config = env.get("CLAUDE_CONFIG_DIR") or (os.path.join(env["HOME"], ".claude") if env.get("HOME") else "")
    if not config:
        return []
    projects = os.path.join(config, "projects")
    name = slug(top)
    try:
        folders = [entry for entry in os.listdir(projects) if entry == name or entry.startswith(name[:SLUG_MAX] + "-")]
    except FileNotFoundError:
        return []
    found = []
    for folder in folders:
        for root, _, names in os.walk(os.path.join(projects, folder)):
            for file_name in names:
                if file_name.endswith(".jsonl"):
                    path = os.path.join(root, file_name)
                    try:
                        mtime = os.stat(path).st_mtime
                    except FileNotFoundError:
                        continue  # removed while the folder was walked
                    if mtime >= since:
                        found.append((mtime, path))
    return [path for _, path in sorted(found, reverse=True)]


def _timestamp(text: object) -> float | None:
    try:
        # fromisoformat before Python 3.11 reads no "Z".
        return datetime.fromisoformat(str(text).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _reads(line: bytes, top: str) -> list[tuple[str, float, str]]:
    """(file relative to top, when, tool use id) for each Read tool call in one transcript line inside top."""
    try:
        record = json.loads(line)
    except ValueError:
        return []  # the torn last line of a live transcript
    message = record.get("message") if isinstance(record, dict) and record.get("type") == "assistant" else None
    content = message.get("content") if isinstance(message, dict) else None
    at = _timestamp(record.get("timestamp")) if isinstance(content, list) else None
    if at is None:
        return []
    found = []
    for block in content:
        if not isinstance(block, dict) or block.get("type") != "tool_use" or block.get("name") != "Read":
            continue
        tool_input = block.get("input")
        file_path = tool_input.get("file_path") if isinstance(tool_input, dict) else None
        rel = heat.relative(top, str(record.get("cwd") or top), file_path) if isinstance(file_path, str) else None
        if rel is not None:
            found.append((rel, at, str(block.get("id"))))
    return found


def scan(paths: list[str], top: str, since: float, before: float, now: float, deadline: float):
    """(each Read in [since, before) by tool use id: its file and weight as of now; transcripts read whole; cut short by
    deadline; the transcripts that could not be opened)."""
    counted: dict[str, tuple[str, float]] = {}
    unopened: list[str] = []
    for done, path in enumerate(paths):
        try:
            handle = open(path, "rb")
        except OSError as error:
            unopened.append(f"{path}: {error}")  # removed or unreadable since it was listed: the others still count
            continue
        with handle:
            for line in handle:
                if time.monotonic() >= deadline:
                    return counted, done, True, unopened
                if b'"Read"' not in line:
                    continue
                for rel, at, use_id in _reads(line, top):
                    # A tool call is counted once, even when two transcripts both carry it.
                    if since <= at < before and use_id not in counted:
                        counted[use_id] = (rel, heat.decayed(1.0, at, now))
    return counted, len(paths), False, unopened


def run(top: str, env: dict[str, str], log: PluginLog, now: float, deadline: float) -> None:
    """Seed top's store once: the Reads before it was created (all of them when it was not), merged under its lock."""
    started = time.monotonic()
    try:
        path = heat.store_path(env, top)
    except Unavailable as error:
        log.record("error", "heat-seed-failed", f"seeding the read heat of {top} failed: {error}", "seed.py#run", None,
                   {"toplevel": top})
        return
    marker = path[: -len(".json")] + ".seeding"
    try:
        existing = heat.load(path, top, log)
        paths = transcripts(env, top, now - WINDOW_SECONDS)
        counted, read, cut, unopened = scan(paths, top, now - WINDOW_SECONDS, existing.created if existing else now, now,
                                            deadline)
        if unopened:
            log.record("warning", "heat-seed-unopened", f"seeding the read heat of {top} passed over {len(unopened)}"
                       " transcripts it could not open", "seed.py#run", None, {"toplevel": top, "unopened": unopened[:20]})
        merged: list[bool] = []
        scores: dict[str, float] = {}

        def merge(store: heat.Store) -> None:
            if store.seeded:
                return  # another seed finished first; its counts already hold these reads
            for use_id, (rel, score) in counted.items():
                # The Read whose recording created the store is in it already, though its transcript stamp is earlier.
                if use_id != store.first_read:
                    scores[rel] = scores.get(rel, 0.0) + score
            for rel, score in scores.items():
                heat.add(store, rel, score, now)
            store.seeded = True
            merged.append(True)

        heat.update(path, top, now, log, merge)
        detail = {"toplevel": top, "transcripts": len(paths), "read": read, "files": len(scores),
                  "seconds": round(time.monotonic() - started, 3)}
        if not merged:
            log.record("debug", "heat-seed-dropped", f"the read heat of {top} was already seeded", "seed.py#run", None, detail)
        elif cut:
            log.record("debug", "heat-seed-cut", f"seeding the read heat of {top} stopped at its {SEED_SECONDS:g}s budget"
                       f" after {read} of {len(paths)} transcripts", "seed.py#run", None, detail)
        else:
            log.record("debug", "heat-seeded", f"seeded the read heat of {top} from {len(paths)} transcripts",
                       "seed.py#run", None, detail)
    except (OSError, Unavailable) as error:
        log.record("error", "heat-seed-failed", f"seeding the read heat of {top} failed: {error}", "seed.py#run", None,
                   {"toplevel": top})
    finally:
        try:
            os.unlink(marker)
        except FileNotFoundError:
            pass
        except OSError as error:
            log.record("error", "heat-seed-marker", f"the seed marker of {top} could not be removed: {error}",
                       "seed.py#run", None, {"toplevel": top})
