"""Tests for codebase_map.seed: the project folder name, and the one-time seed from fixture transcripts."""

import json
import os
import shutil
import tempfile
import time
import unittest
from datetime import datetime, timezone

from codebase_map import heat, seed
from codebase_map.plugin_log import PluginLog

DAY = 86400
NOW = 1_800_000_000.0


def stamp(at):
    return datetime.fromtimestamp(at, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def tool_line(name, file_path, at, use_id, cwd, **more):
    return json.dumps({"type": "assistant", "timestamp": stamp(at), "cwd": cwd, "message": {"role": "assistant", "content": [
        {"type": "text", "text": "reading"},
        {"type": "tool_use", "id": use_id, "name": name, "input": {"file_path": file_path, **more}},
    ]}}) + "\n"


class SlugTest(unittest.TestCase):
    def test_slug(self):
        rows = [
            ("slashes and dots", "/srv/user/.proj", "-srv-user--proj"),
            ("every other mark", "/srv/a_b c+d", "-srv-a-b-c-d"),
        ]
        for name, path, want in rows:
            with self.subTest(name):
                self.assertEqual(seed.slug(path), want)


class SeedRunTest(unittest.TestCase):
    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp(prefix="flights-seed-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        self.top = os.path.join(self.root, "repo")
        os.makedirs(os.path.join(self.top, ".git"))
        self.config = os.path.join(self.root, "claude")
        self.env = {"XDG_CACHE_HOME": os.path.join(self.root, "cache"), "CLAUDE_CONFIG_DIR": self.config}
        self.logs = os.path.join(self.root, "logs")
        self.log = PluginLog("flights", self.logs)
        self.path = heat.store_path(self.env, self.top)

    def transcript(self, folder, name, lines):
        path = os.path.join(self.config, "projects", folder, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as handle:
            handle.write("".join(lines))
        os.utime(path, (NOW, NOW))
        return path

    def in_repo(self, rel):
        return os.path.join(self.top, rel)

    def stored(self):
        with open(self.path) as handle:
            return json.load(handle)

    def debug_rows(self):
        with open(os.path.join(self.logs, "debug.jsonl")) as handle:
            rows = [json.loads(line) for line in handle]
        for row in rows:
            row.pop("ts")
            row["detail"].pop("seconds")
        return rows

    def test_seed_counts_reads_by_age(self):
        name = seed.slug(self.top)
        self.transcript(name, "s1.jsonl", [
            tool_line("Read", self.in_repo("a/x.go"), NOW - 14 * DAY, "t1", self.top),
            tool_line("Read", "y.go", NOW - 28 * DAY, "t2", self.in_repo("b")),
            tool_line("Edit", self.in_repo("a/x.go"), NOW - DAY, "t3", self.top, old_string="Read"),
            tool_line("Read", self.in_repo("a/old.go"), NOW - 31 * DAY, "t4", self.top),
            tool_line("Read", os.path.join(self.root, "outside.go"), NOW - DAY, "t5", self.top),
            '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Read"',
        ])
        # A sub-agent transcript carrying the same call again, and a folder of the repository's subfolder.
        self.transcript(name, "s1/subagents/agent-a.jsonl", [tool_line("Read", self.in_repo("a/x.go"), NOW - 14 * DAY, "t1", self.top)])
        self.transcript(name + "-b", "s2.jsonl", [tool_line("Read", self.in_repo("b/y.go"), NOW - 14 * DAY, "t6", self.top)])
        # A sibling folder whose name only starts the same is not the repository's.
        self.transcript(name + "x", "s3.jsonl", [tool_line("Read", self.in_repo("a/x.go"), NOW, "t7", self.top)])
        seed.run(self.top, self.env, self.log, NOW, time.monotonic() + 30)
        self.assertEqual(self.stored(), {"format": 1, "toplevel": self.top, "created": NOW, "seeded": True,
                                         "files": {"a/x.go": [0.5, NOW], "b/y.go": [0.75, NOW]}})
        self.assertEqual(self.debug_rows(), [{
            "plugin": "flights", "level": "debug", "event": "heat-seeded",
            "msg": f"seeded the read heat of {self.top} from 3 transcripts", "where": "seed.py#run",
            "detail": {"toplevel": self.top, "transcripts": 3, "read": 3, "files": 2},
        }])

    def test_seed_counts_only_reads_before_the_store(self):
        # The recorder made the store seven days ago: the reads since are in it already.
        heat.update(self.path, self.top, NOW - 7 * DAY, self.log, lambda store: heat.add(store, "a/x.go", 1.0, NOW - 7 * DAY))
        self.transcript(seed.slug(self.top), "s1.jsonl", [
            tool_line("Read", self.in_repo("a/x.go"), NOW - 14 * DAY, "t1", self.top),
            tool_line("Read", self.in_repo("a/x.go"), NOW - 3 * DAY, "t2", self.top),
        ])
        seed.run(self.top, self.env, self.log, NOW, time.monotonic() + 30)
        self.assertEqual(self.stored(), {"format": 1, "toplevel": self.top, "created": NOW - 7 * DAY, "seeded": True,
                                         "files": {"a/x.go": [0.5 ** 0.5 + 0.5, NOW]}})

    def test_seed_skips_the_read_that_created_the_store(self):
        # The recorder made the store at the hook after Read t1, whose transcript stamp is a moment earlier.
        heat.update(self.path, self.top, NOW - DAY, self.log, lambda store: heat.add(store, "a/x.go", 1.0, NOW - DAY), "t1")
        self.transcript(seed.slug(self.top), "s1.jsonl", [
            tool_line("Read", self.in_repo("a/x.go"), NOW - DAY - 1, "t1", self.top),
            tool_line("Read", self.in_repo("b/y.go"), NOW - DAY - 2, "t2", self.top),
        ])
        seed.run(self.top, self.env, self.log, NOW, time.monotonic() + 30)
        self.assertEqual(self.stored()["files"], {"a/x.go": [1.0, NOW - DAY], "b/y.go": [0.5 ** ((DAY + 2) / (14 * DAY)), NOW]})

    def test_scan_passes_over_a_transcript_gone_since_listed(self):
        present = self.transcript(seed.slug(self.top), "s1.jsonl", [tool_line("Read", self.in_repo("a.go"), NOW, "t1", self.top)])
        gone = os.path.join(self.root, "gone.jsonl")
        counted, read, cut, unopened = seed.scan([gone, present], self.top, NOW - DAY, NOW + 1, NOW, time.monotonic() + 30)
        self.assertEqual((counted, read, cut), ({"t1": ("a.go", 1.0)}, 2, False))
        self.assertEqual(unopened, [f"{gone}: [Errno 2] No such file or directory: '{gone}'"])

    def test_seed_runs_once(self):
        heat.update(self.path, self.top, NOW, self.log, lambda store: setattr(store, "seeded", True))
        self.transcript(seed.slug(self.top), "s1.jsonl", [tool_line("Read", self.in_repo("a.go"), NOW - DAY, "t1", self.top)])
        seed.run(self.top, self.env, self.log, NOW, time.monotonic() + 30)
        self.assertEqual(self.stored(), {"format": 1, "toplevel": self.top, "created": NOW, "seeded": True, "files": {}})
        self.assertEqual([row["event"] for row in self.debug_rows()], ["heat-seed-dropped"])

    def test_seed_past_its_budget_keeps_what_it_counted(self):
        self.transcript(seed.slug(self.top), "s1.jsonl", [tool_line("Read", self.in_repo("a.go"), NOW - DAY, "t1", self.top)])
        seed.run(self.top, self.env, self.log, NOW, time.monotonic() - 1)
        self.assertEqual(self.stored(), {"format": 1, "toplevel": self.top, "created": NOW, "seeded": True, "files": {}})
        self.assertEqual(self.debug_rows(), [{
            "plugin": "flights", "level": "debug", "event": "heat-seed-cut",
            "msg": f"seeding the read heat of {self.top} stopped at its 15s budget after 0 of 1 transcripts",
            "where": "seed.py#run", "detail": {"toplevel": self.top, "transcripts": 1, "read": 0, "files": 0},
        }])

    def test_no_transcripts_seed_an_empty_store(self):
        seed.run(self.top, self.env, self.log, NOW, time.monotonic() + 30)
        self.assertEqual(self.stored(), {"format": 1, "toplevel": self.top, "created": NOW, "seeded": True, "files": {}})
        self.assertEqual([row["event"] for row in self.debug_rows()], ["heat-seeded"])


if __name__ == "__main__":
    unittest.main()
