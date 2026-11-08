"""Tests for codebase_map.render: the tree of names, the cut of each root folder to its first entries, the empty map."""

import unittest

from codebase_map import render

HEADER = (
    "Codebase map (every entry at this repository's root, and the first 6 entries of each folder under it;"
    " folders end in /; reuse what exists):"
)


class RenderTest(unittest.TestCase):
    def test_render(self):
        seven = ["cmd/", "internal/", "scripts/", "Makefile", "go.mod", "go.sum", "main.go"]
        rows = [
            ("every root entry, each root folder's entries indented under it, a file with none",
             [(".github/", ["workflows/"]), ("docs/", ["design/", "dev/", "README.md"]), ("Makefile", None)],
             HEADER + "\n.github/\n  workflows/\ndocs/\n  design/\n  dev/\n  README.md\nMakefile"),
            ("a folder holding exactly 6 entries lists them all",
             [("pfm/", seven[:6])], HEADER + "\npfm/\n  cmd/\n  internal/\n  scripts/\n  Makefile\n  go.mod\n  go.sum"),
            ("a folder holding 7 lists its first 6 and counts the rest",
             [("pfm/", seven)],
             HEADER + "\npfm/\n  cmd/\n  internal/\n  scripts/\n  Makefile\n  go.mod\n  go.sum\n  … 1 more"),
            ("a folder git lists no entry inside, such as a submodule, stands alone",
             [("deps/", []), ("README.md", None)], HEADER + "\ndeps/\nREADME.md"),
            ("no entry says so", [], "Codebase map: git lists no file in this repository's work tree."),
        ]
        for name, entries, want in rows:
            with self.subTest(name):
                self.assertEqual(render.render(entries), want)


if __name__ == "__main__":
    unittest.main()
