# lane-model

An implementation of the lane model (`docs/model/`) with Git, GitHub and Claude Code. A lane is one task with its own worktree, runtime and data. The tool keeps lanes apart, keeps runtimes off when nobody needs them, and refuses to lose work.

The model is in `docs/model/`: V3 is the interface (`2026-10-06-lane-model-v3.md`), its parked parts hold the Git and harness integrations and the change log.

## What is here

| Path | What |
|---|---|
| `scripts/lane` | The lane tool. Python 3.11+, standard library only |
| `scripts/lane-hook` | The one Claude Code hook entry point |
| `lanes.toml` | The class file: naming rule, paths, runtime, the pull request class |
| `.claude/settings.json` | Wires the hooks |
| `sample/server.py` | A small runtime with real state, so pause, resume and teardown have something to keep and remove |
| `AGENTS.md` | The method, for the agent |
| `tests/` | Unit tests against a local bare remote and a fake `gh` |

## Set up

You need `git`, `python3` 3.11 or newer, and `gh` logged in to the repository's host. Claude Code reads `.claude/settings.json` after you trust the project.

The lane tool needs `origin` on GitHub. The repository should allow squash and merge commit and not rebase, so catch-up is by merge. Lanes appear under `.claude/worktrees/`; their data under `~/.local/share/lane/`.

## Use

```
scripts/lane create fix-login-redirect
scripts/lane start fix-login-redirect
scripts/lane list
scripts/lane pause fix-login-redirect
scripts/lane teardown fix-login-redirect     # after its pull request is merged or closed
scripts/lane housekeeping                    # by hand, from the main worktree
```

`list` shows every lane with its state, whether its finish rule is met, who runs it and who writes in it. Anything wrong is listed under the table with the command that fixes it.

## Test

```
python3 -m unittest discover tests
```

## Adopt in another project

The lane tool here is one implementation of the model, not the model itself. Each project can have its own lane tool and its own settings, as long as it keeps the model in `docs/model/`.

To start from this one, copy `scripts/lane`, `scripts/lane-hook` and `lanes.toml`, edit the class file (slug, runtime command, naming rule), and add the hooks to the project's `.claude/settings.json`. The runtime command must carry `{lane_id}`.
