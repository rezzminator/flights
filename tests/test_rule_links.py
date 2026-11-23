"""Tests for the rule-links hook end to end: the real entry point run as Claude Code runs it, against a throwaway
config folder, with the shipped rules folder or a fixture plugin root."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from tests import PLUGIN_DIR

ENTRY = os.path.join(PLUGIN_DIR, "rule_links")
PAYLOAD = json.dumps({"hook_event_name": "SessionStart", "session_id": "s-rules", "source": "startup"})


def context(text: str) -> str:
    return json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}}) + "\n"


class RuleLinksTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="flights-rule-links-")
        self.addCleanup(shutil.rmtree, self.root, True)
        self.config = os.path.join(self.root, "config")
        self.rules = os.path.join(self.config, "rules")
        self.plugin = os.path.join(self.root, "plugin")
        self.logs = os.path.join(self.root, "logs")
        for stem in ("coding", "testing"):
            os.makedirs(os.path.join(self.plugin, "rules"), exist_ok=True)
            with open(os.path.join(self.plugin, "rules", stem + ".md"), "w") as out:
                out.write(f"# {stem}\n")
        self.env = {"PATH": os.environ.get("PATH", ""), "HOME": os.path.join(self.root, "home"),
                    "CLAUDE_CONFIG_DIR": self.config, "CLAUDE_PLUGIN_ROOT": self.plugin, "PLUGIN_LOG_DIR": self.logs}

    def run_hook(self, env=None):
        done = subprocess.run([sys.executable, "-I", "-B", ENTRY], input=PAYLOAD.encode(), env=env or self.env,
                              capture_output=True, timeout=30)
        self.assertEqual(0, done.returncode, done.stderr.decode())
        return done.stdout.decode()

    def source(self, stem, plugin=None):
        return os.path.join(plugin or self.plugin, "rules", stem + ".md")

    def links(self):
        """Every entry of the rules folder: a link as `name -> target`, anything else as `name (file|folder)`."""
        rows = []
        for name in sorted(os.listdir(self.rules)):
            path = os.path.join(self.rules, name)
            if os.path.islink(path):
                rows.append(f"{name} -> {os.readlink(path)}")
            else:
                rows.append(f"{name} ({'folder' if os.path.isdir(path) else 'file'})")
        return rows

    def test_fresh_install_links_the_shipped_rules_then_stays_silent(self):
        env = dict(self.env)
        del env["CLAUDE_PLUGIN_ROOT"]  # the package's own plugin folder: the three shipped rules
        self.assertEqual(context(f"Flights rules linked into {self.rules}: flights-coding.md, flights-life-cycle.md,"
                                 " flights-testing.md; they load from the next chat."), self.run_hook(env))
        want = [f"flights-{stem}.md -> {self.source(stem, PLUGIN_DIR)}" for stem in ("coding", "life-cycle", "testing")]
        self.assertEqual(want, self.links())
        self.assertEqual("", self.run_hook(env))
        self.assertEqual(want, self.links())

    def test_a_link_into_another_plugin_root_is_repointed(self):
        os.makedirs(self.rules)
        os.symlink("/old/plugin/rules/coding.md", os.path.join(self.rules, "flights-coding.md"))
        os.symlink(self.source("testing"), os.path.join(self.rules, "flights-testing.md"))
        self.assertEqual(context(f"Flights rules linked into {self.rules}: flights-coding.md; they load from the next"
                                 " chat."), self.run_hook())
        self.assertEqual([f"flights-coding.md -> {self.source('coding')}",
                          f"flights-testing.md -> {self.source('testing')}"], self.links())

    def test_a_regular_file_on_a_flights_name_stays_and_is_reported(self):
        os.makedirs(self.rules)
        own = os.path.join(self.rules, "flights-coding.md")
        with open(own, "wb") as out:
            out.write(b"my own coding rule\n")
        self.assertEqual(context(f"Flights rules not installed: {own} is not a symlink, left untouched; move it aside"
                                 f" to let flights link it. Flights rules linked into {self.rules}: flights-testing.md;"
                                 " they load from the next chat."), self.run_hook())
        with open(own, "rb") as kept:
            self.assertEqual(b"my own coding rule\n", kept.read())
        self.assertEqual(["flights-coding.md (file)", f"flights-testing.md -> {self.source('testing')}"], self.links())
        with open(os.path.join(self.logs, "flights", "errors.jsonl")) as log:
            row = json.loads(log.readline())
        self.assertEqual(("error", "rules-not-installed", [own], "s-rules"),
                         (row["level"], row["event"], row["detail"]["kept"], row["session"]))

    def test_a_plugin_whose_shared_package_cannot_load_is_said(self):
        lone = os.path.join(self.root, "lone")
        shutil.copytree(ENTRY, os.path.join(lone, "rule_links"))  # no codebase_map beside it
        done = subprocess.run([sys.executable, "-I", "-B", os.path.join(lone, "rule_links")], input=PAYLOAD.encode(),
                              env=self.env, capture_output=True, timeout=30)
        self.assertEqual(0, done.returncode, done.stderr.decode())
        self.assertEqual(context("Flights rules not installed: the rule links cannot load: ModuleNotFoundError: No module"
                                 " named 'codebase_map'"), done.stdout.decode())
        self.assertFalse(os.path.lexists(self.rules))

    def test_a_stale_flights_link_goes_and_the_users_own_entries_stay(self):
        os.makedirs(self.rules)
        for stem in ("coding", "testing"):
            os.symlink(self.source(stem), os.path.join(self.rules, f"flights-{stem}.md"))
        os.symlink("/old/plugin/rules/old.md", os.path.join(self.rules, "flights-old.md"))
        os.symlink("/somewhere/my-rule.md", os.path.join(self.rules, "my-rule.md"))
        with open(os.path.join(self.rules, "mine.md"), "w") as out:
            out.write("mine\n")
        os.makedirs(os.path.join(self.rules, "flights-folder.md"))
        self.assertEqual(context(f"Flights rules removed from {self.rules}: flights-old.md; the change loads from the"
                                 " next chat."), self.run_hook())
        self.assertEqual([f"flights-coding.md -> {self.source('coding')}", "flights-folder.md (folder)",
                          f"flights-testing.md -> {self.source('testing')}", "mine.md (file)",
                          "my-rule.md -> /somewhere/my-rule.md"], self.links())

    def test_the_config_folder_is_claude_config_dir_else_home(self):
        cases = [("CLAUDE_CONFIG_DIR set", self.config, self.config),
                 ("only HOME", None, os.path.join(self.env["HOME"], ".claude"))]
        for name, config, want in cases:
            with self.subTest(name):
                env = dict(self.env)
                if config is None:
                    del env["CLAUDE_CONFIG_DIR"]
                rules = os.path.join(want, "rules")
                self.assertEqual(context(f"Flights rules linked into {rules}: flights-coding.md, flights-testing.md;"
                                         " they load from the next chat."), self.run_hook(env))
                self.assertEqual(self.source("coding"), os.readlink(os.path.join(rules, "flights-coding.md")))

    def test_an_unwritable_rules_folder_is_said_and_logged(self):
        os.makedirs(self.rules)
        os.chmod(self.rules, 0o555)
        self.addCleanup(os.chmod, self.rules, 0o755)
        link = os.path.join(self.rules, "flights-coding.md")
        line = f"Flights rules not installed: could not link {link}: Permission denied"
        self.assertEqual(context(line), self.run_hook())
        self.assertEqual([], self.links())
        with open(os.path.join(self.logs, "flights", "errors.jsonl")) as log:
            row = json.loads(log.readline())
        self.assertEqual(("error", "rules-not-installed", line, "s-rules"),
                         (row["level"], row["event"], row["msg"], row["session"]))

    def test_a_plugin_without_its_rules_folder_is_said(self):
        shutil.rmtree(os.path.join(self.plugin, "rules"))
        self.assertEqual(context("Flights rules not installed: the plugin's rules folder"
                                 f" {os.path.join(self.plugin, 'rules')} cannot be read: No such file or directory"),
                         self.run_hook())


if __name__ == "__main__":
    unittest.main()
