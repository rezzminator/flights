"""Tests for the hook end to end: a throwaway git repository with a Go module, Python packages and comment front
doors, read through the real entry point, the real git and the real Go toolchain."""

import contextlib
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
from codebase_map import cache, command, heat, hook
from codebase_map.plugin_log import PluginLog
from tests import PACKAGE_DIR, PLUGIN_DIR

HOT = (
    "Codebase map (hottest first, by how often this repository's files are read, recent reads weighing more; each"
    " package folder and the first line of its front door's doc; reuse what exists, and read a folder's front door"
    " before its other files):"
)
HEADER = (
    "Codebase map (no read history yet: the session's folder first, then by name; each package folder and the first"
    " line of its front door's doc; reuse what exists, and read a folder's front door before its other files):"
)
LINES = {
    "alpha": "alpha/: Package alpha adds numbers.",
    "beta": "beta/: (no front door doc)",
    "engine": "engine/src/: Engine crate front door.",
    "linked": "linked/: (front door unreadable: linked/__init__.py points outside the repository)",
    "odd": "odd/: (front door unreadable: odd/index.ts is not a regular file)",
    "tools": "tools/: Tools for the fixture.",
    "nodoc": "tools/nodoc/: (no front door doc)",
    "web": "web/: Web front door for the fixture.",
}
MAP_AT_TOP = "\n".join([HEADER] + [LINES[k] for k in ("alpha", "beta", "engine", "linked", "odd", "tools", "nodoc", "web")])
MAP_IN_TOOLS = "\n".join([HEADER] + [LINES[k] for k in ("tools", "nodoc", "alpha", "beta", "engine", "linked", "odd", "web")])
FIXTURE = {
    # No go line: a go that may edit go.mod adds one, which the round trip's clean work tree rules out.
    "go.mod": "module example.com/fixture\n",
    "alpha/alpha.go": "// Package alpha adds numbers. It is a fixture.\npackage alpha\n",
    "beta/beta.go": "package beta\n",
    "tools/__init__.py": '"""Tools for the fixture.\n\nMore detail."""\n',
    "tools/nodoc/__init__.py": "",
    "web/index.ts": "/**\n * Web front door for the fixture.\n * @module web\n */\nexport {};\n",
    "engine/src/lib.rs": "//! Engine crate front door.\n//! More.\npub fn x() {}\n",
    ".hidden/__init__.py": '"""Hidden: never listed."""\n',
    "vendor/lib/__init__.py": '"""Vendored: never listed."""\n',
}
# Tracked symlinks as front doors: one leaving the repository, one naming a folder.
FIXTURE_LINKS = {"linked/__init__.py": os.devnull, "odd/index.ts": "../alpha"}


def write_tree(root, files):
    for path, text in files.items():
        os.makedirs(os.path.dirname(os.path.join(root, path)), exist_ok=True)
        with open(os.path.join(root, path), "w") as handle:
            handle.write(text)


class HookTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if shutil.which("go") is None or shutil.which("git") is None:
            raise RuntimeError("go and git must be on PATH: the hook tests read the fixture with the real toolchains")

    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp(prefix="flights-map-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        self.addCleanup(self.wait_for_builds)
        self.env = {
            "PATH": os.environ["PATH"], "HOME": os.path.join(self.root, "home"),
            "XDG_CACHE_HOME": os.path.join(self.root, "cache"), "PLUGIN_LOG_DIR": os.path.join(self.root, "logs"),
            "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CEILING_DIRECTORIES": self.root,
            "GOTOOLCHAIN": "local",
        }
        nogo = os.path.join(self.root, "bin-without-go")
        os.makedirs(nogo)
        os.symlink(shutil.which("git"), os.path.join(nogo, "git"))
        # The login shell is asked for go when PATH has none: one finding none, and one naming the real go.
        self.env_without_go = {**self.env, "PATH": nogo, "SHELL": self.login_shell("finds-none", "exit 1")}
        self.env_go_in_login_shell = {**self.env, "PATH": nogo,
                                      "SHELL": self.login_shell("finds-go", f"printf '%s\\n' '{shutil.which('go')}'")}
        self.repo = self.make_repo("repo", FIXTURE, links=FIXTURE_LINKS)
        write_tree(self.repo, {"extra/__init__.py": '"""Untracked: never listed."""\n'})

    def login_shell(self, name, body):
        path = os.path.join(self.root, "shells", name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as handle:
            handle.write(f"#!/bin/sh\n{body}\n")
        os.chmod(path, 0o755)
        return path

    def wait_for_builds(self):
        # A build or seed still running when its hook answered finishes before the fixture it reads is removed; a seed
        # the entry point's own process started is known by its marker.
        while command.STARTED:
            command.STARTED.pop().wait(timeout=30)
        heat_dir = os.path.join(self.root, "cache", "flights", "heat")
        until = time.monotonic() + 30
        while os.path.isdir(heat_dir) and any(name.endswith(".seeding") for name in os.listdir(heat_dir)):
            self.assertLess(time.monotonic(), until, f"a read heat seed never finished in {heat_dir}")
            time.sleep(0.05)

    def git(self, cwd, *args):
        subprocess.run(["git", "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid", *args],
                       cwd=cwd, env=self.env, check=True, capture_output=True)

    def make_repo(self, name, files, commit=True, links=None):
        repo = os.path.join(self.root, name)
        os.makedirs(repo)
        self.git(repo, "init", "-q")
        write_tree(repo, files)
        for path, target in (links or {}).items():
            os.makedirs(os.path.dirname(os.path.join(repo, path)), exist_ok=True)
            os.symlink(target, os.path.join(repo, path))
        if commit:
            self.git(repo, "add", "-A")
            self.git(repo, "commit", "-q", "-m", "fixture")
        return repo

    def call(self, stdin):
        done = subprocess.run([sys.executable, "-I", "-B", PACKAGE_DIR], input=stdin, env=self.env,
                              capture_output=True, text=True, timeout=30)
        self.assertEqual(done.returncode, 0, done.stderr)
        return done.stdout

    def respond(self, cwd, env, deadline=None):
        payload = {"hook_event_name": "SessionStart", "source": "startup", "cwd": cwd}
        log = PluginLog("flights", os.path.join(self.root, "logs", "flights"))
        out = hook.respond(payload, env, time.monotonic() + 30 if deadline is None else deadline, log)
        return None if out is None else json.loads(out)["hookSpecificOutput"]["additionalContext"]

    def test_round_trip(self):
        outside = os.path.join(self.root, "not-a-repo")
        os.makedirs(outside)
        subagent = {"hook_event_name": "SubagentStart", "cwd": self.repo, "agent_id": "a1"}
        rows = [
            ("the main chat at startup gets the map",
             {"hook_event_name": "SessionStart", "source": "startup", "cwd": self.repo}, ("SessionStart", MAP_AT_TOP)),
            ("the main chat in a package folder gets that folder first",
             {"hook_event_name": "SessionStart", "source": "resume", "cwd": os.path.join(self.repo, "tools")},
             ("SessionStart", MAP_IN_TOOLS)),
            ("a flights:foreman gets the map at its start", {**subagent, "agent_type": "flights:foreman"},
             ("SubagentStart", MAP_AT_TOP)),
            ("a general-purpose sub-agent gets nothing at its start", {**subagent, "agent_type": "general-purpose"}, None),
            ("a flights:lander's own session start after its compaction gets the map",
             {**subagent, "hook_event_name": "SessionStart", "source": "compact", "agent_type": "flights:lander"},
             ("SessionStart", MAP_AT_TOP)),
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
        status = subprocess.run(["git", "status", "--porcelain"], cwd=self.repo, env=self.env, capture_output=True,
                                text=True, check=True).stdout
        self.assertEqual(status, "?? extra/\n", "building the map changed the work tree")

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

    def debug_events(self):
        return [row["event"] for row in self.log_rows("debug.jsonl")]

    def test_cache_hit_runs_no_build(self):
        # Without go a miss cannot read the module: the map answering the same call later comes from the cache.
        # A cache file of another shape at the key is a miss, rebuilt in place.
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.repo, env=self.env, capture_output=True, text=True,
                              check=True).stdout.strip()
        path = cache.cache_path(self.env, self.repo, head)
        os.makedirs(os.path.dirname(path))
        with open(path, "w") as handle:
            json.dump({"toplevel": self.repo, "head": head, "entries": "not pairs"}, handle)
        self.assertEqual(self.respond(self.repo, self.env_without_go),
                         "Codebase map unavailable: go is not on PATH (nor in the login shell)")
        self.assertEqual(self.respond(self.repo, self.env), MAP_AT_TOP)
        self.assertEqual(self.respond(self.repo, self.env_without_go), MAP_AT_TOP)
        self.assertEqual(self.debug_events(), ["cache-miss", "cache-miss", "map-built", "cache-hit"])

    def test_go_from_the_login_shell(self):
        # A session started outside a login shell lacks the PATH its profile sets: the build asks the login shell.
        self.assertEqual(self.respond(self.repo, self.env_go_in_login_shell), MAP_AT_TOP)

    def test_read_recorder_runs_async(self):
        # Every Read of every loop runs the recorder: registered async, it never holds the read back.
        hooks_json = os.path.join(PLUGIN_DIR, "hooks", "hooks.json")
        with open(hooks_json) as handle:
            registered = json.load(handle)["hooks"]["PostToolUse"]
        self.assertEqual(registered, [{"matcher": "Read", "hooks": [{
            "type": "command", "command": 'python3 -I -B "${CLAUDE_PLUGIN_ROOT}/codebase_map"', "async": True, "timeout": 10,
        }]}], hooks_json)

    def test_reads_order_the_map(self):
        def read(rel):
            self.call(json.dumps({"hook_event_name": "PostToolUse", "tool_name": "Read", "cwd": self.repo,
                                  "session_id": "s1", "tool_use_id": "t", "tool_input": {"file_path": os.path.join(self.repo, rel)},
                                  "tool_response": {}}))
        for rel in ("web/index.ts", "web/index.ts", "web/index.ts", "tools/nodoc/__init__.py", "outside/../../x.go"):
            read(rel)
        out = json.loads(self.call(json.dumps({"hook_event_name": "SessionStart", "source": "startup", "cwd": self.repo})))
        rest = [LINES[k] for k in ("alpha", "beta", "engine", "linked", "odd", "tools")]
        self.assertEqual(out["hookSpecificOutput"]["additionalContext"],
                         "\n".join([HOT, LINES["web"], LINES["nodoc"], *rest]))
        # The session start seeds the store once from this config's transcripts (none here), keeping the recorded reads.
        self.wait_for_builds()
        with open(heat.store_path(self.env, self.repo)) as handle:
            stored = json.load(handle)
        self.assertEqual((stored["seeded"], sorted(stored["files"]), round(stored["files"]["web/index.ts"][0], 3)),
                         (True, ["tools/nodoc/__init__.py", "web/index.ts"], 3.0))

    def test_miss_past_the_deadline_builds_for_the_next_start(self):
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.repo, env=self.env, capture_output=True, text=True,
                              check=True).stdout.strip()
        self.assertEqual(self.respond(self.repo, self.env, deadline=time.monotonic()),
                         f"Codebase map unavailable: the map for commit {head[:12]} is still building;"
                         " it goes on in the background and is ready at the next start")
        path = cache.cache_path(self.env, self.repo, head)
        until = time.monotonic() + 30
        while not os.path.exists(path):
            self.assertLess(time.monotonic(), until, f"the background build never wrote {path}")
            time.sleep(0.05)
        self.assertEqual(self.respond(self.repo, self.env_without_go), MAP_AT_TOP)

    def test_unavailable(self):
        unborn = self.make_repo("unborn", {"a/__init__.py": ""}, commit=False)
        broken = self.make_repo("broken", {"bad/go.mod": "garbage line\n"})
        rows = [
            ("a repository with no commit", unborn,
             "Codebase map unavailable: the repository has no commit yet, and the map is kept per commit"),
            ("a module go list cannot read", broken,
             "Codebase map unavailable: go list in bad/ failed (exit 1): go.mod:1: unknown directive: garbage"),
        ]
        for name, cwd, want in rows:
            with self.subTest(name):
                self.assertEqual(self.respond(cwd, self.env), want)
        # A build's own failure is logged by the build, before the hook that read it logs the unavailable map.
        self.assertEqual([row["event"] for row in self.log_rows("errors.jsonl")],
                         ["map-unavailable", "map-build-failed", "map-unavailable"])


if __name__ == "__main__":
    unittest.main()
