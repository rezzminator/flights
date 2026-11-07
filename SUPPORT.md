# Getting help

- **No map at session start.** Outside a git repository there is none, by design. Inside one,
  look for a `Codebase map unavailable:` line in the context: it names the reason (no commit
  yet, `go` not on `PATH`, `go list` failing, the map still building). A sub-agent receives the
  map only when its type is one of the flights builder types; see [Limits](./README.md#limits).
- **A question about using flights.**
  [Open an issue](https://github.com/rezzminator/flights/issues/new/choose) with the Question template.
- **A bug.** Use the bug report template; include `claude --version`, the flights version, the
  `Codebase map unavailable:` line if any, and rows from the plugin log.
- **A security problem.** Follow [SECURITY.md](./SECURITY.md), never a public issue.
