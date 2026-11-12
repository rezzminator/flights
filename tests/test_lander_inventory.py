"""Tests for the lander-inventory skill's kit: what a diff left behind, measured across committed, uncommitted and
untracked work."""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from tests import PLUGIN_DIR

# LANDER_INVENTORY_SCRIPT points the suite at another copy (the unfixed one, for the watched-failure proof).
SCRIPT = os.environ.get("LANDER_INVENTORY_SCRIPT") or os.path.join(PLUGIN_DIR, "skills", "lander-inventory",
                                                                    "lander-inventory.py")


class WorkingTreeTest(unittest.TestCase):
    """A flight's work sits committed, uncommitted and untracked; the inventory measures all three."""

    def setUp(self):
        self.repo = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)
        self.write("a.py", "old_alpha_name = 1\n")
        self.write("b.py", "old_beta_name = 2\n")
        self.write("old_delta_file.py", "x = 1\n")
        self.write("ref.py", "old_alpha_name old_beta_name old_delta_file\n")
        self.git("init", "-q", "-b", "main", ".")
        self.git("add", ".")
        self.git("commit", "-qm", "base")
        self.base = self.git("rev-parse", "HEAD").strip()
        self.write("a.py", "new_alpha_name = 1\n")
        self.git("commit", "-qam", "committed")
        self.write("b.py", "new_beta_name = 2\n")  # uncommitted
        os.remove(os.path.join(self.repo, "old_delta_file.py"))  # uncommitted deletion
        self.write("c.py", "# replaces old_delta_file\n" + "".join(f"v{i} = {i}\n" for i in range(450)))  # untracked

    def write(self, name, text):
        with open(os.path.join(self.repo, name), "w") as f:
            f.write(text)

    def git(self, *args):
        p = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-C", self.repo, *args],
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout

    def run_inv(self, *args):
        return subprocess.run([sys.executable, SCRIPT, self.repo, self.base, *args], capture_output=True, text=True)

    def test_working_tree_carries_committed_uncommitted_and_untracked(self):
        p = self.run_inv()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        rows = p.stdout.splitlines()
        self.assertIn(f"INVENTORY {self.base}..WORKTREE", rows[0])
        left = {r.split(" ")[1]: r for r in rows if r.startswith("LEFT ") and not r.split(" ")[1].isdigit()}
        self.assertIn("old_alpha_name", left, "the committed change")
        self.assertIn("old_beta_name", left, "the uncommitted change")
        gone = [r for r in rows if r.startswith("GONE old_delta_file ")]
        self.assertEqual(len(gone), 1, "the uncommitted deletion")
        self.assertIn("c.py:1", gone[0], "an untracked file is searched")
        diff_checkers = [r for r in rows if r.startswith("PLAN DIFF-CHECKER ")]
        self.assertEqual(len(diff_checkers), 1, rows)
        self.assertIn("c.py", diff_checkers[0], "an untracked file is counted")

    def test_only_uncommitted_work_is_no_empty_diff(self):
        self.base = self.git("rev-parse", "HEAD").strip()
        p = self.run_inv()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("LEFT old_beta_name ", p.stdout)
        self.assertNotIn("LEFT old_alpha_name ", p.stdout)

    def test_head_keeps_the_commit_range(self):
        p = self.run_inv("HEAD")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn(f"INVENTORY {self.base}..HEAD", p.stdout)
        self.assertIn("LEFT old_alpha_name ", p.stdout)
        self.assertNotIn("old_beta_name", p.stdout)
        self.assertIn("PLAN DIFF-CHECKERS none", p.stdout)

    def plan_rows(self, *args):
        p = self.run_inv(*args)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        return [r for r in p.stdout.splitlines() if r.startswith(("PLAN DIFF-CHECKER", "PLAN OWN"))]

    def test_cluster_size_and_cap_cut_the_diff_checkers(self):
        for name in ("d.py", "e.py"):  # untracked: 1,055 production lines with a.py, b.py and c.py
            self.write(name, "".join(f"w{i} = {i}\n" for i in range(300)))
        abc, d, e = "455 lines · a.py b.py c.py", "300 lines · d.py", "300 lines · e.py"
        for args, want in (
            ((), [f"PLAN DIFF-CHECKER 1 · 755 lines · a.py b.py c.py d.py · tests none", f"PLAN DIFF-CHECKER 2 · {e} · tests none"]),
            (("--cluster-lines", "300"), [f"PLAN DIFF-CHECKER 1 · {abc} · tests none", f"PLAN DIFF-CHECKER 2 · {d} · tests none",
                                          f"PLAN DIFF-CHECKER 3 · {e} · tests none"]),
            (("--cluster-lines", "300", "--max-diff-checkers", "1"),
             ["PLAN DIFF-CHECKER 1 · 1055 lines · a.py b.py c.py d.py e.py · tests none"]),
        ):
            with self.subTest(args):
                self.assertEqual(self.plan_rows(*args), want)

    def test_own_lists_what_no_diff_checker_reads(self):
        self.write("notes.md", "one\ntwo\nthree\n")  # untracked prose: no cluster takes it
        checker = "PLAN DIFF-CHECKER 1 · 455 lines · a.py b.py c.py · tests none"
        self.assertEqual(self.plan_rows(), [checker], "no --own, no PLAN OWN row")
        self.assertEqual(self.plan_rows("--own"), [checker, "PLAN OWN 3 lines · notes.md"])

    def test_paths_narrow_the_diff(self):
        p = self.run_inv("--own", "--paths", "a.py")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        rows = p.stdout.splitlines()
        self.assertEqual(rows[0].split(" · ")[0], f"INVENTORY {self.base}..WORKTREE -- a.py")
        self.assertIn("LEFT old_alpha_name ", p.stdout)
        self.assertNotIn("old_beta_name", [r.split(" ")[1] for r in rows if r.startswith("LEFT ")])
        self.assertEqual([r for r in rows if r.startswith("PLAN ")][1:3],
                         ["PLAN DIFF-CHECKERS none · production diff 2 lines <= 400: the whole hunt is yours",
                          "PLAN OWN 2 lines · a.py"])


if __name__ == "__main__":
    unittest.main()
