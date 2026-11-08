"""Tests for the hook end to end: a throwaway git repository with tracked, untracked, ignored and deleted files, a
submodule and a nested repository, read through the real entry point and the real git."""

import contextlib
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

import codebase_map
from codebase_map import cache, command, hook
from codebase_map.plugin_log import PluginLog
from tests import PACKAGE_DIR

HEADER = (
    "Codebase map (every entry at this repository's root, and the first 6 entries of each folder under it;"
    " folders end in /; reuse what exists):"
)
TREE = "\n".join([
    HEADER,
    ".github/", "  workflows/",
    "deps/", "  lib/",
    "docs/", "  design/", "  dev/", "  README.md", "  draft.md",
    "pfm/", "  cmd/", "  internal/", "  scripts/", "  Makefile", "  a.txt", "  b.txt", "  … 3 more",
    "sm/",
    "tools/", "  scratch/",
    ".gitignore", "Makefile", "README.md", "notes.txt",
])
FIXTURE = {
    ".gitignore": "ignored.log\n",
    ".github/workflows/ci.yml": "name: ci\n",
    "Makefile": "all:\n",
    "README.md": "# fixture\n",
    "docs/README.md": "docs\n",
    "docs/design/a.md": "a\n",
    "docs/dev/b.md": "b\n",
    "docs/old.md": "deleted from the work tree after the commit\n",
    "gone/file.txt": "deleted from the work tree after the commit\n",
    "pfm/cmd/pfm/main.go": "package main\n",
    "pfm/internal/x.go": "package internal\n",
    "pfm/scripts/s.sh": "true\n",
    "pfm/Makefile": "all:\n",
    "pfm/go.mod": "module example.com/pfm\n",
    "pfm/go.sum": "",
    "pfm/a.txt": "", "pfm/b.txt": "", "pfm/c.txt": "",
}
UNTRACKED = {"notes.txt": "listed\n", "ignored.log": "ignored, never listed\n", "docs/draft.md": "listed\n"}
# A submodule's gitlink names a commit the fixture never fetches: git lists the path, the work tree holds an empty folder.
GITLINK = "160000,1111111111111111111111111111111111111111,{}"


def write_tree(root, files):
    for path, text in files.items():
        os.makedirs(os.path.dirname(os.path.join(root, path)), exist_ok=True)
        with open(os.path.join(root, path), "w") as handle:
            handle.write(text)


class HookTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if shutil.which("git") is None:
            raise RuntimeError("git must be on PATH: the hook tests read the fixture with the real git")

    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp(prefix="flights-map-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        self.addCleanup(self.wait_for_builds)
        self.env = {
            "PATH": os.environ["PATH"], "HOME": os.path.join(self.root, "home"),
            "XDG_CACHE_HOME": os.path.join(self.root, "cache"), "PLUGIN_LOG_DIR": os.path.join(self.root, "logs"),
            "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CEILING_DIRECTORIES": self.root,
        }
        self.repo = self.make_repo("repo", FIXTURE)
        for gitlink in ("deps/lib", "sm"):
            os.makedirs(os.path.join(self.repo, gitlink))
            self.git(self.repo, "update-index", "--add", "--cacheinfo", GITLINK.format(gitlink))
        self.git(self.repo, "commit", "-q", "-m", "submodules")
        os.remove(os.path.join(self.repo, "docs", "old.md"))
        shutil.rmtree(os.path.join(self.repo, "gone"))
        write_tree(self.repo, UNTRACKED)
        self.git(self.repo, "init", "-q", os.path.join(self.repo, "tools", "scratch"))
        self.head = self.git(self.repo, "rev-parse", "HEAD")

    def wait_for_builds(self):
        # A build still running when its hook answered finishes before the fixture it reads is removed.
        while command.STARTED:
            command.STARTED.pop().wait(timeout=30)

    def git(self, cwd, *args):
        return subprocess.run(["git", "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid", *args],
                              cwd=cwd, env=self.env, check=True, capture_output=True, text=True).stdout.strip()

    def make_repo(self, name, files, commit=True):
        repo = os.path.join(self.root, name)
        os.makedirs(repo)
        self.git(repo, "init", "-q")
        write_tree(repo, files)
        if commit:
            self.git(repo, "add", "-A")
            self.git(repo, "commit", "-q", "-m", "fixture")
        return repo

    def call(self, stdin):
        done = subprocess.run([sys.executable, "-I", "-B", PACKAGE_DIR], input=stdin, env=self.env,
                              capture_output=True, text=True, timeout=30)
        self.assertEqual(done.returncode, 0, done.stderr)
        return done.stdout

    def respond(self, cwd, env=None, deadline=None):
        payload = {"hook_event_name": "SessionStart", "source": "startup", "cwd": cwd}
        log = PluginLog("flights", os.path.join(self.root, "logs", "flights"))
        out = hook.respond(payload, env or self.env, time.monotonic() + 30 if deadline is None else deadline, log)
        return None if out is None else json.loads(out)["hookSpecificOutput"]["additionalContext"]

    def test_round_trip(self):
        outside = os.path.join(self.root, "not-a-repo")
        os.makedirs(outside)
        subagent = {"hook_event_name": "SubagentStart", "cwd": self.repo, "agent_id": "a1"}
        rows = [
            ("the main chat at startup gets the tree",
             {"hook_event_name": "SessionStart", "source": "startup", "cwd": self.repo}, ("SessionStart", TREE)),
            ("the main chat in a subfolder gets the same tree, from the repository's root",
             {"hook_event_name": "SessionStart", "source": "resume", "cwd": os.path.join(self.repo, "pfm", "cmd")},
             ("SessionStart", TREE)),
            ("a flights:foreman gets the tree at its start", {**subagent, "agent_type": "flights:foreman"},
             ("SubagentStart", TREE)),
            ("a general-purpose sub-agent gets nothing at its start", {**subagent, "agent_type": "general-purpose"}, None),
            ("a flights:lander's own session start after its compaction gets the tree",
             {**subagent, "hook_event_name": "SessionStart", "source": "compact", "agent_type": "flights:lander"},
             ("SessionStart", TREE)),
            ("a general-purpose sub-agent's own session start gets nothing",
             {**subagent, "hook_event_name": "SessionStart", "source": "compact", "agent_type": "general-purpose"}, None),
            ("outside a git repository the main chat gets nothing",
             {"hook_event_name": "SessionStart", "source": "startup", "cwd": outside}, None),
        ]
        for name, payload, want in rows:
            with self.subTest(name):
                out = self.call(json.dumps(payload))
                expected = "" if want is None else {"hookSpecificOutput": {"hookEventName": want[0], "additionalContext": want[1]}}
                self.assertEqual(json.loads(out) if out else out, expected)
        status = self.git(self.repo, "status", "--porcelain", "--ignore-submodules=none")
        self.assertEqual(status, "D docs/old.md\n D gone/file.txt\n?? docs/draft.md\n?? notes.txt\n?? tools/",
                         "building the map changed the work tree")

    def test_payload_not_utf8_is_said(self):
        # In process: a strict UTF-8 stdin, as under a UTF-8 locale, which -I keeps PYTHONIOENCODING from forcing.
        stdin = io.TextIOWrapper(io.BytesIO(b"\xff{"), encoding="utf-8", errors="strict")
        out = io.StringIO()
        with mock.patch.dict(os.environ, self.env, clear=True), mock.patch("sys.stdin", stdin), \
                contextlib.redirect_stdout(out):
            self.assertEqual(codebase_map.main([]), 0)
        self.assertEqual(out.getvalue(), "Codebase map unavailable: the hook payload is not a JSON object"
                         " ('utf-8' codec can't decode byte 0xff in position 0: invalid start byte)\n")

    def test_unreadable_payload_is_said_and_logged(self):
        self.assertEqual(self.call("not json"),
                         "Codebase map unavailable: the hook payload is not a JSON object"
                         " (Expecting value: line 1 column 1 (char 0))\n")
        rows = self.log_rows("errors.jsonl")
        for row in rows:
            row.pop("ts")
        self.assertEqual(rows, [{
            "plugin": "flights", "level": "error", "event": "payload-unreadable",
            "msg": "Codebase map unavailable: the hook payload is not a JSON object (Expecting value: line 1 column 1 (char 0))",
            "where": "__init__.py#main", "detail": {"bytes": 8},
        }])

    def log_rows(self, level_file):
        path = os.path.join(self.root, "logs", "flights", level_file)
        if not os.path.exists(path):
            return []
        with open(path) as handle:
            return [json.loads(line) for line in handle]

    def test_cache_hit_runs_no_build(self):
        # A 0.2.0 entry, one (folder, synopsis) pair per package, under its own key and under this key without the
        # format: neither is read; the miss rebuilds the second in place, and the next start reads the tree back.
        old = {"toplevel": self.repo, "head": self.head, "entries": [["docs", "Package docs."]]}
        old_key = hashlib.sha256(f"1\0{self.repo}\0{self.head}".encode()).hexdigest()[:40]
        path = cache.cache_path(self.env, self.repo, self.head)
        os.makedirs(os.path.dirname(path))
        for each in (os.path.join(os.path.dirname(path), f"{old_key}.json"), path):
            with open(each, "w") as handle:
                json.dump(old, handle)
        self.assertEqual(self.respond(self.repo), TREE)
        self.assertEqual(self.respond(self.repo), TREE)
        self.assertEqual([row["event"] for row in self.log_rows("debug.jsonl")], ["cache-miss", "map-built", "cache-hit"])

    def test_miss_past_the_deadline_builds_for_the_next_start(self):
        self.assertEqual(self.respond(self.repo, deadline=time.monotonic()),
                         f"Codebase map unavailable: the map for commit {self.head[:12]} is still building;"
                         " it goes on in the background and is ready at the next start")
        path = cache.cache_path(self.env, self.repo, self.head)
        until = time.monotonic() + 30
        while not os.path.exists(path):
            self.assertLess(time.monotonic(), until, f"the background build never wrote {path}")
            time.sleep(0.05)
        self.assertEqual(self.respond(self.repo), TREE)

    def test_unavailable(self):
        unborn = self.make_repo("unborn", {"a.txt": ""}, commit=False)
        # git's own wording differs between versions: a git failing ls-files with one fixed message stands in for it.
        failing = os.path.join(self.root, "bin-failing-ls-files")
        os.makedirs(failing)
        with open(os.path.join(failing, "git"), "w") as handle:
            handle.write(f'#!/bin/sh\n[ "$1" = ls-files ] && {{ echo "fatal: index file corrupt" >&2; exit 128; }}\n'
                         f'exec "{shutil.which("git")}" "$@"\n')
        os.chmod(os.path.join(failing, "git"), 0o755)
        nogit = {**self.env, "PATH": os.path.join(self.root, "bin-without-git")}
        rows = [
            ("a repository with no commit", unborn, self.env,
             "Codebase map unavailable: the repository has no commit yet, and the map is kept per commit"),
            ("git failing to list the paths", self.repo, {**self.env, "PATH": failing},
             "Codebase map unavailable: git ls-files failed (exit 128): fatal: index file corrupt"),
            ("no git on PATH", self.repo, nogit, "Codebase map unavailable: git is not on PATH"),
        ]
        for name, cwd, env, want in rows:
            with self.subTest(name):
                self.assertEqual(self.respond(cwd, env), want)
        # A build's own failure is logged by the build, before the hook that read it logs the unavailable map.
        self.assertEqual([row["event"] for row in self.log_rows("errors.jsonl")],
                         ["map-unavailable", "map-build-failed", "map-unavailable", "map-unavailable"])


if __name__ == "__main__":
    unittest.main()
