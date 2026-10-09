"""Tests of scripts/lane-hook: feed it the JSON the harness sends and read what it answers."""
import json, os, subprocess, sys, unittest
from pathlib import Path

from test_lane import Base, sh


class Hook(Base):
    def hook(self, event, cwd=None, extra_env=None, **fields):
        data = {"hook_event_name": event, "session_id": fields.pop("sid", "sess-aaaa-1111"), "cwd": str(cwd or self.main), **fields}
        p = subprocess.run([sys.executable, str(self.main / "scripts" / "lane-hook")], input=json.dumps(data), text=True,
                           capture_output=True, env={**self.env, **(extra_env or {})}, cwd=cwd or self.main)
        return p

    def decision(self, p):
        self.assertEqual(p.returncode, 0, p.stderr)
        if not p.stdout.strip():
            return "allow", ""
        o = json.loads(p.stdout)["hookSpecificOutput"]
        return o.get("permissionDecision", "context"), o.get("permissionDecisionReason") or o.get("additionalContext", "")

    def tool(self, name, cwd=None, **ti):
        return self.decision(self.hook("PreToolUse", cwd=cwd, tool_name=name, tool_input=ti))

    def bash(self, cmd, cwd=None): return self.tool("Bash", cwd=cwd, command=cmd)[0]


class Writes(Hook):
    def test_main_worktree_refuses_every_file_tool(self):
        for t, k in (("Edit", "file_path"), ("Write", "file_path"), ("NotebookEdit", "notebook_path")):
            d, why = self.tool(t, **{k: str(self.main / "app.txt")})
            self.assertEqual(d, "deny"); self.assertIn("I8", why)
        self.assertEqual(self.tool("Write", file_path=str(self.main / "new.txt"))[0], "deny")

    def test_files_outside_the_project_are_allowed(self):
        self.assertEqual(self.tool("Write", file_path=str(self.tmp / "elsewhere.txt"))[0], "allow")

    def test_lane_write_takes_the_writer_seat_and_a_second_session_is_refused(self):
        self.ok("create", "alpha-one")
        f = str(self.wt("alpha-one") / "x.txt")
        self.assertEqual(self.tool("Write", cwd=self.wt("alpha-one"), file_path=f)[0], "allow")
        self.assertEqual(self.tool("Edit", cwd=self.wt("alpha-one"), file_path=f)[0], "allow")
        p = self.hook("PreToolUse", sid="sess-bbbb-2222", tool_name="Write", tool_input={"file_path": f}, cwd=self.wt("alpha-one"))
        d, why = self.decision(p)
        self.assertEqual(d, "deny"); self.assertIn("sess-aaa", why)
        self.assertEqual(self.listing()[0]["writer"]["session_id"], "sess-aaaa-1111")

    def test_unreadable_class_file_denies_writes(self):
        (self.main / "lanes.toml").write_text("nonsense = ")
        self.assertEqual(self.tool("Write", file_path=str(self.main / "a.txt"))[0], "deny")


class BashGuard(Hook):
    def test_writing_shapes_in_main_are_refused(self):
        for cmd in ("echo hi > x.txt", "echo hi >> x.txt", "cat a | tee b", "rm -rf node_modules", "mv a b", "cp a b", "mkdir d",
                    "touch f", "sed -i s/a/b/ app.txt", "git commit -m x", "git checkout -b y", "git stash", "git -C . reset --hard",
                    "npm install", "pnpm add left-pad", "curl -o out http://x", "cd sub && rm f", "ls; rm f", "FOO=1 rm f"):
            self.assertEqual(self.bash(cmd), "deny", cmd)

    def test_reading_shapes_in_main_are_allowed(self):
        for cmd in ("ls -la", "git status", "git fetch origin", "git log --oneline | head", "git worktree list", "cat app.txt",
                    "grep -r 'a>b' .", "ls 2>/dev/null", "make 2>&1 | tail", "scripts/lane list", "scripts/lane create x-y-z",
                    "python3 scripts/lane teardown abc", "echo 'x > y'", "git diff > /dev/null"):
            self.assertEqual(self.bash(cmd), "allow", cmd)

    def test_inside_a_lane_nothing_is_refused(self):
        self.ok("create", "alpha-one")
        self.assertEqual(self.bash("echo hi > x.txt && rm f", cwd=self.wt("alpha-one")), "allow")

    def test_the_named_holes_really_are_holes(self):
        for cmd in ("python3 -c \"open('x','w')\"", "bash -c 'echo > x'", "find . -name '*.tmp' -delete"):
            self.assertEqual(self.bash(cmd), "allow", cmd)


