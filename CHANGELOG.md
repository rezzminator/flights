# Changelog

Every release of flights. Versions follow [semantic versioning](https://semver.org); each release is the `main` commit tagged `flights--v<version>`, with a GitHub release carrying the section below.

## [Unreleased]

### Added

- The tracer and the reviewers ship in the plugin, moved from Professor: the agents `flights:tracer` (Sonnet, effort high), which answers numbered questions from code, `flights:sub-tracer` (Haiku, effort low), the reader it spawns per thread, and `flights:reviewer` and `flights:reviewer-pro` (Opus, effort high), which review a diff range with one tracer run and with up to three; the skill `flights:tracetree`, the tracer's kit, run from `${CLAUDE_PLUGIN_ROOT}/skills/tracetree/tracetree.py`; and the skill `/flights:tracer-use`, the manual of a tracer's caller, which both reviewers preload. With the tool-visibility-controller plugin installed, `flights:sub-tracer` and `flights:tracetree` are visible to `flights:tracer` and `flights:sub-tracer` alone.
- In a linked git worktree the map lists only the folders that worktree changed: the paths `git diff --name-only --no-renames` names against the merge-base of its `HEAD` and the main worktree's `HEAD`, plus the untracked files git does not ignore, each as its folder. Their lines are the full map's, in its order, within the same 2,000 characters, then `(N more folders not listed)` counting the changed folders left out, under the header `Codebase map of the folders this worktree changed (what already exists; reuse it, read a file only when you need its details):`. A worktree whose changes reach no folder with a line gets the full map, and so does one whose git reads fail or time out, with a `flight-folders-unread` warning naming the git error; a folder holding only untracked files has no line. The main checkout's map is unchanged.
- Each build that lands removes the map cache's `*.json`, `*.error` and `.building-*` files last written more than 7 days ago; a prune that fails is a `cache-prune-failed` warning and never fails the build.

### Changed

- The codebase map is ponytail's symbol map, its `hooks/ponytail-map.js` ported to stdlib Python with the same output: one line per folder of tracked source files, `{folder}/: {names}`, naming the top-level functions, classes and exports each file defines (Python, JavaScript, TypeScript, Go, Rust, Ruby, Java, Kotlin, PHP, Swift, C#), each file's first 3 names and 1 each in a folder of more than 8, shared code (util, lib, service, component, hook, core, model, schema, api and the like) first, within a 2,000-character budget, then `(N more folders not listed)`. The header reads `Codebase map (what already exists; reuse it, read a file only when you need its details):`. Tests, generated, minified and vendored files, symlinks and untracked files are skipped; a repository whose source files name nothing gets no map. A session started in a subfolder gets the map of the whole repository, from its root. Ponytail's MIT notice ships in `plugins/flights/THIRD_PARTY_NOTICES.md`.
- A map cached by 0.2.0 is never read: the cache entry format moved, so each commit's map rebuilds once.
- The map is cached per `HEAD` commit alone, no longer per repository top level too: the main checkout and every worktree at one commit share one build. A build reads its own work tree, so another tree at the same commit can see a dirty tree's names rather than the commit's.

### Removed

- The map at the `SubagentStart` of `flights:hunter` and `flights:sub-lander`: their runs are short and their briefs name their places by file and line. `flights:foreman`, `flights:foreman-sonnet` and `flights:lander` keep it.
- The read-heat ordering: the asynchronous `PostToolUse` `Read` hook that recorded every read, the read scores and their one-time seed from transcripts, and their log rows.
- The front-door doc lines: no Go, Python, TypeScript, JavaScript or Rust package doc is read, and no synopsis stands beside a folder; the 4000-character cut and its footer give way to the 2,000-character budget and `(N more folders not listed)`.
- The `go` requirement, with the background build's lookup of `go` through the login shell: the map needs only `python3` and `git`.

### Migration

- Spawn `flights:tracer` where you spawned `tracer`, and `flights:reviewer` and `flights:reviewer-pro` where you spawned `reviewer` and `reviewer-pro`; preload `flights:tracer-use` where an agent preloaded `tracer:use`. The kit runs from `${CLAUDE_PLUGIN_ROOT}/skills/tracetree/tracetree.py`, no longer `~/.claude/skills/tracetree/tracetree.py`. Trace runs stay under `/tmp/{project}/tracer/`, so a run made before the move is still recalled.
- Delete `~/.cache/flights/heat/` (under `$XDG_CACHE_HOME/flights/heat/` when that is set): nothing reads it any more.
- Nothing to delete under `~/.cache/flights/map/`: each build removes the files older than 7 days, so the older formats' files go by themselves within a week.
- A hunter or sub-lander that needs a folder's names reads the files its brief names; nothing else changes for them.

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
