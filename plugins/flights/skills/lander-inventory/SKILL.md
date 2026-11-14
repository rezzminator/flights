---
name: lander-inventory
description: Internal kit of flights:lander and flights:reviewer — lander-inventory.py lists what a diff left behind (LEFT, LITERAL, GONE rows) and computes the review's spawn PLAN. Not invoked directly — ask flights:lander or flights:reviewer.
visibility:
  visible-to:
    include: [flights:lander, flights:reviewer]
---

# lander-inventory

Run `python3 -I ${CLAUDE_PLUGIN_ROOT}/skills/lander-inventory/lander-inventory.py {WORKTREE} {BASE} [HEAD] [--spec FILE …] [--paths PATHSPEC …] [--cluster-lines N] [--max-diff-checkers N] [--own]`, the path written in full. Python 3 standard library; it reads the worktree through `git` and writes nothing. The diff is BASE against the working tree — commits, staged, unstaged and untracked work; with HEAD, the commits BASE..HEAD alone; `--paths` narrows either to those pathspecs. Exit 0 prints the rows; exit 2 prints `FAILED` and the cause when git or the input breaks, or the usage line when an argument is missing.

- `LEFT`: a name the diff removed everywhere it touched, still in the tree outside history files.
- `LITERAL`: a name a code or data file dropped from inside a string or key on a replaced line.
- `GONE`: a file the diff deleted or renamed away, still named in the tree.
- `PLAN`: the spawn — `PLAN DIFF-CHECKER` clusters (k = min(4, ceil(production diff lines / 600)), none at 400 lines or fewer; `--cluster-lines` replaces the 600, `--max-diff-checkers` the 4), `PLAN SPEC-CHECKER` row ranges over each `--spec` file with 10 or more numbered rows (4 in all at most), `PLAN USAGE-CHECKER` ranges over the rows above by line number (6 at most); with `--own`, `PLAN OWN`, the changed files no diff-checker reads (prose, tests no cluster took, and the whole diff when there is no diff-checker).
