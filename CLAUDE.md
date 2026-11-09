# flights — a Claude Code plugin: the flights agent family that builds and lands work, and a codebase map, ponytail's symbol map ported (one line per source folder naming its exported functions, classes and types, within 2,000 characters; a linked worktree's lists only the folders it changed), injected into the main chat and the flights builder agents at their start

Every user installs from `main`: a map that silently goes missing leaves an agent writing a second copy of code that exists.

Where Vocabulary, Runtime or On demand disagrees with the code on a path, command or convention, follow the code and name each mismatch in your reply; `# Rules` binds regardless.

# Vocabulary

- spec: the plugin's promised behaviour · `README.md`
- installable plugin: the folder the install copies whole · `plugins/flights/`
- marketplace: this repository's own listing of its one plugin, named `professor` · `.claude-plugin/marketplace.json`
- flights family: the `flights:*` agents, the `/flights:{spec|doctor}` commands and the `flights:lander-inventory` skill · `plugins/flights/agents/`, `plugins/flights/commands/`, `plugins/flights/skills/`
- hooks: the `SessionStart` and `SubagentStart` command hooks, both running the package · `plugins/flights/hooks/hooks.json`
- package: the map, stdlib-only Python; `__init__.py`'s menu names every other file · `plugins/flights/codebase_map/__init__.py`
- map agent types: the sub-agent types that receive the map, the one list · `plugins/flights/codebase_map/hook.py` (`MAP_AGENT_TYPES`)
- unavailable line: `Codebase map unavailable: {reason}`, what a loop receives when the map cannot be built · `plugins/flights/codebase_map/command.py` (`UNAVAILABLE`)
- cache: the map cache, a commit's folder lines per `HEAD`, one build shared by every work tree at that commit, under `${XDG_CACHE_HOME:-$HOME/.cache}/flights/map/` · `plugins/flights/codebase_map/cache.py`
- port: ponytail's `{ponytail}/hooks/ponytail-map.js` map, ported behaviour-identical to stdlib Python; its MIT notice ships beside it · `plugins/flights/codebase_map/build.py`, `plugins/flights/THIRD_PARTY_NOTICES.md`
- plugin-log: the logging library: level files, bounded rows, rotation · `plugins/flights/codebase_map/plugin_log.py`
- tests: one unittest file per concern; `test_hook.py` builds a throwaway git repository and runs the real entry point and git; its expected full map and `test_build.py`'s expected values are ponytail's own output on the same input, captured once, except the flight-folder expectations, which ponytail has no counterpart for · `tests/`
- release check: the version agrees in plugin.json and the README badge, and `CHANGELOG.md` has its dated section · `scripts/release-check.sh`, `Makefile`
- CI workflows: the check, run on the `develop → main` pull request, and the publish on its merge · `.github/workflows/ci.yml`, `.github/workflows/publish.yml`

# Runtime

## Claude

- Live check: `claude --plugin-dir plugins/flights`, any installed copy of flights disabled for that run.
- By hand: `python3 -I -B plugins/flights/codebase_map < payload.json` prints the hook's JSON for a `SessionStart` or `SubagentStart` payload.

## Local

- Python 3.9 or later and git on `PATH`; a missing one fails the tests, never skips them.
- Done gate, green before every commit: `make test`, `make validate` (needs the `claude` CLI), `scripts/release-check.sh`.
- Narrowest test: `python3 -B -m unittest tests.{file}.{Class}.{test}`.

## CI

- `ci.yml`'s `check` (`make check`, on Linux and macOS) and `release` (`make release`) gate the `develop → main` pull request through its `ci` job; no CI runs on a push. Its merge runs `publish.yml`'s `publish`, which tags the merge commit `flights--v{X.Y.Z}` and publishes the GitHub release from the CHANGELOG section.

# Rules

## Publication

- **Nothing identifying ships:** NEVER a machine-absolute path (`/home/…`, `/Users/…`), personal data or a private project name in a tracked file, a commit message or a pull request body.
- **`main` is release-only:** it moves only by merging the `develop → main` pull request with a merge commit, after `ci` passes; NEVER a direct push, a squash or an admin override.
- **`develop` keeps its history:** NEVER force-push or delete it.
- **Code is pushed, and a release cut, only on the owner's ask.**

## Code

- A failure never reads as absence: a loop that should receive the map receives it or the unavailable line, and the reason is logged; only outside a git repository, or in one whose tracked source files name nothing (ponytail adds no map there either), does it receive nothing.
- The hook never blocks the session: it answers within `CAP_SECONDS`, exits 0 on every path, and a slow build finishes in the background.
- Stdlib Python only, run as `python3 -I -B`; each source file at most 240 lines, named in `__init__.py`'s menu.
- A new behaviour comes with a test in `tests/` watched failing first; a test asserts the whole output string.
- A tracked dev file stays outside `plugins/flights/`.

## Branches and releases

- `develop` is the default branch: every change lands there, by a commit or a pull request.
- A release, in order:
  1. On `develop`: bump the version in `plugins/flights/.claude-plugin/plugin.json` and the README badge, and move `## [Unreleased]` in `CHANGELOG.md` to `## [X.Y.Z] — {date}`.
  2. `make release-check` passes, after `git fetch origin main`.
  3. Open the `develop → main` pull request.
  4. Merge it once `ci` is green; `publish` tags and releases, and no tag is pushed by hand.
- Semantic versioning: a fix is a patch; a new behaviour a minor; a removed behaviour a major, its CHANGELOG entry saying how to migrate.
