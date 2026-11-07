# flights

Claude Code plugin for a codebase map read from each package's front door — one line per package folder, given to the main chat at session start and to the flights builder agents at their start, cached per commit.

At each `SessionStart` of the main chat, and at the `SubagentStart` of the agent types `flights-foreman`, `flights-foreman-sonnet`, `flights-lander`, `flights-hunter` and `flights-sub-lander`, the session's git repository is mapped: one line per Go package (`go list`), Python package (`__init__.py` docstring), `index.ts`/`index.js` or `lib.rs`/`mod.rs` folder, each with the first line of its front door's doc, or `(no front door doc)`. The map is cached per commit under `${XDG_CACHE_HOME:-$HOME/.cache}/flights/map/`, stays within 4000 characters with a footer counting the folders left out, and lists the session's folder first. A map that cannot be built is said in one `Codebase map unavailable: {reason}` line; outside a git repository nothing is added. The hook answers within 4.5 seconds and has no settings.

Install with `claude plugin install flights@professor` after `claude plugin marketplace add rezzminator/flights`. Needs `python3` 3.9 or later and `git`, and `go` for a repository with Go modules. Limits: Claude Code only. Remove it with `claude plugin uninstall flights@professor`. Full documentation: <https://github.com/rezzminator/flights>

Built and maintained with [Professor](https://github.com/rezzminator/professor).
