"""Tests for the flights family the plugin ships: each agent, command and skill under its plugin name; the cast's
tiers; the one long-command wait; the lander's and the reviewer's computed review spawn and their kit; critical decisions to main; the
Sonnet foreman carrying the foreman manual whole; the tracer running the tracetree kit from the plugin;
and the codebase map reaching the agents it names."""

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
AGENT_NAMES = ["diff-checker", "foreman", "foreman-sonnet", "lander", "reviewer", "spec-checker", "speccer",
               "sub-tracer", "tracer", "usage-checker"]
COMMAND_NAMES = {"doctor": "flights:doctor", "spec": "flights:spec"}
SKILL_NAMES = {"lander-inventory": "lander-inventory", "tracer-use": "tracer-use", "tracetree": "tracetree"}

# The frontmatter lines in which the Sonnet foreman differs from the foreman, whole.
SONNET_FOREMAN_LINES = {
    "name": "name: foreman-sonnet\n",
    "description": "description: Builds clear work with a pattern to follow — the code has the pattern, the requirements "
                   "are settled. Pass what flights:foreman takes. main chat → here → main chat → flights:lander → gitter. "
                   "Returns DONE or PARTIAL, decisions, files, test lines, outside changes.\n",
    "model": "model: sonnet\n",
    "effort": "effort: high\n",
}
FOREMAN_KEYS = ["name", "description", "model", "effort", "effortControl", "tools"]
EFFORT_CONTROL = "effortControl:\n  floor: medium\n  ceiling: xhigh\n"
FOREMAN_TOOLS = ("tools: Read, Write, Edit, Bash, Skill, SendMessage, mcp__forward-compaction__forward_compaction, "
                 "mcp__forward-compaction__look_back\n")
KIT_CALL = "python3 -I ${CLAUDE_PLUGIN_ROOT}/skills/lander-inventory/lander-inventory.py "
TRACETREE_CALL = "python3 ${CLAUDE_PLUGIN_ROOT}/skills/tracetree/tracetree.py"
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
        want = {"flights:foreman", "flights:foreman-sonnet", "flights:lander"}
        self.assertEqual(hook.MAP_AGENT_TYPES, want)
        shipped = {f"flights:{name}" for name in AGENT_NAMES}
        self.assertEqual(hook.MAP_AGENT_TYPES - shipped, set(), f"{AGENTS}: a map agent type no agent carries")


