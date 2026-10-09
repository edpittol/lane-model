# Working in this project

This project implements the lane model (`docs/model/`). It also uses it: the main worktree is read-only, and every change, including a change to the lane tool, is made in a lane and ships through a pull request.

## The loop

1. `scripts/lane create <name>` makes the lane from a human brief. The name is two to four lowercase words joined by dashes, 3 to 40 characters. The command prints the worktree path.
2. Enter the lane with `EnterWorktree` (name or path). Work only there.
3. Commit and push the lane branch. Open the pull request once, when the work is finished.
4. The human merges or closes it. Then `scripts/lane teardown <name>` removes the lane.

## Commands

| Command | Does |
|---|---|
| `create <name>` | Lane worktree from the Git host's base, then prep |
| `prep <name>` | Warn if the lane runs elsewhere, then sync with the base |
| `start <name>` / `resume <name>` | Start the runtime and become its runner. `resume` preps first |
| `pause [<name> \| --all]` | Stop the runtimes you run. Data stays |
| `stop <name>` | Stop the runtime of a Runaway lane (no live runner) |
| `write <name>` / `release <name>` | Take or empty the writer seat. The edit hooks take it for you |
| `seats <name>` | Show runner, writer and runtime |
| `list` | Every lane, Leftover and anomaly, each with its fix |
| `teardown <name>` | Remove the lane, only after every check passes |
| `housekeeping` | Tear down finished lanes with the same command. Report the rest. Run by hand, from the main worktree |

## Rules for the agent

- A refusal stands. A taken seat stays with whoever sits in it: make the change in another lane. Never take over a runtime, never edit around a refusal.
- Start a runtime only when you need the running application, and pause it when the pull request is open. Session end pauses what you still run.
- `teardown --discard` and `teardown --unfinished` are the human's word, one lane at a time. Never pass them unprompted. `--unfinished` does not discard work, and `--discard` does not skip the finish rule.
- A subagent acts as this session. It shares your seats and your lane. Do not create worktrees for subagents: subagent worktree isolation is refused.
- Do not run `git worktree remove` or `ExitWorktree remove` on a lane. Use `ExitWorktree keep`.
- Do not run `git worktree prune`. The tool never does, because it would erase the seats of a Leftover.

## What the main-worktree guard cannot see (I8)

The hooks refuse Edit, Write and NotebookEdit in the main worktree, and refuse Bash commands that write by a known shape while the working directory is the main worktree: redirects, `tee`, `mv`, `cp`, `rm`, `mkdir`, `touch`, `sed -i`, `git commit/checkout/reset/...`, package installs, `curl -o`. It does not see:

- an interpreter that writes (`python3 -c`, `node -e`, `bash -c`, a script that writes)
- `find -delete`, `xargs`, `eval`
- a `cd` into the main worktree from inside a lane
- any write by a person in a terminal

A session that has entered a worktree is also stopped by the harness itself, which cannot be turned off.

## Conventions

- Commit messages carry no `Co-Authored-By` or session trailers.
- Comments say only what a senior cannot read from the code. Touch only the lines the change needs.
- Tests: `python3 -m unittest discover tests`. They use a local bare remote and a fake `gh`, so they need no network.
