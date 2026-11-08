<div align="center">

# flights

**Claude Code plugin for the flights agents that build and land work — two foremen, a lander with its three reviewers, a speccer, /flights:spec and /flights:doctor — and a codebase map, a names-only tree of every entry at the repository's root and the first 6 entries of each folder under it, given to the main chat and the flights builder agents at their start, cached per commit**

[![CI](https://github.com/rezzminator/flights/actions/workflows/ci.yml/badge.svg?branch=develop)](https://github.com/rezzminator/flights/actions/workflows/ci.yml)
[![Version](https://img.shields.io/badge/version-0.2.0-blue)](./CHANGELOG.md)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](./LICENSE)
[![Claude Code plugin](https://img.shields.io/badge/Claude%20Code-plugin-D97757)](https://code.claude.com/docs/en/plugins)
[![Built with Professor](https://img.shields.io/badge/built%20with-Professor-8A2BE2)](https://github.com/rezzminator/professor)

**Contents:** [Why](#why) · [Quick start](#quick-start) · [The agents](#the-agents) · [The map](#the-map) · [How it works](#how-it-works) · [Logs](#logs) · [Limits](#limits) · [Help](#help) · [Contributing](#contributing) · [License](#license) · [Changelog](./CHANGELOG.md)

</div>

## Why

An agent that does not know what a codebase already holds writes a second copy of it. flights ships the agents that build and land work, and hands every loop that builds code a map of what exists before it starts: every entry at the repository's root and the first 6 entries of each folder under it, names only, from the paths git lists.

## Quick start

```sh
claude plugin marketplace add rezzminator/flights
claude plugin install flights@professor
```

Start a session in a git repository. Needs `python3` (3.9 or later) and `git`. Remove it with `claude plugin uninstall flights@professor`.

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
Codebase map (every entry at this repository's root, and the first 6 entries of each folder under it; folders end in /; reuse what exists):
.github/
  workflows/
docs/
  design/
  dev/
  README.md
pfm/
  cmd/
  internal/
  scripts/
  Makefile
  go.mod
  go.sum
  … 3 more
Makefile
README.md
```

- **The root, whole.** Every entry at the repository's root, folders first, then files, each group sorted by name in byte order. A folder's name ends in `/`. There is no size cut.
- **Each root folder, its first 6.** Under each root folder, indented two spaces, its own first 6 entries in the same order, then `… N more` when it holds more. Nothing deeper is listed.
- **What git lists.** The entries are the paths `git ls-files --cached --others --exclude-standard` names — tracked files, and untracked files that are not ignored — that the work tree still holds. A submodule, or an untracked repository nested inside, shows as a folder.
- **Names only.** No text stands beside a name.
- A repository whose work tree holds no listed file gets `Codebase map: git lists no file in this repository's work tree.`

## How it works

- **Who receives it.** The main chat at `SessionStart` (startup, resume, clear and compact). A sub-agent at `SubagentStart` only when its type is `flights:foreman`, `flights:foreman-sonnet`, `flights:lander`, `flights:hunter` or `flights:sub-lander`; every other sub-agent receives nothing.
- **The same map wherever the session starts.** A session started in a subfolder gets the tree of the whole repository, from its root.
- **Cached per commit.** The map is kept per repository top level and `HEAD` commit under `${XDG_CACHE_HOME:-$HOME/.cache}/flights/map/`. A new commit builds a new map.
- **Never slow.** The hook answers within 4.5 seconds. A map not yet cached is built in the background; when the build outlasts that, the loop is told the map is still building, and the next start finds it cached.
- **A failure is said.** When the map cannot be built — no commit yet, `git` missing or failing — the loop receives one line, `Codebase map unavailable: {reason}`, never nothing. Outside a git repository there is no codebase, and the loop receives nothing.
- **No settings.** There is nothing to configure.

## Logs

Rows go to `$PLUGIN_LOG_DIR/flights/`, else `$HOME/.local/state/flights/logs/`: `errors.jsonl` for every unavailable map and every build that failed, `debug.jsonl` for each cache hit, miss and build.

## Limits

- Claude Code only: Codex and OpenCode receive no map, and load none of the agents, commands or skill from this plugin.
- The agents hand work on to Professor's agents (`gitter` for every git write, `tracer`, `pcm`, `documenter`), and `/flights:doctor` reads runs through Professor's `pfm`; without Professor those hand-offs have no target.
- The map is read from the work tree when its commit is first seen; edits made after that show at the next commit.
- The sub-agent types that receive the map are fixed in the plugin.
- A sub-agent's own `SessionStart` after its compaction is told apart from the main chat's only when Claude Code names the sub-agent in it; when it does not, that sub-agent receives the map.

## Help

See [SUPPORT.md](./SUPPORT.md); security problems go through [SECURITY.md](./SECURITY.md).

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md).

## License

[MIT](./LICENSE). Built and maintained with [Professor](https://github.com/rezzminator/professor).
