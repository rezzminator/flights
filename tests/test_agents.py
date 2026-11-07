"""Tests for the flights family the plugin ships: each agent, command and skill under its plugin name; the cast's
tiers; the one long-command wait; the lander's computed review spawn and its kit; critical decisions to main; the
Sonnet foreman carrying the foreman manual whole; and the codebase map reaching the agents it names."""

import os
import re
import unittest
from pathlib import Path

from codebase_map import hook
from tests import PLUGIN_DIR

PLUGIN = Path(PLUGIN_DIR)
AGENTS = PLUGIN / "agents"
COMMANDS = PLUGIN / "commands"
SKILLS = PLUGIN / "skills"

# Claude Code names a plugin agent `flights:{frontmatter name}`, a command `flights:{file name}` shown as its
# frontmatter name when that already starts with `flights:`, a skill `flights:{folder}`.
AGENT_NAMES = ["foreman", "foreman-sonnet", "hunter", "lander", "spec-walker", "speccer", "sub-lander"]
COMMAND_NAMES = {"doctor": "flights:doctor", "spec": "flights:spec"}
SKILL_NAMES = {"lander-inventory": "lander-inventory"}

# The frontmatter lines in which the Sonnet foreman differs from the foreman, whole.
SONNET_FOREMAN_LINES = {
    "name": "name: foreman-sonnet\n",
    "description": "description: Builds clear work with a pattern to follow — the code has the pattern, the requirements "
                   "are settled. Pass what flights:foreman takes. main chat → here → main chat → flights:lander → gitter. "
                   "Returns DONE or PARTIAL, decisions, files, test lines, outside changes.\n",
    "model": "model: sonnet\n",
}
FOREMAN_KEYS = ["name", "description", "model", "effort", "effortControl"]
EFFORT_CONTROL = "effortControl:\n  floor: medium\n  ceiling: xhigh\n"
KIT_CALL = "python3 -I ${CLAUDE_PLUGIN_ROOT}/skills/lander-inventory/lander-inventory.py "
CHILD_TOOLS = r"(?m)^tools: Read, Grep, Glob, Bash(, mcp__forward-compaction__(forward_compaction|look_back))*$"


def parts(path):
    """The frontmatter and the body of a markdown file that opens with a `---` block."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise AssertionError(f"{path}: no frontmatter block")
    _, head, body = text.split("---\n", 2)
    return head, body


def blocks(head):
    """Each top-level frontmatter key, in order, with its whole block: the key's line and its indented lines."""
    out = {}
    key = None
    for line in head.splitlines(keepends=True):
        if line[:1] not in (" ", "\t"):
            key = line.split(":", 1)[0]
            out[key] = ""
        out[key] += line
    return out


def tiers(path):
    return dict(re.findall(r"(?m)^(model|effort): (\S+)$", parts(path)[0]))


def agent(name):
    return AGENTS / f"{name}.md"


def text(name):
    return agent(name).read_text(encoding="utf-8")


class ShippedNamesTest(unittest.TestCase):
    def test_family_under_plugin_names(self):
        self.assertEqual(sorted(p.stem for p in AGENTS.glob("*.md")), AGENT_NAMES, f"{AGENTS}: the agent roster")
        for name in AGENT_NAMES:
            with self.subTest(name):
                self.assertEqual(blocks(parts(agent(name))[0])["name"], f"name: {name}\n", f"{agent(name)}: name")
        self.assertEqual(sorted(p.stem for p in COMMANDS.glob("**/*.md")), sorted(COMMAND_NAMES), f"{COMMANDS}: commands")
        for stem, want in COMMAND_NAMES.items():
            with self.subTest(stem):
                path = COMMANDS / f"{stem}.md"
                self.assertEqual(blocks(parts(path)[0])["name"], f"name: {want}\n", f"{path}: name")
        self.assertEqual(sorted(p.parent.name for p in SKILLS.glob("*/SKILL.md")), sorted(SKILL_NAMES), f"{SKILLS}: skills")
        for folder, want in SKILL_NAMES.items():
            with self.subTest(folder):
                path = SKILLS / folder / "SKILL.md"
                self.assertEqual(blocks(parts(path)[0])["name"], f"name: {want}\n", f"{path}: name")

    def test_map_reaches_shipped_agents(self):
        want = {"flights:foreman", "flights:foreman-sonnet", "flights:lander", "flights:hunter", "flights:sub-lander"}
        self.assertEqual(hook.MAP_AGENT_TYPES, want)
        shipped = {f"flights:{name}" for name in AGENT_NAMES}
        self.assertEqual(hook.MAP_AGENT_TYPES - shipped, set(), f"{AGENTS}: a map agent type no agent carries")


