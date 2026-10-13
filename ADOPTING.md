# Adopting the lane model: notes for an implementation

`LANE-MODEL.md` says what must hold. `IMPLEMENTATION.md` shows one way to make it hold, with a runtime that is one process, no dependencies and no landing step. A project that adopts the model usually has more than that: a runtime with dependencies (a container engine, a database server), a landing step with gates, worktrees that existed before the tool, and a harness whose sessions come and go. These notes come from the first port of that kind, in October 2026: a web application with a database-backed runtime, a thousand-line shell script that ran its lanes, and a landing command with a dozen gates, replaced by one tool written against the model. Each note names the rule it serves. None of them changes the model. Where the reference tool in this repository does not yet do what a note says, the note says so.

## 1. Write the binding before the tool

The model is a set of terms. The first artefact of a port is the table that says what plays each term in the project: main worktree, lane worktree, starting point, safe copy, finish rule, runner, writer, seat, reach, prep, pause, teardown, housekeeping, Runaway, Leftover, each with the thing that plays it and the command that does it. That table is the checklist for everything that follows. The code review reads the diff against it, the docs review reads the workflow against it, and a reader who knows the model finds the project's choices in one place. The port wrote the table after the code, and each place where the two disagreed cost a review round.

The binding says what plays a term. It never restates the rule, which stays in the model file, checked in unchanged.

## 2. A change to the tool acts only once it has landed

The harness runs the hook from the main worktree whatever worktree the session is in (`.claude/settings.json` strips the lane path off `CLAUDE_PROJECT_DIR`). A change to the tool, the hook, the lane file or the hook wiring is made in a lane like any other change (I8). It has no effect until it has landed and the main worktree has pulled it. Say so in the agent's workflow document, next to the rule that every change is made in a lane. Otherwise a session that changes the hook expects to see the change act, and reports a bug.

The lane that brings the tool into a project is the hard case. The tool reads its lane settings from the main worktree, which has none yet, so that lane cannot be exercised against its own repository, and the hook it adds is not wired there either. What worked:

- Run every real probe (create, start, the hook on each wired event, session end, teardown) in a clone of the branch, in a scratch directory, with `origin` pointed at the real remote, so the Git host answers as it will in the project.
- Land the branch through whatever landed changes before it: the previous script, or a push and a pull request by hand.
- Pull the main worktree. Only then is the tool live, and the first lane that uses it is the next one.

Decide the bootstrap path before writing code, since it decides how the first pull request is made and what the previous tooling must still be able to do on the day.

## 3. A session is its process, not its id

An agent harness gives a session a new id on a clear of its context and on a resume, while the process that runs the session stays the same. A seat keyed by the session id then looks like another live session's seat. The tool refuses the session its own writer seat, which is what section 7.1 asks for when the seat really is someone else's. The session's end then pauses nothing, because the ledger lists its lanes under the old id. The reference tool keys session seats by id, so this applies to it.

Rules that fixed it:

