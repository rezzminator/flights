<div align="center">

# flights

**Claude Code plugin for the flights agents that build and land work — two foremen, a lander with its three reviewers, a speccer, /flights:spec and /flights:doctor — and a codebase map read from each package's front door, one line per package folder, hottest first by how often the repository's files are read, given to the main chat and the flights builder agents at their start, cached per commit**

[![CI](https://github.com/rezzminator/flights/actions/workflows/ci.yml/badge.svg?branch=develop)](https://github.com/rezzminator/flights/actions/workflows/ci.yml)
[![Version](https://img.shields.io/badge/version-0.2.0-blue)](./CHANGELOG.md)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](./LICENSE)
[![Claude Code plugin](https://img.shields.io/badge/Claude%20Code-plugin-D97757)](https://code.claude.com/docs/en/plugins)
[![Built with Professor](https://img.shields.io/badge/built%20with-Professor-8A2BE2)](https://github.com/rezzminator/professor)

**Contents:** [Why](#why) · [Quick start](#quick-start) · [The agents](#the-agents) · [The map](#the-map) · [How it works](#how-it-works) · [Logs](#logs) · [Limits](#limits) · [Help](#help) · [Contributing](#contributing) · [License](#license) · [Changelog](./CHANGELOG.md)

</div>

## Why

An agent that does not know what a codebase already holds writes a second copy of it. flights ships the agents that build and land work, and hands every loop that builds code a map of what exists before it starts: one line per package folder, read from the package's front door — the doc comment its own authors wrote — never guessed from code.

## Quick start

```sh
claude plugin marketplace add rezzminator/flights
claude plugin install flights@professor
```

Start a session in a git repository. Needs `python3` (3.9 or later) and `git`; a repository with Go modules needs `go`. Remove it with `claude plugin uninstall flights@professor`.

## The agents

Claude Code names each plugin agent `flights:{name}`: that is the `subagent_type` you spawn it by and the `agent_type` every hook sees.

| Agent | Model | Its work |
| --- | --- | --- |
| `flights:foreman` | Opus, effort high | builds one request by its own hand: design choices, ambiguity, unfamiliar code, an unknown cause, cross-module work |
| `flights:foreman-sonnet` | Sonnet, effort high | the same manual, word for word, for clear work with a pattern to follow |
| `flights:lander` | Opus, effort medium | takes a worktree to merge-ready once every foreman on it returned: syncs to the target's tip, runs the gate, spawns the review its kit computes |
| `flights:hunter` | Opus | spawned by the lander: one diff cluster's defects, read whole against the spec rows it implements |
| `flights:spec-walker` | Sonnet | spawned by the lander: a range of the request's numbered rows, each traced to its code |
| `flights:sub-lander` | Haiku | spawned by the lander: names the diff removed that the tree still holds, and threads past the diff |
| `flights:speccer` | Opus, effort xhigh | designs novel work with you before a build, through `/flights:spec` |

| Command or skill | What it does |
| --- | --- |
| `/flights:spec [work \| file]` | grills the request until nothing stays open; returns the `requirements.md` and `spec.md` paths, ready to build |
| `/flights:doctor [session or agent id]` | measures a flight: landed lines per million input tokens, written and read per agent, the silent share, then where the reading went |
| `flights:lander-inventory` | the lander's kit, `skills/lander-inventory/lander-inventory.py`: what a diff left behind (`LEFT`, `LITERAL`, `GONE` rows) and the review's spawn `PLAN` |

The `effortControl` and `visibility` frontmatter keys take effect with the auto-effort and tool-visibility-controller plugins installed: the foremen's effort is then steered between medium and xhigh, the lander's three reviewers and its kit are visible to the lander alone, and the lander and speccer to the main chat alone. Without them Claude Code ignores those keys.

## The map

```text
Codebase map (hottest first, by how often this repository's files are read, recent reads weighing more; each package folder and the first line of its front door's doc; reuse what exists, and read a folder's front door before its other files):
internal/clock/: Package clock is the one time seam: every time call routes through a Clock.
internal/store/: Package store keeps the index in SQLite.
tools/: Tools for the release scripts.
tools/legacy/: (no front door doc)
web/: The web client's entry point.
(12 more package folders not listed)
```

| Language | A package folder | Its line |
| --- | --- | --- |
| Go | every package of every tracked `go.mod`'s module, from `go list` | the package doc's synopsis (its first sentence) |
| Python | a folder with a tracked `__init__.py` | the first line of its docstring, read with `ast` |
| TypeScript, JavaScript | a folder with a tracked `index.ts` or `index.js` | the first prose line of the comment opening the file |
| Rust | a folder with a tracked `lib.rs` or `mod.rs` | the first line of its leading `//!` doc |

A package with no doc shows `(no front door doc)`, so the gap is visible. Hidden folders and `vendor/`, `node_modules/` and `testdata/` trees are left out. The text stays within 4000 characters, each line within 200, and a footer counts the folders left out.

### The order

The hottest package folder comes first: the one whose files the loops in this repository read most, recent reads weighing more. The cut to 4000 characters then drops the coldest.

- **Every read counts.** Each `Read` any loop makes — the main chat and every sub-agent — adds one to its file's score, recorded by an asynchronous `PostToolUse` hook that never slows the read. A file outside the session's repository, or inside a work tree nested in it (a submodule, a linked worktree), is not counted.
- **Recent reads weigh more.** A score halves every 14 days; a file whose score falls below 0.01 is forgotten.
- **A folder's heat** is the sum over the files whose nearest enclosing package folder it is: a read of `internal/clock/fake/fake.go` counts for `internal/clock/` when `internal/clock/fake/` is no package folder, never for `internal/` too.
- **Ties**, and every folder never read, keep the old order: the session's own folder and its subfolders first, then by name.
- **The first start** seeds the scores once, in the background within 15 seconds, from this Claude Code config's own transcripts of the repository (`${CLAUDE_CONFIG_DIR:-$HOME/.claude}/projects/`), counting each `Read` of the last 30 days by its age.
- **The header says which order you got.** With no read of any package folder yet, it reads `Codebase map (no read history yet: the session's folder first, then by name; …)`.
- The scores are kept per repository top level, across commits, in `${XDG_CACHE_HOME:-$HOME/.cache}/flights/heat/`; they never change which map is cached.

## How it works

- **Who receives it.** The main chat at `SessionStart` (startup, resume, clear and compact). A sub-agent at `SubagentStart` only when its type is `flights:foreman`, `flights:foreman-sonnet`, `flights:lander`, `flights:hunter` or `flights:sub-lander`; every other sub-agent receives nothing. Every loop's reads are counted, whether or not it receives the map.
- **Cached per commit.** The map is kept per repository top level and `HEAD` commit under `${XDG_CACHE_HOME:-$HOME/.cache}/flights/map/`. A cached map is answered without running `go`. A new commit builds a new map.
- **Never slow.** The hook answers within 4.5 seconds. A map not yet cached is built in the background; when the build outlasts that, the loop is told the map is still building, and the next start finds it cached.
- **`go` from your login shell.** A session started outside a login shell can lack the `PATH` your shell profile sets. When `go` is not on the hook's `PATH`, the background build asks your login shell once (`$SHELL -lc 'command -v go'`, `/bin/sh` without `SHELL`) and runs the `go` it names.
- **A failure is said.** When the map cannot be built — no commit yet, `go` neither on `PATH` nor in the login shell, `go list` failing — the loop receives one line, `Codebase map unavailable: {reason}`, never nothing. Outside a git repository there is no codebase, and the loop receives nothing.
- **No settings.** There is nothing to configure.

## Logs

Rows go to `$PLUGIN_LOG_DIR/flights/`, else `$HOME/.local/state/flights/logs/`: `errors.jsonl` for every unavailable map and every read or seed that failed, `warnings.jsonl` for a read score file found unusable and rebuilt and for transcripts a seed could not open, `debug.jsonl` for each cache hit, miss and build and each seed (`heat-seed-cut` when its 15 seconds ran out first).

## Limits

- Claude Code only: Codex and OpenCode receive no map, and load none of the agents, commands or skill from this plugin.
- The agents hand work on to Professor's agents (`gitter` for every git write, `tracer`, `pcm`, `documenter`), and `/flights:doctor` reads runs through Professor's `pfm`; without Professor those hand-offs have no target.
- The map is read from the work tree when its commit is first seen; edits made after that show at the next commit.
- The sub-agent types that receive the map are fixed in the plugin.
- A sub-agent's own `SessionStart` after its compaction is told apart from the main chat's only when Claude Code names the sub-agent in it; when it does not, that sub-agent receives the map.
- Other languages' packages are not listed.

## Help

See [SUPPORT.md](./SUPPORT.md); security problems go through [SECURITY.md](./SECURITY.md).

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md).

## License

[MIT](./LICENSE). Built and maintained with [Professor](https://github.com/rezzminator/professor).
