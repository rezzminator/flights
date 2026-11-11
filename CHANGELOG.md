# Changelog

Every release of flights. Versions follow [semantic versioning](https://semver.org); each release is the `main` commit tagged `flights--v<version>`, with a GitHub release carrying the section below.

## [Unreleased]

### Changed

- `flights:speccer` is `flights:foreman-pro`: it designs work the codebase has never done, then builds it by its own hand. It reads the whole path the work touches, writes `design.md` in the flight directory before its first edit, and returns `BLOCKED` with the design and its questions, no edit made, when a fork only the user can settle remains. A `LEVEL 0–10` brief line (default 5) sets how far past the ask the design goes and what research it may buy: none at 0–3, `rr` only for a question the code cannot settle at 4–6, `rr-pro` and two whole designs compared at 7–8, `rr-pro-max` and the boldest design at 9–10; `/ultimate` is preloaded at every level. It runs on Opus at effort high, steered between medium and xhigh, and receives the codebase map. `/flights:spec` grills and writes `requirements.md`, then hands the build to `flights:foreman-pro` on the user's go; it no longer writes a `spec.md`. A setting, hook matcher or brief that names `flights:speccer` names `flights:foreman-pro`.
- The lander's three child agents are named for what they check: `flights:hunter` is `flights:diff-checker`, `flights:spec-walker` is `flights:spec-checker` and `flights:sub-lander` is `flights:usage-checker`, and the inventory script prints `PLAN DIFF-CHECKER`, `PLAN SPEC-CHECKER` and `PLAN USAGE-CHECKER` rows. A setting, hook matcher or brief that names an old agent type names the new one.
- The lander sheds its review once the fixes are in: it fixes every finding with the review still in context, then makes one `forward_compaction` call carrying the report's path, and the affected tests and the gate run from the report. Replayed over 95 past landings of 1,000 or more changed lines, the shed saves 15 to 20% of the lander's own cost; in a bench landing the lander went from 121,000 tokens of context to 31,000 and returned `FIXED` 6 requests later.
- The lander and both foremen wait in slices of at most 270 s: a command that can run longer runs in the background and writes its exit code to a file, awaited by repeating one `timeout 270` call (was one blocking wait of any length for a command past ten minutes). A wait past 300 s lets the prompt cache expire, and the next request re-pays the whole context: over 239 past landings those requests cost $77, against $9 in slices.
- Both foremen build from a trace their brief carries: with a `TRACE {RUN} · nodes {IDs}` line the foreman's one locating call is `tt check {RUN} --full {ID}` for each node, and it opens a file only for lines no node printed. A Sonnet foreman given the trace this way cost 27% less, with 35% fewer requests, than one given the same brief without it (two runs each).

## [1.0.0] — 2026-11-10

### Added

- The tracer and the reviewers ship in the plugin, moved from Professor: the agents `flights:tracer` (Sonnet, effort high), which answers numbered questions from code, `flights:sub-tracer` (Haiku, effort low), the reader it spawns per thread, and `flights:reviewer` and `flights:reviewer-pro` (Opus, effort high), which review a diff range with one tracer run and with up to three; the skill `flights:tracetree`, the tracer's kit, run from `${CLAUDE_PLUGIN_ROOT}/skills/tracetree/tracetree.py`; and the skill `/flights:tracer-use`, the manual of a tracer's caller, which both reviewers preload. With the tool-visibility-controller plugin installed, `flights:sub-tracer` and `flights:tracetree` are visible to `flights:tracer` and `flights:sub-tracer` alone.
- In a linked git worktree the map lists only the folders that worktree changed: the paths `git diff --name-only --no-renames` names against the merge-base of its `HEAD` and the main worktree's `HEAD`, plus the untracked files git does not ignore, each as its folder. Their lines are the full map's, in its order, within the same 2,000 characters, then `(N more folders not listed)` counting the changed folders left out, under the header `Codebase map of the folders this worktree changed (what already exists; reuse it, read a file only when you need its details):`. A worktree whose changes reach no folder with a line gets the full map, and so does one whose git reads fail or time out, with a `flight-folders-unread` warning naming the git error; a folder holding only untracked files has no line. The main checkout's map is unchanged.
- Each build that lands removes the map cache's `*.json`, `*.error` and `.building-*` files last written more than 7 days ago; a prune that fails is a `cache-prune-failed` warning and never fails the build.

### Changed

- Both foremen build under a price law, since every request re-reads the whole context: reading is three batched rounds before the first edit (locate every name in one Bash call, read the exact ranges, fill what is left), the tests and the change go in one round with the new tests run red first, and once the tests are green the foreman runs one throwaway script that drives the change with the inputs its tests leave out. The return is 25 lines at most and gains `PROBES` (each probed input with its printed result) and `UNTESTED` (behaviour neither a test nor a probe ran); `TESTS` and `PROBES` answer `COULD NOT RUN: {first error line}` when they could not.
- Both foremen build work one write-and-prove round cannot hold, several items or one item across many files, from a work list: right after the first reading round the foreman saves a list to a file outside the tree, named for the request, a line an item (`open {item} — {files}`), builds it group by group (one read call, one fill call, then every item of the group edited in one message and proven by one test call), rewrites each finished group's lines as `done {item} — {test name or file:line}` or `open {item} — {why}`, probes once after the last group and carries the list's path through a compaction. An item the brief names, or a file it points to lists, is never left open for the run's size, context or price, nor for a check the foreman cannot run: the item is built and what could not be checked goes under `UNTESTED`. A work list of more than 10 items returns one `ACCEPTANCE` row a group, one for each `open` line, and the list's path under `FILES`; one `open` row makes the status `PARTIAL`, whoever owns the item.
- `flights:foreman` runs at effort medium, where it ran at high; `flights:foreman-sonnet` stays at high. `effortControl` still raises a foreman's effort one step at a failing test run, so the write after the red proof runs one level above the reading.
- Both foremen carry a `tools:` list: `Read`, `Write`, `Edit`, `Bash`, `Skill`, `SendMessage` and the two forward-compaction tools. Their first request is about a fifth smaller (about 7,000 tokens), and `SendMessage` no longer costs a `ToolSearch` call first.
- `/flights:doctor` checks a foreman's reading rounds (requests before the first edit past the third, read-only requests carrying one command) and its unprobed returns.
- The codebase map is ponytail's symbol map, its `hooks/ponytail-map.js` ported to stdlib Python with the same output: one line per folder of tracked source files, `{folder}/: {names}`, naming the top-level functions, classes and exports each file defines (Python, JavaScript, TypeScript, Go, Rust, Ruby, Java, Kotlin, PHP, Swift, C#), each file's first 3 names and 1 each in a folder of more than 8, shared code (util, lib, service, component, hook, core, model, schema, api and the like) first, within a 2,000-character budget, then `(N more folders not listed)`. The header reads `Codebase map (what already exists; reuse it, read a file only when you need its details):`. Tests, generated, minified and vendored files, symlinks and untracked files are skipped; a repository whose source files name nothing gets no map. A session started in a subfolder gets the map of the whole repository, from its root. Ponytail's MIT notice ships in `plugins/flights/THIRD_PARTY_NOTICES.md`.
- A map cached by 0.2.0 is never read: the cache entry format moved, so each commit's map rebuilds once.
- The map is cached per `HEAD` commit alone, no longer per repository top level too: the main checkout and every worktree at one commit share one build. A build reads its own work tree, so another tree at the same commit can see a dirty tree's names rather than the commit's.

### Removed

- A foreman's children: the `Agent` tool and the § Another area section are gone from both foremen, with the `TRACER` line of the return and `/flights:doctor`'s shared-file-children check. Three forms of delegation were benched against the foreman building alone (an Opus foreman designing for Sonnet children, two foremen sharing a worktree, a tracer reading first) and each cost more.
- The foremen's effort buttons and their § Effort section: no foreman pressed one in 85 bench runs.
- The map at the `SubagentStart` of `flights:hunter` and `flights:sub-lander`: their runs are short and their briefs name their places by file and line. `flights:foreman`, `flights:foreman-sonnet` and `flights:lander` keep it.
- The read-heat ordering: the asynchronous `PostToolUse` `Read` hook that recorded every read, the read scores and their one-time seed from transcripts, and their log rows.
- The front-door doc lines: no Go, Python, TypeScript, JavaScript or Rust package doc is read, and no synopsis stands beside a folder; the 4000-character cut and its footer give way to the 2,000-character budget and `(N more folders not listed)`.
- The `go` requirement, with the background build's lookup of `go` through the login shell: the map needs only `python3` and `git`.

### Migration

- Split work across areas from the main chat: several foremen may share one worktree on separate files. To give a foreman its children back, add `Agent` to its `tools:` line.
- A caller that reads a foreman's return: `TRACER` is gone, `PROBES` and `UNTESTED` are new, and each `DECISIONS` item ends with how to flip it.
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
