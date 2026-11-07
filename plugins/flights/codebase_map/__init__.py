"""codebase_map: the in-house codebase map, one line per package folder read from its front door's doc.

Claude Code runs `python3 -I -B {plugin}/codebase_map` (hooks/hooks.json) at the main chat's
SessionStart and at each sub-agent's SubagentStart, with the hook payload on stdin; the map
reaches the main chat and the flights builder agent types only. `main` is the entry point:
with no argument it answers the hook, with `build {toplevel} {head}` it is the background
builder a cache miss starts.

- __main__.py: puts the package's parent on sys.path, which `python3 -I` leaves out, and calls main.
- hook.py: the hook payload in, the hook JSON out; which loops receive the map (MAP_AGENT_TYPES).
- cache.py: the per-commit cache of a repository's entries; a miss starts the background build and waits for it.
- build.py: a repository's entries, gathered from every front-door reader.
- go_packages.py: Go package folders and their doc synopsis, from `go list` per module.
- py_packages.py: Python package folders and their `__init__.py` docstring's first line, via `ast`.
- comment_doors.py: index.ts/index.js and lib.rs/mod.rs folders and their front door's leading comment.
- repo.py: the git questions: the repository's top level, its HEAD, its tracked files; and the one read of a tracked front door.
- command.py: the one door for running a command, and Unavailable, the failure the map names.
- plugin_log.py: the plugin-log library: level files under $PLUGIN_LOG_DIR/flights (else ~/.local/state/flights/logs).
- render.py: the injected text: header, cwd-first order, the budget and its footer, the unavailable line.
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback

from . import cache, hook
from .plugin_log import PluginLog, log_dir
from .render import UNAVAILABLE

PLUGIN = "flights"
# The whole hook answers within this many seconds; a cache miss still building then says so.
CAP_SECONDS = 4.5


def main(argv: list[str]) -> int:
    """Answer one hook call from stdin, or run the background build; always exit 0, never blocking the session."""
    env = dict(os.environ)
    log = PluginLog(PLUGIN, log_dir(env.get("PLUGIN_LOG_DIR"), env.get("HOME"), PLUGIN))
    if len(argv) == 3 and argv[0] == "build":
        cache.run_build(argv[1], argv[2], env, log)
        return 0
    deadline = time.monotonic() + CAP_SECONDS
    # Bytes: json.loads decodes them inside the try, so a payload that is not UTF-8 is said, not a traceback.
    raw = sys.stdin.buffer.read()
    try:
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError(f"expected a JSON object, got {type(payload).__name__}")
    except ValueError as error:
        # No event to answer by name: plain stdout is what a SessionStart hook adds as context.
        text = f"{UNAVAILABLE}the hook payload is not a JSON object ({error})"
        log.record("error", "payload-unreadable", text, "__init__.py#main", None, {"bytes": len(raw)})
        print(text)
        return 0
    try:
        out = hook.respond(payload, env, deadline, log)
    except Exception as error:  # a bug still answers the loop, never a silent session start
        traceback.print_exc(file=sys.stderr)
        if not hook.receives_map(payload):
            return 0
        text = f"{UNAVAILABLE}internal error: {type(error).__name__}: {error}"
        log.record("error", "hook-threw", text, "__init__.py#main", payload.get("session_id"), {"traceback": traceback.format_exc()})
        out = hook.response(str(payload.get("hook_event_name")), text)
    if out is not None:
        print(out)
    return 0