class FlightContractsTest(unittest.TestCase):
    def test_cast_tiers(self):
        cast = {
            "foreman": ("opus", "high"), "foreman-sonnet": ("sonnet", "high"), "lander": ("opus", "medium"),
            "hunter": ("opus", None), "spec-walker": ("sonnet", None), "sub-lander": ("haiku", None),
            "speccer": ("opus", "xhigh"),
        }
        self.assertEqual(sorted(cast), AGENT_NAMES, "every shipped agent has its tier")
        for name, (model, effort) in cast.items():
            with self.subTest(name):
                want = {"model": model, **({"effort": effort} if effort else {})}
                self.assertEqual(tiers(agent(name)), want, f"{agent(name)}: tier")

    def test_sonnet_foreman_carries_the_foreman_manual(self):
        foreman_head, foreman_body = parts(agent("foreman"))
        sonnet_head, sonnet_body = parts(agent("foreman-sonnet"))
        self.assertEqual(sonnet_body, foreman_body, f"{agent('foreman-sonnet')}: the body drifted from {agent('foreman')}")
        foreman, sonnet = blocks(foreman_head), blocks(sonnet_head)
        for name, keys in (("foreman", list(foreman)), ("foreman-sonnet", list(sonnet))):
            # effortControl lets auto-effort steer it; no tools line, so it inherits every tool and the effort buttons.
            self.assertEqual(keys, FOREMAN_KEYS, f"{agent(name)}: frontmatter keys")
        for key in FOREMAN_KEYS:
            with self.subTest(key):
                want = SONNET_FOREMAN_LINES.get(key, foreman[key])
                self.assertEqual(sonnet[key], want, f"{agent('foreman-sonnet')}: {key}")
        self.assertEqual(foreman["effortControl"], EFFORT_CONTROL, f"{agent('foreman')}: effortControl")

    def test_one_blocking_wait_past_ten_minutes(self):
        for name in ("foreman", "foreman-sonnet", "lander"):
            with self.subTest(name):
                body = text(name)
                self.assertIn("longer than 10 minutes", body, f"{agent(name)}: the long-command threshold")
                self.assertIn("timeout {s} bash -c 'until [ -s \"$1\" ]", body, f"{agent(name)}: the one blocking wait")

    def test_lander_spawns_its_computed_plan(self):
        lander = text("lander")
        self.assertIn(KIT_CALL, lander, f"{agent('lander')}: the inventory runs from the plugin's kit")
        kit = Path(KIT_CALL.split()[2].replace("${CLAUDE_PLUGIN_ROOT}", PLUGIN_DIR))
        self.assertTrue(kit.is_file(), f"{kit}: the inventory kit ships")
        self.assertTrue((kit.parent / "SKILL.md").is_file(), f"{kit.parent}: a skill folder holds SKILL.md")
        self.assertNotRegex(lander, r"/(Users|home)/", f"{agent('lander')}: no machine-absolute path")
        self.assertIn("ONE message spawning exactly the PLAN rows", lander, f"{agent('lander')}: the spawn is the plan")
        self.assertIn("ls-files --others --exclude-standard", lander, f"{agent('lander')}: reads untracked source")
        for child in ("hunter", "spec-walker", "sub-lander"):
            with self.subTest(child):
                self.assertIn(f"subagent_type: flights:{child}", lander, f"{agent('lander')}: spawns flights:{child}")
                head = parts(agent(child))[0]
                self.assertIn("include: [flights:lander]", head, f"{agent(child)}: visible to the lander alone")
                self.assertRegex(head, CHILD_TOOLS, f"{agent(child)}: read-only tools, forward-compaction its only addition")

    def test_critical_decisions_go_to_main(self):
        for name in ("foreman", "lander"):
            with self.subTest(name):
                body = text(name)
                self.assertIn("never ask the user", body, f"{agent(name)}: decides, never asks")
                self.assertIn('SendMessage(to: "main")', body, f"{agent(name)}: a critical decision goes to main")


if __name__ == "__main__":
    unittest.main()
