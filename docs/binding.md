# Binding of the lane-model project

Appendix A of the model says every project keeps its binding with its workflow docs. This is this project's. It was written on 2026-10-09 against model V3 as changed by Appendix C of `docs/model/2026-10-06-lane-model-v3.parked.md`.

## Terms

| Term | lane-model |
|---|---|
| Main worktree | The clone. Read-only by hook (I8) |
| Worktree location | `.claude/worktrees/<name>` |
| Git host | GitHub, through `gh`, asked on every sync and every teardown |
| Landing methods allowed | Read from the host on every sync. On the real repository: squash and merge commit, rebase off, so catch-up by merge |
| Lane classes | One, `pull-request`, the default, so no lane is marked. Declared in `lanes.toml` |
| Lane name | `[a-z0-9]+(-[a-z0-9]+)*`, 3 to 40 characters. Branch, directory and name are the same string |
| Binding restrictions | A session may run several lanes. A subagent acts as its session |
| Agent harness | Claude Code, hooks in `.claude/settings.json`, one entry point `scripts/lane-hook`. Every hook runs the main worktree's copy: the command cuts `$CLAUDE_PROJECT_DIR` at `/.claude/worktrees/`, so it must change with the worktree location |
| Lane tool | `scripts/lane` |
| Seats | `lane.json` in the lane worktree's own Git directory (`.git/worktrees/<n>/lane.json`), written atomically under a lock. Holds runner, writer, starting point, port |
| Roster | `lane.<name>.class` and `.created` in the Git config, so a branch traces to its lane after the worktree is gone |
| Session ledger | `.git/lane-sessions/<session id>`: the lanes a session sat in, read by the session-end hook |
| Runtime | `sample/server.py`, a small HTTP server |
| Data | `$LANE_DATA_ROOT` or `~/.local/share/lane/<project id>/<name>/`: a SQLite file and the runtime log |
| Identity | Lane id `<slug>-<6 hex of the main path>-lane-<name>`, carried on the runtime's command line as `--lane-id`. Port: first free from 3100, recorded in the seats file |
| Dependencies | python3 3.11+, git, gh |
| Pause | `lane pause`. The session-end hook pauses what the session runs, on every end reason |
| Housekeeping run by | Nobody on a schedule. `scripts/lane housekeeping`, by hand |
| The human's word to discard work (I1) | `teardown --discard` |
| The human's word to tear down an unfinished lane (I4) | `teardown --unfinished` |
| Liveness | Pid plus process start time. A session with no findable pid falls back to its heartbeat, limit 30 minutes. The list says which test declared a seat stale |

## Capabilities (sections 9 and 13.5)

Tested means a real headless Claude Code session 2.1.295 on 2026-10-09 with the hooks wired, in a scratch project. Unit means the hook was fed the JSON shape and answered correctly, nothing more.

| Capability | Has it | Evidence |
|---|---|---|
| Refuse removal of a lane worktree outside teardown | Partly | `ExitWorktree remove` is refused by the hook (tested). Removal at session exit fires `WorktreeRemove`, which runs teardown with its refusals and keeps the lane when teardown refuses (measured, for a lane made by `WorktreeCreate`). `git worktree remove` and `rm -rf` cannot be refused and leave a Leftover |
| Each runner signals its end | Sessions only | `SessionEnd` pauses the session's lanes and releases its writer seat (tested, reason `other`). A person or script that dies leaves a Runaway lane |
| Record runner, writer and liveness | Yes | Lane tool. Session pid found through an undocumented harness session record or an ancestor command line carrying the session id (tested; which of the two answered was not recorded) |
| Find every process of a lane | Mostly | `--lane-id` on the runtime's command line, plus its descendants. A process that detaches and reparents to init is missed (gap L2) |
| Refuse a write in the main worktree | Mostly | Edit, Write, NotebookEdit refused (tested). Bash writing shapes refused (unit; the model in the real session declined to try). Holes listed in `AGENTS.md` |
| Refuse a write in a lane by someone other than its writer | Edit, Write, NotebookEdit | The first edit takes the writer seat, a second session is refused (unit). Bash writes in a lane are not covered |
| Session signals its end with reason and working directory | Yes | Tested |
| Harness records which session is in which worktree | No | The lane tool keeps the ledger itself |

## What the harness does, measured

| Question | Answer |
|---|---|
| Does `EnterWorktree` with a name fire `WorktreeCreate`? | Yes. The hook creates the lane and the session is placed in it |
| Does `EnterWorktree` with a path fire anything? | No `WorktreeCreate`, no `CwdChanged`. Prep runs from the `PostToolUse` hook of `EnterWorktree` instead (unit) |
| Does subagent worktree isolation fire `WorktreeCreate`? | Yes, with name `agent-<hex>` and no `agent_id`. The hook refuses by that name and the agent sees the reason |
| Do subagent hooks carry the parent's `session_id`? | Yes, with `agent_id` and `agent_type` added. A subagent therefore sits in its session's seats |
| What does `WorktreeRemove` send, and when? | `worktree_path`, the lane's absolute path, with `cwd` inside the lane. A clean `claude --worktree <name>` session fires it at exit without asking, though it is named. Exit 2 from the hook keeps the directory and the lane |
| Does `ExitWorktree remove` reach the hook? | Only with `discard_changes: true`. Without it the harness refuses on its own for a hook-created worktree |
| Does a session see the lane environment? | Yes. `SessionStart` exports `LANE_SESSION_ID`, `LANE_SESSION_PID` and its start time to every later Bash command through the env file |
| Does the harness block main-worktree writes by itself? | Yes for a session that entered a worktree. The lane hooks matter for sessions that did not |
| Where does a `claude --worktree` session run its hooks from? | `$CLAUDE_PROJECT_DIR` is the lane, so a command built on it ran the lane branch's copy of the hook. After teardown at exit, `SessionEnd` found no script and failed (seen by hand in an interactive session, 2026-10-09). Hence the cut to the main worktree |

## Open gaps

| Id | Gap |
|---|---|
| L1 | Stacked lane whose parent was squashed or rebased, caught up by replay: 12.4 asks for the parent's merged head to be read and only the lane's own commits replayed. Not implemented. Matters only where the repository allows rebase landing, which this one does not |
| L2 | A runtime process that detaches from the lane's process tree is not traced to its lane |
| L3 | A lane removed by the exit prompt, `git worktree remove` or `rm` becomes a Leftover. The session-end hook tears it down by name only for lanes in the session ledger; the rest wait for `list` and `housekeeping` |
| L5 | A person's identity is their login name, and liveness is the shell that ran the command. Pausing from another terminal as the same person is allowed. The model does not say whether a person is a login or a shell |
| L6 | The session pid sources are undocumented harness behaviour and may change |
| L7 | Bash writes inside a lane do not take the writer seat |
| L8 | A `claude --worktree` session has the lane as its project, so it probably reads `.claude/settings.json` from the lane branch. A lane that edits the wiring may change which hooks guard it. Not measured |
