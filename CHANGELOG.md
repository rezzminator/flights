# Changelog

Every release of flights. Versions follow [semantic versioning](https://semver.org); each release is the `main` commit tagged `flights--v<version>`, with a GitHub release carrying the section below.

## [0.2.0] — 2026-11-07

### Added

- The flights agent family ships in the plugin, under the names Claude Code gives a plugin's parts: the agents `flights:foreman`, `flights:foreman-sonnet` (the foreman's manual word for word, on Sonnet), `flights:lander`, `flights:hunter`, `flights:spec-walker`, `flights:sub-lander` and `flights:speccer`; the commands `/flights:spec` and `/flights:doctor`; and the skill `flights:lander-inventory`, whose kit the lander runs from `${CLAUDE_PLUGIN_ROOT}/skills/lander-inventory/lander-inventory.py`.
- The map lists the hottest package folder first: each `Read` of any loop (the main chat and every sub-agent) adds one to its file's score (a file inside a work tree nested in the repository, such as a submodule or a linked worktree, counts for none), recorded by an asynchronous `PostToolUse` hook that never slows the read; a score halves every 14 days and is forgotten below 0.01; a folder's heat is the sum over the files whose nearest enclosing package folder it is. The 4000-character cut drops the coldest folders first; ties and never-read folders keep the session's folder first, then the name.
- The header names the order: `hottest first, by how often this repository's files are read, recent reads weighing more`, or `no read history yet: the session's folder first, then by name`.
- The scores are kept per repository top level across commits under `${XDG_CACHE_HOME:-$HOME/.cache}/flights/heat/`, and seeded once in the background, within 15 seconds, from this Claude Code config's own transcripts of the repository (`${CLAUDE_CONFIG_DIR:-$HOME/.claude}/projects/`), each `Read` of the last 30 days counted by its age.
- Log rows for the read scores: a failed read or seed in `errors.jsonl`, an unusable score file rebuilt empty and transcripts a seed could not open in `warnings.jsonl`, each seed in `debug.jsonl` (`heat-seed-cut` when its budget ran out first).

### Changed

- The map goes to the sub-agent types `flights:foreman`, `flights:foreman-sonnet`, `flights:lander`, `flights:hunter` and `flights:sub-lander`, the agents this plugin now ships; the `flights-*` types 0.1.0 named receive none. To migrate, spawn `flights:foreman` where you spawned `flights-foreman`, and likewise for each.

### Fixed

- A session started outside a login shell, whose `PATH` lacks the `go` the user's shell profile adds, no longer gets `Codebase map unavailable: go is not on PATH`: the background build asks the login shell (`$SHELL -lc 'command -v go'`, `/bin/sh` without `SHELL`) and runs the `go` it names; only when that finds none too does the map say `go is not on PATH (nor in the login shell)`.

## [0.1.0] — 2026-11-07

### Added

- A codebase map at each main-chat `SessionStart` (startup, resume, clear, compact) and at the `SubagentStart` of the agent types `flights-foreman`, `flights-foreman-sonnet`, `flights-lander`, `flights-hunter` and `flights-sub-lander`; every other sub-agent receives none.
- One line per package folder, `{folder}/: {synopsis}`, read from each package's front door: a Go package's doc synopsis from `go list` in each tracked module, a Python package's `__init__.py` docstring via `ast`, the leading comment of `index.ts`/`index.js`, and the leading `//!` doc of `lib.rs`/`mod.rs`. A package without one shows `(no front door doc)`.
- The map reads and never writes: `go list` runs with `-mod=readonly`, so no `go.mod` is edited and no module looked up; a front door that is a symlink leaving the repository, or names no regular file, shows `(front door unreadable: {why})`.
- The session's folder and its subfolders first; the text within 4000 characters, each synopsis within 200, and a footer counting the folders left out.
- The map cached per repository and `HEAD` commit under `${XDG_CACHE_HOME:-$HOME/.cache}/flights/map/`; a cached map runs no `go`.
- The hook answers within 4.5 seconds: a map not yet cached builds in the background, and a build that outlasts the answer is said as still building and ready at the next start.
- A map that cannot be built is said as `Codebase map unavailable: {reason}`; outside a git repository nothing is added.
- Plugin log rows under `$PLUGIN_LOG_DIR/flights/`, else `$HOME/.local/state/flights/logs/`: each unavailable map in `errors.jsonl`, each cache hit, miss and build in `debug.jsonl`.

### Known limits

- Claude Code only: Codex and OpenCode receive no map.
- A sub-agent's own `SessionStart` after its compaction that does not name the sub-agent gives it the map.
