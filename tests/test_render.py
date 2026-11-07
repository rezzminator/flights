"""Tests for codebase_map.render: order by read heat and the session's folder, the synopsis cut, the empty map and the
budget footer."""

import unittest

from codebase_map import render

HEADER = (
    "Codebase map (no read history yet: the session's folder first, then by name; each package folder and the first"
    " line of its front door's doc; reuse what exists, and read a folder's front door before its other files):"
)
HOT = (
    "Codebase map (hottest first, by how often this repository's files are read, recent reads weighing more; each"
    " package folder and the first line of its front door's doc; reuse what exists, and read a folder's front door"
    " before its other files):"
)
H = len(HEADER)
LONG = [("a", "x" * 60), ("b", "y" * 60)]


class RenderTest(unittest.TestCase):
    def test_render(self):
        rows = [
            ("the top folder lists every folder by name, the root as ./",
             [("web", "W"), ("alpha", "A"), (".", "Root")], ".", 4000,
             HEADER + "\n./: Root\nalpha/: A\nweb/: W"),
            ("the session's folder and its subfolders come first, a name sharing its prefix does not",
             [("alpha", "A"), ("tools", "T"), ("tools/nodoc", "(no front door doc)"), ("toolsx", "X")], "tools", 4000,
             HEADER + "\ntools/: T\ntools/nodoc/: (no front door doc)\nalpha/: A\ntoolsx/: X"),
            ("whitespace collapses to one line",
             [("a", "one\n   two")], ".", 4000, HEADER + "\na/: one two"),
            ("a synopsis at the cap is kept whole",
             [("a", "x" * 200)], ".", 4000, HEADER + "\na/: " + "x" * 200),
            ("a synopsis one past the cap is cut to it",
             [("a", "x" * 201)], ".", 4000, HEADER + "\na/: " + "x" * 199 + "…"),
            ("no package folder says so",
             [], ".", 4000,
             "Codebase map: this repository has no package folder"
             " (no Go package, Python package, index.ts/index.js or lib.rs/mod.rs is tracked)."),
            ("every line fits at exactly the budget",
             LONG, ".", H + 130, HEADER + "\na/: " + "x" * 60 + "\nb/: " + "y" * 60),
            ("one under the budget the last line gives way to a footer counting it",
             LONG, ".", H + 129, HEADER + "\na/: " + "x" * 60 + "\n(1 more package folder not listed)"),
            ("the first line and that footer fit at exactly the budget",
             LONG, ".", H + 100, HEADER + "\na/: " + "x" * 60 + "\n(1 more package folder not listed)"),
            ("one under that, the footer counts both",
             LONG, ".", H + 99, HEADER + "\n(2 more package folders not listed)"),
        ]
        for name, entries, cwd, budget, want in rows:
            with self.subTest(name):
                self.assertEqual(render.render(entries, cwd, budget), want)

    def test_render_by_heat(self):
        three = [("alpha", "A"), ("tools", "T"), ("web", "W")]
        rows = [
            ("the hottest folder first, a cold one after by the session's folder, then by name",
             three, {"web": 2.0, "alpha": 0.5}, "tools", 4000, HOT + "\nweb/: W\nalpha/: A\ntools/: T"),
            ("equal heat falls back to the session's folder, then the name",
             three, {"web": 1.0, "alpha": 1.0, "tools": 1.0}, "web", 4000, HOT + "\nweb/: W\nalpha/: A\ntools/: T"),
            ("heat only for folders off the map reads as no history",
             three, {"gone": 3.0}, "tools", 4000, HEADER + "\ntools/: T\nalpha/: A\nweb/: W"),
            ("zero heat reads as no history", three, {"web": 0.0}, ".", 4000, HEADER + "\nalpha/: A\ntools/: T\nweb/: W"),
            ("the budget cut drops the coldest folders",
             [("alpha", "x" * 60), ("tools", "y" * 60), ("web", "z" * 60)], {"web": 2.0, "tools": 1.0}, ".",
             len(HOT) + 67 + 69 + 35,
             HOT + "\nweb/: " + "z" * 60 + "\ntools/: " + "y" * 60 + "\n(1 more package folder not listed)"),
        ]
        for name, entries, heat, cwd, budget, want in rows:
            with self.subTest(name):
                self.assertEqual(render.render(entries, cwd, budget, heat), want)


if __name__ == "__main__":
    unittest.main()
