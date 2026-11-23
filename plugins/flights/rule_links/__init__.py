"""rule_links: installs the plugin's rule files as links in the user's Claude rules folder.

Claude Code runs `python3 -I -B {plugin}/rule_links` (hooks/hooks.json) at the main chat's SessionStart, with the hook
payload on stdin. Each `{plugin root}/rules/{stem}.md` becomes the symlink `{config}/rules/flights-{stem}.md`
({config}: $CLAUDE_CONFIG_DIR, else ~/.claude); a rule file a hook links loads from the next chat. The chat hears
nothing when every link was already right, one line when one changed, and one `Flights rules not installed: {reason}`
line, logged, when it could not install. `main` is the entry point; it exits 0 on every path.

- __main__.py: puts the package's parent on sys.path, which `python3 -I` leaves out, and calls main.
- links.py: the links themselves: the config folder, the shipped stems, the atomic link, the sync and its line.

The hook's JSON answer and the logging library are codebase_map's (hook.response, plugin_log), shared, not copied.
"""

from __future__ import annotations

import json
import os
import sys
import traceback

from codebase_map.hook import response
from codebase_map.plugin_log import PluginLog, log_dir

from .links import NOT_INSTALLED, NotInstalled, config_dir, sync

PLUGIN = "flights"
PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))


def main(argv: list[str]) -> int:
    """Install the links for one SessionStart; always exit 0, never blocking the session."""
    env = dict(os.environ)
    log = PluginLog(PLUGIN, log_dir(env.get("PLUGIN_LOG_DIR"), env.get("HOME"), PLUGIN))
    try:
        payload = json.loads(sys.stdin.buffer.read())
    except ValueError:
        payload = None  # the links need nothing from it: only the session id for a log row is lost
    if not isinstance(payload, dict):
        payload = {}
    session = payload.get("session_id")
    plugin_root = env.get("CLAUDE_PLUGIN_ROOT") or os.path.dirname(PACKAGE_DIR)
    rules = None
    try:
        rules = os.path.join(config_dir(env), "rules")
        outcome = sync(plugin_root, rules)
        text = outcome.line()
        if outcome.kept:
            log.record("error", "rules-not-installed", text, "__init__.py#main", session, {"rules": rules, "kept": outcome.kept})
    except NotInstalled as error:
        text = f"{NOT_INSTALLED}{error}"
        log.record("error", "rules-not-installed", text, "__init__.py#main", session, {"rules": rules, "plugin": plugin_root})
    except Exception as error:  # a bug still answers the chat, never a silent session start
        traceback.print_exc(file=sys.stderr)
        text = f"{NOT_INSTALLED}internal error: {type(error).__name__}: {error}"
        log.record("error", "rules-not-installed", text, "__init__.py#main", session, {"traceback": traceback.format_exc()})
    if text is not None:
        print(response(str(payload.get("hook_event_name") or "SessionStart"), text))
    return 0
