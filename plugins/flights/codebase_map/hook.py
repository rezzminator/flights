"""The hook payload in, the hook JSON out: which loops receive the map, and the map of the repository holding the
loop's folder; in a linked worktree, of the folders it changed."""

from __future__ import annotations

import json
import os
import time

from . import cache, repo
from .command import UNAVAILABLE, Unavailable
from .plugin_log import PluginLog

# The sub-agent types that receive the map at their start, matched exactly; every other sub-agent receives nothing.
MAP_AGENT_TYPES = frozenset({
    "flights:foreman",
    "flights:foreman-sonnet",
    "flights:lander",
})
# Each git question the hook asks itself is bounded by this many seconds.
GIT_TIMEOUT = 1.0


def receives_map(payload: dict) -> bool:
    """SubagentStart: an allowed agent type. SessionStart: the main chat, or an allowed sub-agent's own session start."""
    event = payload.get("hook_event_name")
    if event == "SubagentStart":
        return payload.get("agent_type") in MAP_AGENT_TYPES
    if event == "SessionStart":
        # agent_id is present only inside a sub-agent; the main chat (even under --agent) carries none.
        return "agent_id" not in payload or payload.get("agent_type") in MAP_AGENT_TYPES
    return False


def flight_paths(top: str, env: dict[str, str], deadline: float, log: PluginLog, session: str | None) -> list[str] | None:
    """A linked worktree's changed paths: each path git diff names against the merge-base of its HEAD and the main
    worktree's, and each untracked path git does not ignore. None in the main checkout; None too when a git read fails
    or times out, logged as a warning, so the caller serves the full map."""
    def timeout() -> float:
        # Bounded by GIT_TIMEOUT and by what is left of the hook's own deadline.
        return max(0.0, min(GIT_TIMEOUT, deadline - time.monotonic()))

    try:
        if not repo.linked_worktree(top, env, timeout()):
            return None
        base = repo.merge_base(top, repo.main_worktree_head(top, env, timeout()), env, timeout())
        return repo.changed_paths(top, base, env, timeout()) + repo.untracked_paths(top, env, timeout())
    except Unavailable as error:
        log.record("warning", "flight-folders-unread", f"the folders this worktree changed could not be read, so it gets the"
                   f" full map: {error}", "hook.py#flight_paths", session, {"toplevel": top})
        return None


def map_text(cwd: str, env: dict[str, str], deadline: float, log: PluginLog, session: str | None = None) -> str | None:
    """The map for the repository holding cwd: a linked worktree's changed folders, else every folder. None outside a
    git repository, which is no failure: there is no codebase to map; None when no tracked source file names anything,
    where ponytail too adds no map."""
    top = repo.toplevel(cwd, env, GIT_TIMEOUT)
    if top is None:
        return None
    head = repo.head(top, env, GIT_TIMEOUT)
    paths = flight_paths(top, env, deadline, log, session)
    lines = cache.map_for(top, head, env, deadline, log)
    # Imported here: only a loop that receives the map renders it; every other hook call skips compiling build's patterns.
    from . import build

    # A worktree whose changes reach no folder with a line (fresh, or only non-source files) gets the full map.
    flight = build.flight_map(lines, paths) if paths is not None else ""
    return flight or build.full_map(lines) or None


def response(event: str, text: str) -> str:
    return json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}})


def respond(payload: dict, env: dict[str, str], deadline: float, log: PluginLog) -> str | None:
    """The hook's stdout for payload, or None when this loop receives nothing; log records each unavailable map."""
    if not receives_map(payload):
        return None
    # Claude Code runs the hook in the session's folder; a payload without cwd means that one.
    cwd = payload.get("cwd") or os.getcwd()
    try:
        text = map_text(cwd, env, deadline, log, payload.get("session_id"))
    except Unavailable as error:
        text = f"{UNAVAILABLE}{error}"
        log.record("error", "map-unavailable", text, "hook.py#respond", payload.get("session_id"),
                   {"cwd": cwd, "event": payload.get("hook_event_name"), "agentType": payload.get("agent_type")})
    if text is None:
        return None
    return response(payload["hook_event_name"], text)
