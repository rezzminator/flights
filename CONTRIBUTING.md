# Contributing

Thanks for helping. flights is small on purpose: two hooks, one map, one cache
and a rule that a failure is always said, never silent. A change that keeps it
that way is the easiest to merge.

## Layout

| Path | Role |
| --- | --- |
| `plugins/flights/` | Everything that installs, and nothing else; dev files never go in it |
| `plugins/flights/hooks/hooks.json` | The `SessionStart` and `SubagentStart` command hooks |
| `plugins/flights/codebase_map/` | The map, a stdlib-only Python package; its front door `__init__.py` names every file |
| `tests/` | One unittest file per concern; `test_hook.py` builds a throwaway git repository and runs the real entry point, git and Go |
| `scripts/release-check.sh` | The version agrees everywhere it is written |

## Set up

Python 3.9 or later, git and Go on `PATH`; the `claude` CLI for `make validate`.

```sh
make test               # every test; a missing go or git fails the run
make validate           # claude plugin validate --strict
scripts/release-check.sh
```

Try the checkout in a real session with `claude --plugin-dir plugins/flights`,
any installed copy of flights disabled for that run.

## Rules for a change

- A new behaviour comes with a test in `tests/` that you watched fail first.
- A failure never reads as absence: the hook injects `Codebase map unavailable: {reason}`
  and logs it, never nothing.
- Each source file stays at or under 240 lines, and the front door's menu names it.
- A change in behaviour moves `README.md` and `CHANGELOG.md` (under
  `## [Unreleased]`) in the same pull request.
- No machine-absolute paths or personal data in a tracked file.

## Send it in

1. Fork the repository and branch off `develop`.
2. Make the change with its test; run the gates above.
3. Open a pull request against `develop`; `main` holds only releases.

By contributing you agree to license your work under the repository's
[MIT license](./LICENSE) and to follow the [Code of Conduct](./CODE_OF_CONDUCT.md).
