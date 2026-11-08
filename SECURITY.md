# Security policy

## Supported versions

Only the latest release of flights gets security fixes.

## Reporting a vulnerability

Use GitHub's
[private vulnerability reporting](https://github.com/rezzminator/flights/security/advisories/new),
never a public issue. Include what you found, how to reproduce it, Claude Code's version
(`claude --version`) and the flights version.

## What flights touches

- It runs `git rev-parse` and `git ls-files` in the session's repository and reads no file's
  content. It changes no file of the repository.
- It writes the map's cache under `${XDG_CACHE_HOME:-$HOME/.cache}/flights/map/`: the names at
  the repository's root and in each folder under it, never a file's content.
- It writes its own log files under `$PLUGIN_LOG_DIR/flights/` (else
  `$HOME/.local/state/flights/logs/`), private to the user, holding repository paths,
  commits, agent types and failure reasons.