- Two session seats are one actor when both record a process (pid and the process's start time) and the two match. The id is a label. A seat with no known process matches by id alone.
- On a session start whose source is a clear or a resume, when the process is found: walk the whole inventory of lanes, rewrite the seats that belong to this process under the new id, merge the old id's ledger into the new one, and delete the old ledger only when a seat moved. Read every record first and take the lock only on the records that change.
- A session end is not one event. The harness ends a session on a clear and on a resume too. Pause the lanes the session runs and release its writer seats only on the reasons that end the process (`prompt_input_exit`, `logout` and `other` in Claude Code, as of the port), and leave the seats alone on `clear` and `resume`, which the next start re-keys.
- Export the session's identity to the shell on every start, empty when the process was not found or the tool could not load. Otherwise a shell started from inside another session inherits the parent session's values and acts as that session.

## 4. The hook fails closed and releases only what it took

An error inside the hook is not a reason to let the call through. In Claude Code a hook that exits 2 blocks the call and a hook that exits 1 with a traceback allows it. Catch every error after the refusals and exit 2 with the error text, on every event that decides.

A Bash command may reach several lanes: the one it runs in after its `cd`s and every lane a path in it names. The hook takes one writer seat per lane. When the second lane refuses, the hook denies the call, and the seat the call took in the first lane must not stay taken. Keep the list of seats this call took, excluding the ones the caller already held, and release exactly those on a refusal or an error. The same holds on the file-tool path. The reference tool takes the seats in one pass and leaves the first taken when the second refuses.

## 5. What the guard reads

The guard decides from the directory the command runs in after its `cd`s and from the paths it names. It matches the shapes it knows: a redirect, the plain writers, the git subcommands that write, package installs, download flags, in-place editors. It sees through the wrappers it knows (`env`, `sudo`, `doas`, `command`, `nohup`, `time`, `exec`, `nice`, `timeout`). It blanks quoted text first, including ANSI-C quoting and heredocs, so a quoted `>` is not a redirect. `case` arms, line continuations and comments need their own handling, and the reviews found a hole in each.

Three decisions that held up:

- A path into another lane takes that lane's writer seat too. `rm -rf <worktrees>/<name>` from anywhere takes the writer seat of the lane it names and leaves a Leftover, which the next list shows (I3). A path outside the project is nobody's lane and is fine.
- A call of the lane tool itself is never a writing shape. Each of its commands applies the model's checks itself, and `run <cmd>` counts as whatever `<cmd>` does.
- `(( x > 3 ))` reads as a redirect in the main worktree. Document the workaround (`[ "$x" -gt 3 ]`) instead of parsing arithmetic.

The hook runs on every Bash call under a timeout, so the lexer must be linear in the command's length. The port's `case` handling and ANSI-C quoting were quadratic until a review measured them. A 400 KB command now takes a tenth of a second. Keep a performance test.

What the guard cannot see is a list the docs must carry (I8): a command run by another interpreter or program (`eval`, `sh -c`, `python3 -c`, `xargs`, `find -exec`), wrappers and writers it does not know, git plumbing, a symlink made and used in one command, a `cd` that fails at run time, a variable or a substitution in a target, and the parser corners found so far. Keep that list in one file and point at it from everywhere else. Turn every corner a review finds into a test case, allowed or denied, so the list and the code match.

## 6. Catch-up: declare the strategy, and hold rather than guess

The model leaves catch-up to the integration and asks it to name its source of truth and never lose a change (I7). Declare the strategy in the lane file (`catch_up = "merge"` or `"replay"`). Do not infer it from the Git host's merge settings, as the reference tool does. The strategy is the history the project wants, and a repository that allows several merge methods has no single answer.

The base is the default branch, or the base of the open pull request for a stacked lane.

The tool holds a replay, changes nothing and names the one command that clears the hold, when:

- an operation is in progress (a merge, a rebase, a cherry-pick).
- the worktree has uncommitted changes. Commit them, and a work-in-progress commit is fine. Nothing stashes, because a stash moves work out of reach of every safe-copy check.
- the replay conflicts. The tool aborts it and leaves the worktree as it was. The human runs the one rebase, resolves it and continues.
- the Git host is unreachable.
- another live writer sits in the lane.
- the lane has merge commits of its own, which a replay would flatten. Land them by another method, or pass `--flatten` on the human's word.
- `origin/<name>` holds commits the lane lacks, such as a reviewer's push or a suggestion applied on the host. A replay must not rewrite them in silence. The one exception is a remote that holds the lane's own patches under other ids, which a patch-id comparison tells apart.

After a replay, the next push of a published branch needs `--force-with-lease`, and the result line says so. Prep runs on every entry into the lane (a session starting in it, a `cd` into it, a worktree enter), before start and before land, so a catch-up never happens in the middle of a start or a land.

## 7. Lanes that predate the tool

Every project adopting the model has worktrees made by hand or by the previous script. The tool cannot know their starting point (I7), and they have no roster entry and no seats. Treat a missing record as "not adopted yet", not as a stray or as a lane with no seats:

- `list` shows the lane with that note and its fix, `prep <name>`.
- Adoption records the merge-base with the default branch as the starting point, writes the roster entry, and holds on a failed fetch (I9). It is one-way and changes no file.
- Commands that only stop or release (stop, release, pause by someone who is not the runner) adopt silently with a bare record, since they need no starting point.
- Teardown works on an unadopted lane with every check.

## 8. Runtimes with dependencies

**Identity (I6).** Derive every id from the name. When a dependency shortens the ids it receives (a container engine, a project-id limit), hash the part past the limit and keep a registry line that maps the id back to the name. Write it at the first start and remove it last at teardown.

**Teardown with the dependency down (I13, I9).** Remove what can be removed (worktree, branch, records), keep the registry line, and list the stack's remains as the lane's remaining resources until a `teardown <name>` with the dependency up. When the tool finds nothing else of the lane and the dependency is down, refuse, since nothing can tell that the lane is absent.

**Order of removal.** Stop the runtime with its data kept, then the worktree, then the data, then the records, and the registry line last. A failure halfway then leaves a Leftover the list can trace to its name, not a resource nobody can clean up.

**A failed start undoes what it made.** It undoes and names the data it created, the port it claimed and the configuration it generated. A retry then starts clean, and the lane is Prepared again rather than half-started.

**A start under way is a state the seats must show.** Land and pause leave it alone and say so, instead of pausing a runtime that is still coming up.

**Operations that reset the runtime's data run only under the live runner.** A schema check or a migration replay in a landing gate resets the lane's database. On a Runaway lane, the message names three steps: stop, start, then the operation. On another runner's lane, the command refuses, since the lane is theirs. On a start under way, it waits. Check it before the gates and again right before the reset, since the seats can change while the gates run. Runner-only commands, such as an admin console on the lane's database, name the same three steps on a Runaway lane.

## 9. Every message names the next step

The model asks that every anomaly names its fix (I10) and that every refusal says what lifts it (section 7). Most review rounds of the port were about wording, because the reader of a message is an agent that will run exactly what the message says. Cases that each took a round:

- `pause` by someone other than the runner, on a stale runner seat with the runtime up, names `stop <name>`, and on a Leftover it names `teardown <name>`.
- `start` on a Runaway lane names `stop <name>` and then `start`.
- A held prep names the one Git command the human runs, and nothing else.
- A teardown refusal says, per blocker, whether `--discard` lifts it, whether `--unfinished` lifts it, or whether nothing does (a live seat, a locked worktree, a start under way, permissions, an unreachable host).
- `list` shows the finish rule's result beside the state, "not adopted yet" where it applies, and the step that clears each Leftover.

Test the wording. A test that a command refuses is half a test. The other half checks that the refusal names the command the reader runs next.

## 10. Tests

- A fake for every program the tool calls: the host's CLI, `git` for the fetches and diffs that must fail, the dependency's CLI, the container engine, `lsof`. Each fake keeps a call log the test reads back. A failure marker, a file in the fake's directory, makes the fake fail on a path that must refuse. A hook in the fake that fails one gate by name tests the landing loop.
- A port span per test run, so suites run in parallel without taking each other's ports.
- Remove the session's identity variables from the environment in the test setup. A suite run from inside a session inherits them, and the tool then acts as that session.
- A second live session is a real subprocess that sleeps, with its pid in the seat, so liveness is tested against the operating system, not a flag.
- Feed each hook event the JSON the harness sends and read the answer. Log the real events once (the reference hook's `LANE_HOOK_LOG`) and copy their shapes into the tests.
- Tests the reviews found missing, in the order they were found: seat identity across a clear and a resume; release on a refused seat take; teardown with the dependency down; adoption; each item of the hold list; each lexer corner; the wording of each refusal; the lexer's running time.

## 11. The documents

The agent's workflow document follows the model's steps, with the project's commands filled in. Its sections are a lane from a brief (create, what prep holds on, changes that stay Prepared, when to start, how to address the lane, the seats); changes to the agent's own files; rounds of work (commit, push, report, how a runtime stops); the work finished (approved, done for now, teardown with its refusals); the project's own rules; and the I8 list last. The binding document holds the table of section 1, the catch-up, the harness's events, the commands, the states, the ports, the teardown refusals and the landing gates. A one-paragraph decision record says why the model was adopted and what the trade-off was.

Keep each long list (what the guard cannot see, what teardown refuses) in one file and point at it from the others. The port carried the I8 list in two places, and the two copies diverged within a day.

## 12. Running the port

The port ran in stages, each with its own review: the model's core (records, seats, states, create, prep, teardown, list, housekeeping); the runtime binding; the landing command; the hook; a sweep of every document and comment that named the old tool; the workflow documents; then the small fixes the reviews left. Each stage was implemented, then a stronger model reviewed the diff against the model file with a written brief, then the findings were fixed. Review and fix repeated until a review found nothing, with no cap on rounds. Before landing, the probes of section 2 ran on the clone. The reviews caught what the tests did not: a rule lost when a replaced hook was deleted, an ordering that made a Leftover untraceable, and the messages of section 9. A review brief holds the model file, the stage's scope, the ordering rules, and the instruction to name the rule each finding breaks.
