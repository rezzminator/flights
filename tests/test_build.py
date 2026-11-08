"""Tests for codebase_map.build, the port of ponytail's map: each expected value below is upstream's own answer, captured
once by running ponytail's hooks/ponytail-map.js (namesIn, its sort, buildMap) on the same input."""

import os
import shutil
import tempfile
import unittest

from codebase_map import build


class NamesInTest(unittest.TestCase):
    def test_names_in(self):
        rows = [
            ("a line ending in a bare \\r starts a line, as JS's multiline ^ reads it",
             "a.py", "def a():\r    pass\rdef b():\r", ["a", "b"]),
            ("a line ending in \\u2028 starts a line", "a.py", "x = 1\u2028def c():\n", ["c"]),
            ("a no-break space is JS whitespace", "a.py", "def\u00a0d():\n", ["d"]),
            ("an export list is trimmed of JS whitespace, a byte order mark too", "a.ts", "export { \ufeffe, \u00a0f }\n",
             ["e", "f"]),
            ("a name is ASCII: a non-ASCII letter ends it", "a.py", "def \u00fcn():\ndef a\u00fc():\n", ["a"]),
            ("Rust: only pub items", "a.rs", "pub struct S;\npub async fn go_now() {}\nfn hidden() {}\n", ["S", "go_now"]),
            ("JVM: classes and interfaces, indented too", "A.java", "public static final class K {}\n  interface I {}\n",
             ["K", "I"]),
            ("Ruby: a leading run of blank lines and indentation", "a.rb", "\n\n  module M\n  class C::D\n", ["M", "C"]),
            ("a basename of two dots and an extension has that extension, as Node's extname says", "x/..py",
             "def g():\n", ["g"]),
            ("a basename that is only a dot and an extension has none", "x/.py", "def h():\n", []),
            ("a name found twice is listed once", "a.py", "def X():\nclass X:\n", ["X"]),
            ("Go: exported functions and methods, then types", "a.go",
             "func (r *R) Get() {}\nfunc lower() {}\ntype R struct{}\n", ["Get", "R"]),
            ("a file of no mapped language names nothing", "a.txt", "def t():\n", []),
        ]
        for name, path, text, want in rows:
            with self.subTest(name):
                self.assertEqual(build.names_in(path, text), want)


class SourceFilesTest(unittest.TestCase):
    def test_order(self):
        paths = ["b/x.py", "B/a.py", "a_b.py", "a-b.py", "a.b/c.py", "lib/z.py", "Lib/a.py", "x10.py", "x9.py", "a(b).py",
                 "a[b].py", "a@b.py", "a+b.py", "a$b.py", "core/m.go", "a b.py", "t/test_x.py", "t/x.spec.ts", "t/x.d.ts",
                 "node_modules/x.js", "t/notes.md", "caf\u00e9.py"]
        self.assertEqual(build.source_files(paths), [
            "core/m.go", "Lib/a.py", "lib/z.py", "a_b.py", "a-b.py", "a.b/c.py", "a(b).py", "a[b].py", "a@b.py",
            "a+b.py", "a$b.py", "B/a.py", "b/x.py", "x10.py", "x9.py",
        ])


class BuildMapTest(unittest.TestCase):
    def test_read(self):
        top = tempfile.mkdtemp(prefix="flights-build-")
        self.addCleanup(shutil.rmtree, top, True)
        os.makedirs(os.path.join(top, "src"))
        files = {
            # 13 code units, then 32762 two-unit characters: the 65536th unit is half of the last one, before `late`.
            "src/emoji.py": ("def early():\n" + "\U0001F600" * 32762 + "\ndef late():\n").encode("utf-8"),
            # The cut keeps `\ndef c` of `\ndef cut():`.
            "src/edge.py": ("x" * 65530 + "\ndef cut():\n").encode("utf-8"),
            "src/bad.py": b"def ok():\n\xff\xfe\xc3\ndef ok2():\n",
        }
        for path, data in files.items():
            with open(os.path.join(top, path), "wb") as handle:
                handle.write(data)
        self.assertEqual(build.build_map(top, list(files)),
                         "Codebase map (what already exists; reuse it, read a file only when you need its details):\n"
                         "src/: ok, ok2, c, early")


if __name__ == "__main__":
    unittest.main()
