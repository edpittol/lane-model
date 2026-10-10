"""Tests of the lane tool against a local bare remote and a fake gh. Run: python3 -m unittest discover tests"""
import json, os, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FAKE = ROOT / "tests" / "fake-gh"


def sh(*a, cwd=None, env=None, check=True):
    p = subprocess.run(a, cwd=cwd, env=env, capture_output=True, text=True)
    if check and p.returncode:
        raise AssertionError(f"{a} failed: {p.stderr}")
    return p


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="lane-test-")).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.remote, self.main, self.gh = self.tmp / "remote.git", self.tmp / "proj", self.tmp / "gh"
        self.gh.mkdir()
        (self.tmp / "bin").mkdir()
        os.symlink(FAKE, self.tmp / "bin" / "gh")
        sh("git", "init", "-q", "--bare", "-b", "main", str(self.remote))
        sh("git", "init", "-q", "-b", "main", str(self.main))
        for k, v in (("user.name", "t"), ("user.email", "t@t")):
            sh("git", "config", k, v, cwd=self.main)
        shutil.copytree(ROOT / "scripts", self.main / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(ROOT / "sample", self.main / "sample", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy(ROOT / "lanes.toml", self.main / "lanes.toml")
        (self.main / ".gitignore").write_text(".claude/worktrees/\n")
        (self.main / "app.txt").write_text("one\n")
        sh("git", "add", "-A", cwd=self.main)
        sh("git", "commit", "-qm", "init", cwd=self.main)
        sh("git", "remote", "add", "origin", str(self.remote), cwd=self.main)
        sh("git", "push", "-q", "origin", "main", cwd=self.main)
        self.env = {**os.environ, "PATH": f"{self.tmp / 'bin'}:{os.environ['PATH']}", "FAKE_GH_DIR": str(self.gh),
                    "LANE_DATA_ROOT": str(self.tmp / "data"), "LANE_SESSION_ID": "", "HOME": str(self.tmp)}
        self.env.pop("LANE_SESSION_ID")
        (self.gh / "repo.json").write_text(json.dumps({"defaultBranchRef": {"name": "main"}, "mergeCommitAllowed": True,
                                                       "squashMergeAllowed": True, "rebaseMergeAllowed": False}))
        self.addCleanup(self.kill_runtimes)

    def kill_runtimes(self):
        sh("pkill", "-f", "--", "--lane-id lane-model-", check=False)

    def lane(self, *a, cwd=None, **env):
        return subprocess.run([sys.executable, str(self.main / "scripts" / "lane"), *a], cwd=cwd or self.main,
                              env={**self.env, **env}, capture_output=True, text=True)

    def ok(self, *a, **kw):
        p = self.lane(*a, **kw)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p

    def refused(self, *a, **kw):
        p = self.lane(*a, **kw)
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        return p.stderr

    def wt(self, name): return self.main / ".claude" / "worktrees" / name
    def git(self, *a, cwd=None): return sh("git", *a, cwd=cwd or self.main).stdout.strip()
    def prs(self, name, *prs): (self.gh / f"prs-{name}.json").write_text(json.dumps(list(prs)))
    def listing(self): return json.loads(self.ok("list", "--json").stdout)
    def state(self, name): return next(i["state"] for i in self.listing() if i["name"] == name)

    def edit_record(self, name, fn):
        ad = next(d for d in (self.main / ".git" / "worktrees").iterdir() if (d / "gitdir").read_text().strip().endswith(f"/{name}/.git"))
        f = ad / "lane.json"; rec = json.loads(f.read_text()); fn(rec); f.write_text(json.dumps(rec))

    def dead_pid(self):
        p = subprocess.Popen(["true"]); p.wait(); return p.pid

    def commit_in(self, name, fname="work.txt", text="x\n", push=False):
        w = self.wt(name)
        (w / fname).write_text(text)
        sh("git", "add", "-A", cwd=w); sh("git", "commit", "-qm", f"edit {fname}", cwd=w)
        if push:
            sh("git", "push", "-q", "origin", name, cwd=w)


class Create(Base):
    def test_create_makes_prepared_lane_from_remote_base(self):
        self.ok("create", "alpha-one")
        self.assertEqual(self.state("alpha-one"), "Prepared")
        self.assertEqual(self.git("rev-parse", "alpha-one"), self.git("rev-parse", "origin/main"))
        self.assertTrue(self.git("config", "lane.alpha-one.created"))

    def test_bad_and_duplicate_names_refused(self):
        for bad in ("ab", "Bad-Name", "a--b", "trail-", "x" * 41, "a/b"):
            self.assertIn("naming rule", self.refused("create", bad), bad)
        self.assertIn("naming rule", self.refused("create", "--", "-lead"))
        self.ok("create", "alpha-one")
        self.assertIn("not unique", self.refused("create", "alpha-one"))

    def test_name_left_on_the_git_host_is_not_reused(self):
        self.prs("old-merged", {"number": 4, "state": "MERGED", "headRefOid": "0" * 40, "baseRefName": "main", "url": ""})
        err = self.refused("create", "old-merged")
        self.assertIn("pull request #4 (merged)", err)
        self.assertFalse(self.wt("old-merged").exists())
        sh("git", "push", "-q", "origin", "main:refs/heads/old-closed", cwd=self.main)
        self.prs("old-closed", {"number": 2, "state": "CLOSED", "headRefOid": "0" * 40, "baseRefName": "main", "url": ""})
        err = self.refused("create", "old-closed")
        self.assertIn("pull request #2 (closed)", err)
        self.assertIn("a branch on origin", err)
        sh("git", "push", "-q", "origin", "main:refs/heads/old-branch", cwd=self.main)
        self.assertIn("a branch on origin", self.refused("create", "old-branch"))
        self.assertFalse(self.git("branch", "--list", "old-*"))

    def test_uniqueness_is_never_guessed_when_origin_is_unreachable(self):
        sh("git", "remote", "set-url", "origin", str(self.tmp / "gone.git"), cwd=self.main)
        self.assertIn("uniqueness is never guessed", self.refused("create", "alpha-one"))
        self.assertFalse(self.wt("alpha-one").exists())

    def test_base_is_never_guessed_when_host_is_down(self):
        (self.gh / "DOWN").write_text("")
        self.assertIn("Git host could not be asked", self.refused("create", "alpha-one"))
        self.assertFalse(self.wt("alpha-one").exists())

    def test_lane_file_unreadable_means_nothing_runs(self):
        (self.main / "lanes.toml").write_text("[lane]\nruntime='always'\n")
        self.assertIn("cannot be used", self.refused("create", "alpha-one"))


class Runtime(Base):
    def setUp(self):
        super().setUp()
        self.ok("create", "alpha-one")

    def test_start_pause_resume_keeps_data(self):
        self.ok("start", "alpha-one")
        self.assertEqual(self.state("alpha-one"), "Running")
        port = self.listing()[0]["port"]
        import urllib.request
        self.assertIn("1 hit", urllib.request.urlopen(f"http://127.0.0.1:{port}/").read().decode())
        self.ok("pause", "alpha-one")
        self.assertEqual(self.state("alpha-one"), "Paused")
        self.ok("resume", "alpha-one")
        self.assertIn("2 hit", urllib.request.urlopen(f"http://127.0.0.1:{port}/").read().decode())
        self.ok("pause", "alpha-one")

    def test_second_runner_refused_with_seats(self):
        self.ok("start", "alpha-one", "--as", "script", "--label", "nightly")
        err = self.refused("start", "alpha-one", "--as", "person", "--label", "ed")
        self.assertIn("nightly", err); self.assertIn("next:", err)
        self.assertIn("only its runner pauses", self.refused("pause", "alpha-one", "--as", "person", "--label", "ed"))
        self.ok("pause", "alpha-one", "--as", "script", "--label", "nightly")

    def test_runner_gone_is_runaway_and_stop_recovers(self):
        self.ok("start", "alpha-one", "--as", "script", "--label", "nightly")
        dead = self.dead_pid()
        self.edit_record("alpha-one", lambda r: r["seats"]["runner"].update(pid=dead))
        self.assertEqual(self.state("alpha-one"), "Runaway")
        self.assertIn("lane stop alpha-one", self.ok("list").stdout)
        self.assertIn("Runaway", self.refused("start", "alpha-one"))
        self.assertIn("next:", self.ok("stop", "alpha-one").stderr)
        self.assertEqual(self.state("alpha-one"), "Paused")
        self.ok("start", "alpha-one"); self.ok("pause", "alpha-one")

    def test_stale_runner_with_runtime_down_names_start_as_its_fix(self):
        self.ok("start", "alpha-one", "--as", "script", "--label", "nightly")
        self.ok("pause", "alpha-one", "--as", "script", "--label", "nightly")
        dead = self.dead_pid()
        self.edit_record("alpha-one", lambda r: r["seats"].update(runner={"kind": "script", "label": "nightly", "pid": dead,
                                                                           "pid_start": None, "since": "2026-10-10T00:00:00Z"}))
        out = self.ok("list").stdout
        self.assertIn("lane start alpha-one", out); self.assertNotIn("lane stop", out)
        self.refused("stop", "alpha-one")
        self.ok("start", "alpha-one"); self.ok("pause", "alpha-one")

    def test_person_outlives_the_shell_that_started_it(self):
        self.ok("start", "alpha-one", "--as", "person", "--label", "ed")
        dead = self.dead_pid()
        self.edit_record("alpha-one", lambda r: r["seats"]["runner"].update(pid=dead))
        self.assertEqual(self.state("alpha-one"), "Running")
        self.assertIn("Running, not Runaway", self.refused("stop", "alpha-one"))
        self.assertIn("only its runner pauses", self.refused("pause", "alpha-one", "--as", "person", "--label", "bo"))
        self.ok("pause", "alpha-one", "--as", "person", "--label", "ed")
        self.assertEqual(self.state("alpha-one"), "Paused")

    def test_runner_restarts_a_runtime_that_died(self):
        self.ok("start", "alpha-one", "--as", "person", "--label", "ed")
        self.kill_runtimes()
        sh("sh", "-c", "for i in $(seq 50); do pgrep -f -- '--lane-id lane-model-' >/dev/null || exit 0; sleep 0.1; done; exit 1")
        self.assertIn("runner seat taken but the runtime is down", self.ok("list").stdout)
        self.assertIn("running on", self.ok("start", "alpha-one", "--as", "person", "--label", "ed").stderr)
        self.assertEqual(self.state("alpha-one"), "Running")
        self.assertIn("run by ed", self.refused("start", "alpha-one", "--as", "person", "--label", "bo"))
        self.ok("pause", "alpha-one", "--as", "person", "--label", "ed")

    def test_pause_all_pauses_only_my_lanes(self):
        self.ok("create", "beta-two")
        self.ok("start", "alpha-one"); self.ok("start", "beta-two", "--as", "script", "--label", "other")
        self.ok("pause", "--all")
        self.assertEqual(self.state("alpha-one"), "Paused"); self.assertEqual(self.state("beta-two"), "Running")
        self.ok("pause", "beta-two", "--as", "script", "--label", "other")

    def test_two_lanes_get_distinct_ports(self):
        self.ok("create", "beta-two"); self.ok("start", "alpha-one"); self.ok("start", "beta-two")
        ports = [i["port"] for i in self.listing()]
        self.assertEqual(len(set(ports)), 2)
        self.ok("pause", "--all")


class Seats(Base):
    def setUp(self):
        super().setUp(); self.ok("create", "alpha-one")

    def test_one_writer_stale_replaced(self):
        self.ok("write", "alpha-one", "--as", "script", "--label", "fixer")
        self.assertIn("taken by fixer", self.refused("write", "alpha-one", "--as", "script", "--label", "bot"))
        dead = self.dead_pid()
        self.edit_record("alpha-one", lambda r: r["seats"]["writer"].update(pid=dead))
        out = self.ok("list").stdout
        self.assertIn("stale writer seat", out); self.assertIn("lane write alpha-one", out); self.assertNotIn("lane release", out)
        self.ok("write", "alpha-one", "--as", "script", "--label", "bot")
        self.ok("release", "alpha-one", "--as", "script", "--label", "bot")

    def test_person_writer_seat_outlives_the_shell(self):
        self.ok("write", "alpha-one", "--as", "person", "--label", "ed")
        dead = self.dead_pid()
        self.edit_record("alpha-one", lambda r: r["seats"]["writer"].update(pid=dead))
        self.assertIn("taken by ed", self.refused("write", "alpha-one", "--as", "script", "--label", "bot"))
        self.ok("release", "alpha-one", "--as", "person", "--label", "ed")

    def test_write_and_release_warn_when_another_runner_runs_the_lane(self):
        self.ok("start", "alpha-one", "--as", "script", "--label", "nightly")
        err = self.ok("write", "alpha-one", "--as", "person", "--label", "ed").stderr
        self.assertIn("nightly", err); self.assertIn("will refuse", err)
        self.assertIn("nightly", self.ok("release", "alpha-one", "--as", "person", "--label", "ed").stderr)
        self.assertNotIn("next:", self.ok("write", "alpha-one", "--as", "script", "--label", "nightly").stderr)
        self.ok("release", "alpha-one", "--as", "script", "--label", "nightly")
        self.ok("pause", "alpha-one", "--as", "script", "--label", "nightly")

    def test_only_holder_releases(self):
        self.ok("write", "alpha-one", "--as", "person", "--label", "ed")
        self.assertIn("not by you", self.refused("release", "alpha-one", "--as", "script", "--label", "bot"))


class Teardown(Base):
    def setUp(self):
        super().setUp(); self.ok("create", "alpha-one")

    def test_refusals_come_before_destruction(self):
        self.ok("start", "alpha-one"); self.ok("pause", "alpha-one")
        self.commit_in("alpha-one")
        (self.wt("alpha-one") / "dirty.txt").write_text("d")
        err = self.refused("teardown", "alpha-one")
        self.assertIn("uncommitted", err); self.assertIn("local commit", err); self.assertIn("finish rule not met", err)
        self.assertTrue(self.wt("alpha-one").is_dir())
        self.assertTrue(any((self.tmp / "data").rglob("hits.db")))

    def test_teardown_of_a_runaway_lane_warns_before_it_destroys(self):
        self.ok("start", "alpha-one", "--as", "script", "--label", "nightly")
        dead = self.dead_pid()
        self.edit_record("alpha-one", lambda r: r["seats"]["runner"].update(pid=dead))
        self.prs("alpha-one", {"number": 1, "state": "CLOSED", "headRefOid": "x", "baseRefName": "main", "url": "u"})
        err = self.ok("teardown", "alpha-one").stderr
        self.assertLess(err.index("next:"), err.index("torn down"))

    def test_live_runner_cannot_be_lifted_by_the_humans_word(self):
        self.ok("start", "alpha-one")
        err = self.refused("teardown", "alpha-one", "--discard", "--unfinished")
        self.assertIn("cannot lift", err)
        self.ok("pause", "alpha-one")

    def test_merge_commit_landing_tears_down_everything(self):
        self.ok("start", "alpha-one"); self.ok("pause", "alpha-one")
        self.commit_in("alpha-one", push=True)
        self.prs("alpha-one", {"number": 1, "state": "MERGED", "headRefOid": self.git("rev-parse", "alpha-one"), "baseRefName": "main"})
        self.ok("teardown", "alpha-one")
        self.assertFalse(self.wt("alpha-one").exists())
        self.assertFalse(any((self.tmp / "data").rglob("*")))
        self.assertEqual(self.git("branch", "--list", "alpha-one"), "")
        self.assertEqual(sh("git", "config", "--get", "lane.alpha-one.created", cwd=self.main, check=False).returncode, 1)
        self.assertEqual(self.listing(), [])

    def test_unremovable_worktree_or_data_refuses_before_destruction(self):
        self.ok("start", "alpha-one"); self.ok("pause", "alpha-one")
        (self.wt("alpha-one") / "locked").mkdir()
        self.commit_in("alpha-one", "locked/work.txt", push=True)
        self.prs("alpha-one", {"number": 1, "state": "MERGED", "headRefOid": self.git("rev-parse", "alpha-one"), "baseRefName": "main"})
        data = next((self.tmp / "data").rglob("hits.db")).parent
        for locked in (self.wt("alpha-one") / "locked", data):
            locked.chmod(0o555)
            self.addCleanup(lambda p=locked: p.exists() and p.chmod(0o755))
            self.assertIn("cannot be removed", self.refused("teardown", "alpha-one", "--discard", "--unfinished"))
            self.assertTrue((self.wt("alpha-one") / "locked" / "work.txt").is_file())
            self.assertTrue((data / "hits.db").is_file())
            locked.chmod(0o755)
        self.ok("teardown", "alpha-one")
        self.assertFalse(self.wt("alpha-one").exists())
        self.assertFalse(data.exists())

    def test_squash_landing_uses_merged_head_when_branch_is_deleted(self):
        self.commit_in("alpha-one", push=True)
        head = self.git("rev-parse", "alpha-one")
        self.git("push", "-q", "origin", f"{head}:refs/pull/7/head")
        self.git("push", "-q", "origin", ":alpha-one")
        self.prs("alpha-one", {"number": 7, "state": "MERGED", "headRefOid": head, "baseRefName": "main"})
        self.ok("teardown", "alpha-one")
        self.assertFalse(self.wt("alpha-one").exists())

    def test_squash_landing_without_the_merged_head_refuses(self):
        self.commit_in("alpha-one", push=True)
        head = self.git("rev-parse", "alpha-one")
        self.git("push", "-q", "origin", ":alpha-one")
        self.prs("alpha-one", {"number": 8, "state": "MERGED", "headRefOid": head, "baseRefName": "main"})
        self.assertIn("local commit", self.refused("teardown", "alpha-one"))

    def test_open_pr_refuses_and_unfinished_lifts_only_the_rule(self):
        self.commit_in("alpha-one", push=True)
        self.prs("alpha-one", {"number": 2, "state": "OPEN", "headRefOid": "x", "baseRefName": "main"})
        self.assertIn("still open", self.refused("teardown", "alpha-one"))
        self.ok("teardown", "alpha-one", "--unfinished")

    def test_unfinished_does_not_discard_work(self):
        self.commit_in("alpha-one")
        self.assertIn("local commit", self.refused("teardown", "alpha-one", "--unfinished"))
        self.ok("teardown", "alpha-one", "--unfinished", "--discard")

    def test_host_down_refuses(self):
        (self.gh / "DOWN").write_text("")
        self.assertIn("nothing guesses", self.refused("teardown", "alpha-one"))
        self.assertTrue(self.wt("alpha-one").is_dir())


class Leftover(Base):
    def test_removed_worktree_is_a_leftover_with_a_fix_and_teardown_by_name_ends_it(self):
        self.ok("create", "alpha-one"); self.ok("start", "alpha-one"); self.ok("pause", "alpha-one")
        shutil.rmtree(self.wt("alpha-one"))
        self.assertEqual(self.state("alpha-one"), "Leftover")
        self.assertIn("lane teardown alpha-one", self.ok("list").stdout)
        self.refused("teardown", "alpha-one")
        self.prs("alpha-one", {"number": 3, "state": "CLOSED", "headRefOid": "x", "baseRefName": "main"})
        self.ok("teardown", "alpha-one")
        self.assertEqual(self.listing(), [])
        self.assertEqual(self.git("branch", "--list", "alpha-one"), "")

    def test_leftover_after_git_worktree_remove_is_still_found_by_its_branch(self):
        self.ok("create", "alpha-one")
        self.git("worktree", "remove", "--force", str(self.wt("alpha-one")))
        self.assertEqual(self.state("alpha-one"), "Leftover")
        self.prs("alpha-one", {"number": 3, "state": "MERGED", "headRefOid": "x", "baseRefName": "main"})
        self.ok("teardown", "alpha-one")
        self.assertEqual(self.listing(), [])

    def test_runtime_of_a_leftover_is_listed_and_killed(self):
        self.ok("create", "alpha-one"); self.ok("start", "alpha-one")
        shutil.rmtree(self.wt("alpha-one"))
        self.assertIn("runtime up", self.ok("list").stdout)
        self.git("worktree", "prune")
        self.prs("alpha-one", {"number": 3, "state": "CLOSED", "headRefOid": "x", "baseRefName": "main"})
        self.ok("teardown", "alpha-one")
        self.assertEqual(subprocess.run(["pgrep", "-f", "--", "--lane-id lane-model-.*-lane-alpha-one"], capture_output=True).returncode, 1)


class Sync(Base):
    def setUp(self):
        super().setUp()
        self.other = self.tmp / "other"
        sh("git", "clone", "-q", str(self.remote), str(self.other))
        for k, v in (("user.name", "o"), ("user.email", "o@o")):
            sh("git", "config", k, v, cwd=self.other)
        self.ok("create", "alpha-one")

    def land(self, fname, text):
        (self.other / fname).write_text(text)
        sh("git", "add", "-A", cwd=self.other); sh("git", "commit", "-qm", fname, cwd=self.other)
        sh("git", "push", "-q", "origin", "main", cwd=self.other)

    def prep(self): return self.lane("prep", "alpha-one")

    def test_current_moved_merged(self):
        self.assertIn("Current", self.prep().stdout)
        self.land("landed.txt", "l\n")
        self.assertIn("Moved", self.prep().stdout)
        self.assertTrue((self.wt("alpha-one") / "landed.txt").exists())
        self.commit_in("alpha-one")
        self.land("landed2.txt", "l\n")
        self.assertIn("Merged", self.prep().stdout)
        self.assertTrue((self.wt("alpha-one") / "landed2.txt").exists() and (self.wt("alpha-one") / "work.txt").exists())
        self.assertIn("Current", self.prep().stdout)

    def test_held_when_dirty_conflict_or_host_down(self):
        self.commit_in("alpha-one", "app.txt", "mine\n")
        self.land("app.txt", "theirs\n")
        (self.wt("alpha-one") / "dirty.txt").write_text("d")
        p = self.prep(); self.assertEqual(p.returncode, 1); self.assertIn("uncommitted", p.stdout)
        (self.wt("alpha-one") / "dirty.txt").unlink()
        before = self.git("rev-parse", "HEAD", cwd=self.wt("alpha-one"))
        p = self.prep(); self.assertEqual(p.returncode, 1); self.assertIn("app.txt", p.stdout)
        self.assertEqual(self.git("rev-parse", "HEAD", cwd=self.wt("alpha-one")), before)
        self.assertEqual(self.git("status", "--porcelain", cwd=self.wt("alpha-one")), "")
        (self.gh / "DOWN").write_text("")
        p = self.prep(); self.assertEqual(p.returncode, 1); self.assertIn("Git host", p.stdout)

    def test_replay_when_rebase_is_allowed(self):
        (self.gh / "repo.json").write_text(json.dumps({"defaultBranchRef": {"name": "main"}, "mergeCommitAllowed": False,
                                                       "squashMergeAllowed": False, "rebaseMergeAllowed": True}))
        self.commit_in("alpha-one"); self.land("landed.txt", "l\n")
        self.assertIn("Replayed", self.prep().stdout)
        self.assertEqual(self.git("rev-list", "--merges", "--count", "origin/main..HEAD", cwd=self.wt("alpha-one")), "0")

    def test_prep_holds_under_another_live_writer_and_runs_for_the_writer(self):
        self.ok("write", "alpha-one", "--as", "person", "--label", "ed")
        self.land("landed.txt", "l\n")
        p = self.prep()
        self.assertEqual(p.returncode, 1); self.assertIn("Held", p.stdout); self.assertIn("ed (person)", p.stdout)
        self.assertFalse((self.wt("alpha-one") / "landed.txt").exists())
        self.assertIn("Moved", self.lane("prep", "alpha-one", USER="ed").stdout)
        self.assertTrue((self.wt("alpha-one") / "landed.txt").exists())

    def test_prep_warns_when_another_runner_runs_it(self):
        self.ok("start", "alpha-one", "--as", "script", "--label", "nightly")
        p = self.prep()
        self.assertIn("nightly", p.stderr); self.assertIn("will refuse", p.stderr)
        self.ok("pause", "alpha-one", "--as", "script", "--label", "nightly")


class Housekeeping(Base):
    def test_tears_down_finished_and_reports_the_rest(self):
        self.ok("create", "done-one"); self.ok("create", "open-two"); self.ok("create", "run-three")
        self.ok("start", "run-three", "--as", "script", "--label", "nightly")
        self.prs("done-one", {"number": 1, "state": "MERGED", "headRefOid": "x", "baseRefName": "main"})
        self.prs("run-three", {"number": 2, "state": "MERGED", "headRefOid": "x", "baseRefName": "main"})
        dead = self.dead_pid()
        self.edit_record("run-three", lambda r: r["seats"]["runner"].update(pid=dead))
        out = self.ok("housekeeping").stdout
        self.assertIn("done-one: torn down", out)
        self.assertNotIn("open-two", out)
        self.assertIn("run-three: torn down", out)   # Runaway but finished: the same checks pass, teardown stops the runtime
        self.assertEqual([i["name"] for i in self.listing()], ["open-two"])

    def test_refused_teardown_goes_into_the_report(self):
        self.ok("create", "done-one"); self.commit_in("done-one")
        self.prs("done-one", {"number": 1, "state": "MERGED", "headRefOid": "x", "baseRefName": "main"})
        out = self.ok("housekeeping").stdout
        self.assertIn("teardown refused", out)
        self.assertTrue(self.wt("done-one").is_dir())

    def test_resting_lane_is_reported(self):
        self.ok("create", "idle-one")
        self.edit_record("idle-one", lambda r: r.update(idle_since="2020-01-01T00:00:00Z"))
        self.assertIn("resting since", self.ok("housekeeping").stdout)


if __name__ == "__main__":
    unittest.main()
