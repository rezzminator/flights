"""Tests for codebase_map.go_packages.go_program: go from PATH, else from the user's login shell, else said missing."""

import os
import shutil
import tempfile
import unittest

from codebase_map import go_packages
from codebase_map.command import Unavailable


def executable(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as handle:
        handle.write(text)
    os.chmod(path, 0o755)
    return path


class GoProgramTest(unittest.TestCase):
    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp(prefix="flights-go-"))
        self.addCleanup(shutil.rmtree, self.root, True)

    def shell(self, name, out, code=0):
        # A fake login shell: it answers `-lc 'command -v go'` with out, as a profile adding go to PATH would.
        return executable(os.path.join(self.root, "shells", name), f"#!/bin/sh\nprintf '{out}'\nexit {code}\n")

    def test_go_program(self):
        on_path = executable(os.path.join(self.root, "bin", "go"), "#!/bin/sh\n")
        login_go = executable(os.path.join(self.root, "login", "go"), "#!/bin/sh\n")
        empty = os.path.join(self.root, "empty")
        os.makedirs(empty)
        missing_shell = os.path.join(self.root, "no-such-shell")
        rows = [
            ("go on PATH, the login shell never asked", {"PATH": os.path.dirname(on_path), "SHELL": missing_shell}, on_path),
            ("go only in the login shell", {"PATH": empty, "SHELL": self.shell("finds", login_go)}, login_go),
            ("a profile printing before the answer", {"PATH": empty, "SHELL": self.shell("chatty", f"welcome\\n{login_go}\\n")},
             login_go),
        ]
        for name, env, want in rows:
            with self.subTest(name):
                self.assertEqual(go_packages.go_program(self.root, env, 10), want)
        failing = [
            ("the login shell finds none", {"PATH": empty, "SHELL": self.shell("none", "", 1)},
             "go is not on PATH (nor in the login shell)"),
            ("the login shell names no file", {"PATH": empty, "SHELL": self.shell("relative", "go")},
             "go is not on PATH (nor in the login shell)"),
            ("the login shell cannot run", {"PATH": empty, "SHELL": missing_shell},
             f"go is not on PATH, and the login shell {missing_shell} could not be asked: {missing_shell} is not on PATH"),
        ]
        for name, env, want in failing:
            with self.subTest(name):
                with self.assertRaises(Unavailable) as raised:
                    go_packages.go_program(self.root, env, 10)
                self.assertEqual(str(raised.exception), want)


if __name__ == "__main__":
    unittest.main()
