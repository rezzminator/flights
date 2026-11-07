"""Tests for codebase_map.heat: the decay, each package folder's heat by longest match, and the Read recorder's store."""

import json
import os
import shutil
import tempfile
import unittest

from codebase_map import heat
from codebase_map.plugin_log import PluginLog

DAY = 86400
NOW = 1_800_000_000.0


class DecayTest(unittest.TestCase):
    def test_decayed(self):
        rows = [
            ("a score read now is whole", 1.0, NOW, 1.0),
            ("one half-life halves it", 1.0, NOW - 14 * DAY, 0.5),
            ("two half-lives quarter it", 4.0, NOW - 28 * DAY, 1.0),
            ("a stamp in the future does not grow it", 1.0, NOW + 14 * DAY, 1.0),
        ]
        for name, score, ts, want in rows:
            with self.subTest(name):
                self.assertEqual(heat.decayed(score, ts, NOW), want)


class PackageHeatTest(unittest.TestCase):
    def test_package_heat(self):
        files = {
            "pfm/internal/clock/clock.go": [2.0, NOW],
            "pfm/internal/clock/fake/fake.go": [1.0, NOW],
            "pfm/internal/obs/obs.go": [1.0, NOW - 14 * DAY],
            "pfm/main.go": [1.0, NOW],
            "README.md": [0.5, NOW],
        }
        rows = [
            ("each file counts for its longest enclosing map folder, the top's files for ./",
             [".", "pfm", "pfm/internal", "pfm/internal/clock"],
             {"pfm/internal/clock": 3.0, "pfm/internal": 0.5, "pfm": 1.0, ".": 0.5}),
            ("a file under no map folder counts for none", ["pfm/internal/clock", "web"], {"pfm/internal/clock": 3.0}),
        ]
        for name, folders, want in rows:
            with self.subTest(name):
                self.assertEqual(heat.package_heat(folders, heat.Store(NOW, True, files), NOW), want)


class RecordReadTest(unittest.TestCase):
    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp(prefix="flights-heat-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        self.top = os.path.join(self.root, "repo")
        os.makedirs(os.path.join(self.top, ".git"))
        os.makedirs(os.path.join(self.top, "pfm", "internal"))
        self.env = {"XDG_CACHE_HOME": os.path.join(self.root, "cache")}
        self.logs = os.path.join(self.root, "logs")
        self.log = PluginLog("flights", self.logs)
        self.path = heat.store_path(self.env, self.top)

    def read(self, file_path, now, cwd=None):
        payload = {"hook_event_name": "PostToolUse", "tool_name": "Read", "session_id": "s1",
                   "cwd": cwd or self.top, "tool_input": {"file_path": file_path}, "tool_use_id": "t1"}
        heat.record_read(payload, self.env, self.log, now)

    def stored(self):
        with open(self.path) as handle:
            return json.load(handle)

    def store(self, files, created=NOW, seeded=False, first_read="t1"):
        stored = {"format": 1, "toplevel": self.top, "created": created, "seeded": seeded, "files": files}
        if first_read:
            stored["first_read"] = first_read
        return stored

    def rows(self, level_file):
        path = os.path.join(self.logs, level_file)
        with open(path) as handle:
            rows = [json.loads(line) for line in handle]
        for row in rows:
            row.pop("ts")
        return rows

    def test_reads_add_up_and_decay(self):
        self.read(os.path.join(self.top, "pfm", "a.go"), NOW)
        self.assertEqual(self.stored(), self.store({"pfm/a.go": [1.0, NOW]}))
        self.read("a.go", NOW + 14 * DAY, cwd=os.path.join(self.top, "pfm"))
        self.assertEqual(self.stored(), self.store({"pfm/a.go": [1.5, NOW + 14 * DAY]}))

    def test_paths_outside_the_repository_are_passed_over(self):
        elsewhere = os.path.join(self.root, "elsewhere")
        os.makedirs(elsewhere)
        nested = os.path.join(self.top, ".worktrees", "flight")
        os.makedirs(nested)
        with open(os.path.join(nested, ".git"), "w") as handle:
            handle.write("gitdir: ../../.git/worktrees/flight\n")
        rows = [
            ("a file of a work tree nested inside the repository", os.path.join(nested, "pfm", "a.go"), self.top),
            ("a path holding a NUL byte", os.path.join(self.top, "a\0.go"), self.top),
            ("a file outside the repository", os.path.join(self.root, "other.go"), self.top),
            ("a relative path climbing out of it", "../other.go", self.top),
            ("the repository folder itself", self.top, self.top),
            ("a session in no repository", os.path.join(elsewhere, "x.go"), elsewhere),
        ]
        for name, file_path, cwd in rows:
            with self.subTest(name):
                self.read(file_path, NOW, cwd=cwd)
                self.assertFalse(os.path.exists(self.path), f"{self.path} was written for {file_path}")
        self.read(os.path.join(self.top, "in.go"), NOW)
        self.assertEqual(self.stored(), self.store({"in.go": [1.0, NOW]}))

    def test_prune_at_the_bound(self):
        os.makedirs(os.path.dirname(self.path))
        with open(self.path, "w") as handle:
            json.dump(self.store({"kept.go": [0.01, NOW], "gone.go": [0.0099, NOW]}, created=NOW - DAY, seeded=True,
                                 first_read=""), handle)
        self.read(os.path.join(self.top, "new.go"), NOW)
        self.assertEqual(self.stored(), self.store({"kept.go": [0.01, NOW], "new.go": [1.0, NOW]}, created=NOW - DAY,
                                                   seeded=True, first_read=""))

    def test_unusable_store_is_rebuilt_empty_and_logged(self):
        rows = [
            ("not JSON", b"{not json", "Expecting property name enclosed in double quotes: line 1 column 2 (char 1)"),
            ("not UTF-8", b'{"format": 1, "toplevel": "\xff"}',
             "'utf-8' codec can't decode byte 0xff in position 27: invalid start byte"),
        ]
        os.makedirs(os.path.dirname(self.path))
        for name, raw, reason in rows:
            with self.subTest(name):
                shutil.rmtree(self.logs, True)
                with open(self.path, "wb") as handle:
                    handle.write(raw)
                self.read(os.path.join(self.top, "a.go"), NOW)
                self.assertEqual(self.stored(), self.store({"a.go": [1.0, NOW]}))
                self.assertEqual(self.rows("warnings.jsonl"), [{
                    "plugin": "flights", "level": "warning", "event": "heat-store-unusable",
                    "msg": f"the read heat store {self.path} is unusable and is rebuilt empty: {reason}",
                    "where": "heat.py#load", "detail": {"path": self.path, "toplevel": self.top},
                }])

    def test_read_without_a_file_path_is_logged(self):
        payload = {"hook_event_name": "PostToolUse", "tool_name": "Read", "session_id": "s1", "cwd": self.top,
                   "tool_input": {"path": "a.go"}}
        heat.record_read(payload, self.env, self.log, NOW)
        self.assertFalse(os.path.exists(self.path))
        self.assertEqual(self.rows("warnings.jsonl"), [{
            "plugin": "flights", "level": "warning", "event": "heat-read-unrecognized",
            "msg": "a Read's PostToolUse payload carries no tool_input.file_path", "where": "heat.py#record_read",
            "session": "s1", "detail": {"toolInput": "{'path': 'a.go'}"},
        }])


if __name__ == "__main__":
    unittest.main()