class Lifecycle(Hook):
    def test_entering_an_existing_lane_preps_it_and_tells_the_session(self):
        self.ok("create", "alpha-one")
        self.ok("start", "alpha-one", "--as", "script", "--label", "nightly")
        p = self.hook("PostToolUse", cwd=self.wt("alpha-one"), tool_name="EnterWorktree", tool_input={"path": str(self.wt("alpha-one"))})
        d, ctx = self.decision(p)
        self.assertIn("Prep of alpha-one: Current", ctx); self.assertIn("nightly", ctx); self.assertIn("will refuse", ctx)
        self.ok("pause", "alpha-one", "--as", "script", "--label", "nightly")

    def test_exit_worktree_remove_is_refused_keep_is_allowed(self):
        self.assertEqual(self.tool("ExitWorktree", action="remove")[0], "deny")
        self.assertEqual(self.tool("ExitWorktree", action="keep")[0], "allow")

    def test_session_start_exports_env_and_prepares_the_lane_it_starts_in(self):
        self.ok("create", "alpha-one")
        envfile = self.tmp / "env.sh"
        p = self.hook("SessionStart", cwd=self.wt("alpha-one"), extra_env={"CLAUDE_ENV_FILE": str(envfile)}, source="startup")
        d, ctx = self.decision(p)
        self.assertEqual(d, "context"); self.assertIn("alpha-one", ctx); self.assertIn("Prep of alpha-one: Current", ctx)
        self.assertIn("LANE_SESSION_ID='sess-aaaa-1111'", envfile.read_text())

    def test_session_runs_a_lane_then_its_end_pauses_it_and_releases_the_writer(self):
        self.ok("create", "alpha-one")
        sess = {"LANE_SESSION_ID": "sess-aaaa-1111", "LANE_SESSION_PID": str(os.getpid())}
        self.ok("start", "alpha-one", **sess)
        self.tool("Write", cwd=self.wt("alpha-one"), file_path=str(self.wt("alpha-one") / "x"))
        self.assertEqual(self.state("alpha-one"), "Running")
        p = self.hook("SessionEnd", reason="prompt_input_exit"); self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(self.state("alpha-one"), "Paused")
        self.assertIsNone(self.listing()[0]["writer"])

    def test_session_end_does_not_pause_another_sessions_lane(self):
        self.ok("create", "alpha-one")
        self.ok("start", "alpha-one", LANE_SESSION_ID="sess-bbbb-2222", LANE_SESSION_PID=str(os.getpid()))
        self.hook("SessionEnd", reason="other")
        self.assertEqual(self.state("alpha-one"), "Running")
        self.ok("pause", "alpha-one", LANE_SESSION_ID="sess-bbbb-2222", LANE_SESSION_PID=str(os.getpid()))

    def test_session_end_tears_down_a_lane_removed_by_the_exit_prompt_only_when_checks_pass(self):
        self.ok("create", "alpha-one"); self.ok("create", "beta-two")
        for n in ("alpha-one", "beta-two"):
            self.tool("Write", cwd=self.wt(n), file_path=str(self.wt(n) / "x"))
        self.commit_in("alpha-one", push=True)
        self.git("worktree", "remove", "--force", str(self.wt("alpha-one")))
        self.git("worktree", "remove", "--force", str(self.wt("beta-two")))
        self.prs("beta-two", {"number": 5, "state": "MERGED", "headRefOid": "x", "baseRefName": "main"})
        p = self.hook("SessionEnd", reason="prompt_input_exit")
        self.assertIn("alpha-one: left as it is", p.stderr)
        self.assertEqual([i["name"] for i in self.listing()], ["alpha-one"])
        self.assertEqual(self.state("alpha-one"), "Leftover")

    def test_worktree_create_makes_a_lane_and_prints_its_path_and_refuses_agent_names(self):
        p = self.hook("WorktreeCreate", name="alpha-one")
        self.assertEqual(p.returncode, 0, p.stderr); self.assertEqual(p.stdout.strip(), str(self.wt("alpha-one")))
        self.assertEqual(self.hook("WorktreeCreate", name="agent-a1b2c3").returncode, 2)
        self.assertEqual(self.hook("WorktreeCreate", name="valid-name", agent_id="a1").returncode, 2)
        self.assertEqual(self.hook("WorktreeCreate", name="Bad Name").returncode, 2)

    def test_worktree_remove_runs_teardown_with_its_refusals(self):
        self.ok("create", "alpha-one")
        p = self.hook("WorktreeRemove", worktree_path=str(self.wt("alpha-one")))
        self.assertEqual(p.returncode, 2); self.assertIn("finish rule not met", p.stderr)
        self.prs("alpha-one", {"number": 1, "state": "CLOSED", "headRefOid": "x", "baseRefName": "main"})
        self.assertEqual(self.hook("WorktreeRemove", worktree_path=str(self.wt("alpha-one"))).returncode, 0)
        self.assertFalse(self.wt("alpha-one").exists())

    def test_heartbeat_refreshes_only_old_beats(self):
        self.ok("create", "alpha-one")
        self.tool("Write", cwd=self.wt("alpha-one"), file_path=str(self.wt("alpha-one") / "x"))
        self.edit_record("alpha-one", lambda r: r["seats"]["writer"].update(heartbeat="2020-01-01T00:00:00Z"))
        self.hook("UserPromptSubmit", prompt="hi")
        self.assertGreater(self.listing()[0]["writer"]["heartbeat"], "2026")

    def test_session_without_a_pid_goes_stale_by_heartbeat(self):
        self.ok("create", "alpha-one")
        self.tool("Write", cwd=self.wt("alpha-one"), file_path=str(self.wt("alpha-one") / "x"))
        self.assertNotIn("stale", self.ok("list").stdout)
        self.edit_record("alpha-one", lambda r: r["seats"]["writer"].update(heartbeat="2020-01-01T00:00:00Z"))
        out = self.ok("list").stdout
        self.assertIn("stale writer seat", out); self.assertIn("heartbeat", out)


if __name__ == "__main__":
    unittest.main()
