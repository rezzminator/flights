<div align="center">

# flights

**Claude Code plugin for a codebase map read from each package's front door — one line per package folder, given to the main chat at session start and to the flights builder agents at their start, cached per commit**

[![CI](https://github.com/rezzminator/flights/actions/workflows/ci.yml/badge.svg?branch=develop)](https://github.com/rezzminator/flights/actions/workflows/ci.yml)
[![Version](https://img.shields.io/badge/version-0.1.0-blue)](./CHANGELOG.md)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](./LICENSE)
[![Claude Code plugin](https://img.shields.io/badge/Claude%20Code-plugin-D97757)](https://code.claude.com/docs/en/plugins)
[![Built with Professor](https://img.shields.io/badge/built%20with-Professor-8A2BE2)](https://github.com/rezzminator/professor)

**Contents:** [Why](#why) · [Quick start](#quick-start) · [The map](#the-map) · [How it works](#how-it-works) · [Logs](#logs) · [Limits](#limits) · [Help](#help) · [Contributing](#contributing) · [License](#license) · [Changelog](./CHANGELOG.md)

</div>

## Why

An agent that does not know what a codebase already holds writes a second copy of it. flights hands every loop that builds code a map of what exists before it starts: one line per package folder, read from the package's front door — the doc comment its own authors wrote — never guessed from code.

## Quick start

```sh
claude plugin marketplace add rezzminator/flights
claude plugin install flights@professor
```

Start a session in a git repository. Needs `python3` (3.9 or later) and `git`; a repository with Go modules needs `go`. Remove it with `claude plugin uninstall flights@professor`.

## The map

```text
Codebase map (each package folder and the first line of its front door's doc; reuse what exists, and read a folder's front door before its other files):
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

A package with no doc shows `(no front door doc)`, so the gap is visible. Hidden folders and `vendor/`, `node_modules/` and `testdata/` trees are left out. The session's own folder and its subfolders come first; the text stays within 4000 characters, each line within 200, and a footer counts the folders left out.

## How it works

- **Who receives it.** The main chat at `SessionStart` (startup, resume, clear and compact). A sub-agent at `SubagentStart` only when its type is `flights-foreman`, `flights-foreman-sonnet`, `flights-lander`, `flights-hunter` or `flights-sub-lander`; every other sub-agent receives nothing.
- **Cached per commit.** The map is kept per repository top level and `HEAD` commit under `${XDG_CACHE_HOME:-$HOME/.cache}/flights/map/`. A cached map is answered without running `go`. A new commit builds a new map.
- **Never slow.** The hook answers within 4.5 seconds. A map not yet cached is built in the background; when the build outlasts that, the loop is told the map is still building, and the next start finds it cached.
- **A failure is said.** When the map cannot be built — no commit yet, `go` missing, `go list` failing — the loop receives one line, `Codebase map unavailable: {reason}`, never nothing. Outside a git repository there is no codebase, and the loop receives nothing.
- **No settings.** There is nothing to configure.

## Logs

Rows go to `$PLUGIN_LOG_DIR/flights/`, else `$HOME/.local/state/flights/logs/`: `errors.jsonl` for every unavailable map, `debug.jsonl` for each cache hit, miss and build.

## Limits

- Claude Code only: Codex and OpenCode receive no map.
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
