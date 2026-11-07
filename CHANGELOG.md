# Changelog

Every release of flights. Versions follow [semantic versioning](https://semver.org); each release is the `main` commit tagged `flights--v<version>`, with a GitHub release carrying the section below.

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
