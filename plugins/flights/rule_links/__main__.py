"""Run by `python3 -I -B {plugin}/rule_links`: isolated mode puts only this folder on sys.path, so the package is imported from its parent."""

import os
import sys

sys.path[0] = os.path.dirname(os.path.abspath(sys.path[0]))

try:
    from rule_links import main  # noqa: E402
except Exception as error:  # the package, or the codebase_map it shares, cannot load: still answer and exit 0
    import json
    import traceback

    traceback.print_exc(file=sys.stderr)
    # codebase_map's hook.response is the door for this answer; it is the import that failed, so its shape is written here.
    text = f"Flights rules not installed: the rule links cannot load: {type(error).__name__}: {error}"
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}}))
    sys.exit(0)

sys.exit(main(sys.argv[1:]))