class FlightContractsTest(unittest.TestCase):
    def test_cast_tiers(self):
        cast = {
            "foreman": ("opus", "medium"), "foreman-sonnet": ("sonnet", "high"), "lander": ("opus", "medium"),
            "diff-checker": ("opus", None), "spec-checker": ("sonnet", None), "usage-checker": ("haiku", None),
            "speccer": ("opus", "xhigh"), "reviewer": ("opus", "medium"),
            "tracer": ("sonnet", "high"), "sub-tracer": ("haiku", "low"),
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
            # effortControl lets auto-effort steer it at a failing test run; its tools line is the whole list it may
            # call, with no Agent tool and no effort buttons.
            self.assertEqual(keys, FOREMAN_KEYS, f"{agent(name)}: frontmatter keys")
        for key in FOREMAN_KEYS:
            with self.subTest(key):
                want = SONNET_FOREMAN_LINES.get(key, foreman[key])
                self.assertEqual(sonnet[key], want, f"{agent('foreman-sonnet')}: {key}")
        self.assertEqual(foreman["effortControl"], EFFORT_CONTROL, f"{agent('foreman')}: effortControl")
        self.assertEqual(foreman["tools"], FOREMAN_TOOLS, f"{agent('foreman')}: tools")

    def test_waits_stay_inside_the_prompt_cache(self):
        for name in ("foreman", "foreman-sonnet", "lander"):
            with self.subTest(name):
                body = text(name)
                self.assertIn("a timeout of at most 270 s", body, f"{agent(name)}: the foreground ceiling")
                self.assertIn("timeout 270 bash -c 'until [ -s \"$1\" ]", body, f"{agent(name)}: the repeated wait")

    def test_lander_spawns_its_computed_plan(self):
        lander = text("lander")
        self.assertIn(KIT_CALL, lander, f"{agent('lander')}: the inventory runs from the plugin's kit")
        kit = Path(KIT_CALL.split()[2].replace("${CLAUDE_PLUGIN_ROOT}", PLUGIN_DIR))
        self.assertTrue(kit.is_file(), f"{kit}: the inventory kit ships")
        self.assertTrue((kit.parent / "SKILL.md").is_file(), f"{kit.parent}: a skill folder holds SKILL.md")
        self.assertNotRegex(lander, r"/(Users|home)/", f"{agent('lander')}: no machine-absolute path")
        self.assertIn("ONE message spawning exactly the PLAN rows", lander, f"{agent('lander')}: the spawn is the plan")
        self.assertIn("ls-files --others --exclude-standard", lander, f"{agent('lander')}: reads untracked source")
        for child in ("diff-checker", "spec-checker", "usage-checker"):
            with self.subTest(child):
                self.assertIn(f"subagent_type: flights:{child}", lander, f"{agent('lander')}: spawns flights:{child}")
                head = parts(agent(child))[0]
                self.assertIn("include: [flights:lander, flights:reviewer]", head, f"{agent(child)}: visible to its two callers alone")
                self.assertRegex(head, CHILD_TOOLS, f"{agent(child)}: read-only tools, forward-compaction its only addition")

    def test_tracer_runs_the_plugin_kit(self):
        kit = Path(TRACETREE_CALL.split()[1].replace("${CLAUDE_PLUGIN_ROOT}", PLUGIN_DIR))
        self.assertTrue(kit.is_file(), f"{kit}: the tracetree kit ships")
        for path in (agent("tracer"), agent("sub-tracer"), SKILLS / "tracetree" / "SKILL.md", SKILLS / "tracer-use" / "SKILL.md"):
            with self.subTest(path.name):
                body = path.read_text(encoding="utf-8")
                self.assertIn(TRACETREE_CALL, body, f"{path}: the kit runs from the plugin")
                self.assertNotRegex(body, r"\$HOME/\.claude|/(Users|home)/", f"{path}: no path outside the plugin")
        self.assertIn('subagent_type: "flights:sub-tracer"', text("tracer"), f"{agent('tracer')}: spawns flights:sub-tracer")
        self.assertIn('subagent_type: "flights:sub-tracer"', text("sub-tracer"), f"{agent('sub-tracer')}: splits to flights:sub-tracer")
        for path in (agent("sub-tracer"), SKILLS / "tracetree" / "SKILL.md"):
            with self.subTest(path.name):
                self.assertIn("include: [flights:tracer, flights:sub-tracer]", parts(path)[0], f"{path}: visible to the tracers alone")
        # Every spawn of a shipped agent, in any agent or command, names it by its plugin name.
        spawns = [(path.name, name) for path in sorted([*AGENTS.glob("*.md"), *COMMANDS.glob("*.md")])
                  for name in re.findall(r'subagent_type: "?([\w:-]+)', path.read_text(encoding="utf-8"))]
        self.assertIn(("speccer.md", "flights:tracer"), spawns, "the speccer spawns the tracer")
        self.assertEqual([spawn for spawn in spawns if spawn[1] in AGENT_NAMES], [], "a shipped agent spawned by a bare name")

    def test_reviewer_spawns_its_computed_plan_and_writes_no_code(self):
        head, body = parts(agent("reviewer"))
        self.assertIn(KIT_CALL + "{TREE} {BASE} {HEAD} --own --cluster-lines 750 --max-diff-checkers 12 ", body,
                      f"{agent('reviewer')}: the plan comes from the lander's kit, cut for a review")
        self.assertIn("ONE message spawning exactly the PLAN rows", body, f"{agent('reviewer')}: the spawn is the plan")
        for child in ("diff-checker", "spec-checker", "usage-checker"):
            with self.subTest(child):
                self.assertIn(f"subagent_type: flights:{child}", body, f"{agent('reviewer')}: spawns flights:{child}")
        # Read-only by its tools: Write for the report alone, no Edit.
        self.assertEqual(blocks(head)["tools"], "tools: Read, Write, Bash, Agent, mcp__forward-compaction__forward_compaction, "
                         "mcp__forward-compaction__look_back\n", f"{agent('reviewer')}: tools")
        self.assertNotRegex(body, r"/(Users|home)/", f"{agent('reviewer')}: no machine-absolute path")

    def test_critical_decisions_go_to_main(self):
        for name in ("foreman", "lander"):
            with self.subTest(name):
                body = text(name)
                self.assertIn("never ask the user", body, f"{agent(name)}: decides, never asks")
                self.assertIn('SendMessage(to: "main")', body, f"{agent(name)}: a critical decision goes to main")


if __name__ == "__main__":
    unittest.main()
