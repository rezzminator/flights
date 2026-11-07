"""The hook payload in, the hook JSON out: which loops receive the map, the map for the loop's folder, and each Read
recorded into the read heat."""

from __future__ import annotations

import json
import os

from . import cache, heat, repo, seed
from .command import Unavailable
from .plugin_log import PluginLog
from .render import MAP_BUDGET, UNAVAILABLE, render

# The sub-agent types that receive the map at their start, matched exactly; every other sub-agent receives nothing.
MAP_AGENT_TYPES = frozenset({
    "flights:foreman",
    "flights:foreman-sonnet",
    "flights:lander",
    "flights:hunter",
    "flights:sub-lander",
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


def map_text(cwd: str, env: dict[str, str], deadline: float, log: PluginLog) -> str | None:
    """The map for the repository holding cwd; None outside a git repository, which is no failure: there is no codebase to map."""
    top = repo.toplevel(cwd, env, GIT_TIMEOUT)
    if top is None:
        return None
    head = repo.head(top, env, GIT_TIMEOUT)
    entries = cache.entries(top, head, env, deadline, log)
    folder = os.path.relpath(os.path.realpath(cwd), top)
    store = heat.current(top, env, log)
    if store is None or not store.seeded:
        seed.start(top, env, log)
    folder_heat = {} if store is None else heat.package_heat([folder for folder, _ in entries], store, heat.wall_clock())
    return render(entries, "." if folder.startswith("..") else folder, MAP_BUDGET, folder_heat)


def response(event: str, text: str) -> str:
    return json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}})


def respond(payload: dict, env: dict[str, str], deadline: float, log: PluginLog) -> str | None:
    """The hook's stdout for payload, or None when this loop receives nothing; log records each unavailable map.
    A PostToolUse (the Read recorder) answers nothing."""
    if payload.get("hook_event_name") == "PostToolUse":
        heat.record_read(payload, env, log, heat.wall_clock())
        return None
    if not receives_map(payload):
        return None
    # Claude Code runs the hook in the session's folder; a payload without cwd means that one.
    cwd = payload.get("cwd") or os.getcwd()
    try:
        text = map_text(cwd, env, deadline, log)
    except Unavailable as error:
        text = f"{UNAVAILABLE}{error}"
        log.record("error", "map-unavailable", text, "hook.py#respond", payload.get("session_id"),
                   {"cwd": cwd, "event": payload.get("hook_event_name"), "agentType": payload.get("agent_type")})
    if text is None:
        return None
    return response(payload["hook_event_name"], text)
