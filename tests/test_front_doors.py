"""Tests for the comment and Python front-door readers: the first prose line of the doc, else the no-doc marker."""

import unittest

from codebase_map import comment_doors, py_packages

NO_DOC = "(no front door doc)"


class LeadingCommentTest(unittest.TestCase):
    def test_leading_comment(self):
        rows = [
            ("a JSDoc block's first line", "/**\n * Web front door.\n * @module web\n */\nexport {};\n", "block", "Web front door."),
            ("a tag line before the prose is skipped", "/**\n * @packageDocumentation\n * The tools entry.\n */\n", "block",
             "The tools entry."),
            ("leading line comments", "// Line door.\n// More.\nexport {};\n", "block", "Line door."),
            ("a shebang before the block", "#!/usr/bin/env node\n/* Cli door. */\n", "block", "Cli door."),
            ("code before any comment", "export const x = 1; /* not a door */\n", "block", NO_DOC),
            ("a block never closed", "/* never closed\n", "block", NO_DOC),
            ("triple-slash directives before the doc", '/// <reference types="node" />\n/// <reference path="x.d.ts" />\n'
             "/** Typed door. */\n", "block", "Typed door."),
            ("an empty block", "/** */\nexport {};\n", "block", NO_DOC),
            ("Rust inner doc lines", "//! Crate door.\n//! More.\npub fn x() {}\n", "rust", "Crate door."),
            ("a plain Rust comment before the inner doc", "// not a doc\n//! Later.\n", "rust", NO_DOC),
        ]
        for name, text, style, want in rows:
            with self.subTest(name):
                self.assertEqual(comment_doors.leading_comment(text, style), want)


class DocstringLineTest(unittest.TestCase):
    def test_docstring_line(self):
        rows = [
            ("the docstring's first line", b'"""Tools.\n\nMore."""\n', "Tools."),
            ("a docstring opening on a blank line", b'"""\n    Indented first.\n"""\n', "Indented first."),
            ("a module with no docstring", b"x = 1\n", NO_DOC),
            ("an empty module", b"", NO_DOC),
            ("source ast rejects", b"def (:\n", "(front door unreadable: SyntaxError at line 1)"),
            ("source too deep for the parser", b"x = " + b"+".join([b"a"] * 200000) + b"\n", "(front door unreadable: RecursionError)"),
        ]
        for name, source, want in rows:
            with self.subTest(name):
                self.assertEqual(py_packages.docstring_line(source, "pkg/__init__.py"), want)


if __name__ == "__main__":
    unittest.main()
