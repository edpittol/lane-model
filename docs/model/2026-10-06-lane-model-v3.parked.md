# The lane model, parked parts

Parked parts of V3 (`2026-10-06-lane-model-v3.md`, in this directory), carried over on 2026-10-06 from `2026-09-30-lane-model-v2.parked.md` with their numbers unchanged: sections 9 to 14 and appendices A and B. Sections 1 to 7 stay in V3, and a reference here to one of them points there. V3 itself refers to nothing in this file. Appendix C is the change log of V3; V2's change log stays in the V2 parked file.

## 9. Capabilities that vary

Some invariants can only be enforced in code when the environment offers a matching capability. When one is missing, the invariant does not go away: it falls back to the docs, and the lane tool must at least make the consequence visible (I10). Each project's binding says which of these it has.

| Capability | Needed by | Without it |
|---|---|---|
| Something can refuse the removal of a lane worktree outside teardown | I3 | Removal always produces Leftovers; list and teardown by name carry the whole burden |
| Each kind of runner signals its end | I5 | Every end leaves a runaway, which someone stops by hand or which housekeeping reports |
| The lane tool records each lane's runner and writer, which lanes each runner runs, and whether each is still alive | I5, I12, section 7.1 | Cleanup at a runner's end pauses too much or too little; runaways cannot be told from running lanes; a lane found running can only be reported as "runner unknown"; a destructive step cannot warn that a lane is in use; stale seats need the human |
| The lane tool can find every process of a lane, not only the ones listening on its port | I5, I13 | Side processes survive pause and teardown; the list must say it cannot see them |
| Dependencies can be queried for what they hold, by lane id | I10, I13 | Orphans are invisible while the dependency is down; the list must say so |
| Dependencies accept any id the lane tool derives, or document how they shorten it | I6 | Long names collide; the lane tool must shorten ids itself, with a hash, and keep a registry |
| Something can refuse a write in the main worktree, whatever writes it | I8 | The main worktree rule is partly docs-only; the uncovered paths are named |
| Something can refuse a write in a lane worktree by anyone other than its writer | I12 | The writer rule rests on the writer seat and the refusal of section 7.1; the list says so, and the docs name who can still write unchecked |

## 10. Every change to the lane tooling

A change to the lane tool, a hook, a setting, a lane class, the housekeeping procedure or the use of an integration answers these before it lands:

1. Which invariants does it enforce or rely on?
2. Which transitions (section 7, and the rows an integration adds) does it add, change or remove? Update the tables of section 7 and the diagram of section 6 in the same change.
3. For each transition into the states it touches, does every invariant still hold? The states include the anomalous ones: Leftover, Runaway, a crashed runner, a second writer in the same lane, a runner of several lanes, a runtime started by hand or by a script, a lane whose marker matches no class, and for an integration the cases it lists.
4. Can it leave anything running that no runner needs (I5)?
5. What does it do when a tool it calls is missing or unreachable? It must satisfy I9.
6. What Leftovers, Runaway lanes and stale seats can it produce, and does the list show them with their fix (I10)?
7. Does housekeeping still find and tear down every lane it should, by the names it reads (I6, I11)?
8. Does it rely on a capability of the environment or of an integration, and does the project's binding say the project has it?
9. If it adds or changes a lane class, does the class fill in every setting of section 3 and of the integrations it uses, and keep every rule there? If it changes a class's values, does every existing lane of the class still keep every invariant under the new values? If it makes another class the default, does the project have no unmarked lane? If it removes a class or changes its marker, does that class have no lane?

A change that cannot answer one of these says so where it is reviewed, as an open gap with an id, so the next review does not have to discover it.

## 11. The plain class: lanes without version control

The plain class fills in every setting of section 3 with nothing beyond a file system with directories, the lane tool and one comparison (section 11.3). It shows that the interface can be implemented with no version control system and no agent harness. It stands beside the pull request class of section 12.3, and the model makes neither the default: each project declares which of its classes is its default class.

### 11.1 Settings

| Setting | Plain class |
|---|---|
| Marker | Set by the project |
| Runtime | On demand |
| Runners | Any: a person who starts it by hand, or a script |
| Safe copy | The main worktree: every change in the lane worktree is landed |
| Finish rule | The human's word |

### 11.2 What the class decides in the flow

| Transition | Plain class |
|---|---|
| Land | Someone brings the lane's changes into the main worktree. Who and how is the project's business |
| Finish | The human says the lane is finished |
| Teardown | The safe-copy check: every change in the lane worktree is in the main worktree. A change that is not refuses the teardown, unless the human says to discard it |

A lane of this class has no sync. It keeps the starting point it was created from until it is torn down (I7).

Since nothing but the human's word finishes a lane, housekeeping matters more here: its report of lanes whose seats have both been empty for longer than the project's limit is what keeps them from piling up unseen.

### 11.3 What this class needs

| Dependency | Used for |
|---|---|
| A way to compare a lane worktree with its starting point and with the main worktree | Telling a lane's changes from what landed in the main worktree after the lane started, and proving the lane's changes are landed (I1) |

When the comparison cannot be made, teardown refuses (I9).

## 12. Integrating Git

This section adds Git and a web-based Git host with pull requests to the model. Nothing in sections 1 to 10 changes; every term below is either bound to a Git object or added.

### 12.1 What Git binds

| Model term | With Git |
|---|---|
| Main worktree | The repository's original worktree, on the default branch, current with the remote and clean |
| Lane worktree | A Git worktree on a branch of its own. The branch carries the same name as the directory, marker included, so the class is readable from the branch too. The naming rule and the markers therefore only allow names Git accepts as branch names |
| Starting point | The commit the lane's branch was created from, taken from the remote base and not from the main worktree's local state |
| Change | A commit on the lane's branch, or an uncommitted change in its worktree |
| Landed | Contained in the base on the remote, by whichever landing method the Git host applied |
| Teardown | Also removes the local branch. Never the remote branch or the pull request |
| Leftover | Its remaining resources also include a local branch without a worktree, and a worktree entry whose directory is gone |

### 12.2 Added terms

- **Git host.** The web-based service that holds the repository's remote (`origin`), its pull requests and their state, reached over the network. It is the source of truth for everything about a pull request, including its target branch, which can change after the pull request is opened.
- **Pull request.** A request to land a branch on a target branch, reviewed and merged or closed on the Git host. Called a merge request on some hosts; the model means the same thing.
- **Landing method.** How the Git host lands a pull request on its base. There are three, and a repository may allow any combination of them; which ones it allows is read from the Git host.
  - **Squash:** the pull request's commits become one new commit on the base. The lane's own commits never reach the base.
  - **Merge commit:** the lane's commits reach the base as they are, joined by a merge commit.
  - **Rebase:** the lane's commits are replayed onto the base as new commits. The originals never reach the base, and the Git host may refuse a branch that contains merge commits.
- **Base.** The branch the lane's work is meant to land on. Once the lane has an open pull request, the base is that pull request's current target branch as the Git host reports it, read again every time it is needed and never kept locally; before the pull request exists, the base is the default branch.
- **Stacked lane.** A lane whose pull request targets another lane's branch instead of the default branch.
- **Catch-up.** Bringing a lane that has commits of its own up to date with its base, by merge in or by replay (section 12.4).
- **Merge in.** A catch-up that adds one merge commit to the lane, with the base as the other parent. The lane's existing commits stay as they are.
- **Replay.** A catch-up that recreates the lane's own commits, one by one and in order, on top of the base, and moves the branch to the result. In Git this is a rebase; the model says replay to keep it apart from the rebase landing method.
- **Published.** A lane whose branch has been pushed to the Git host. From then on its history is rewritten only where section 12.4 requires it, and then only by a push that refuses to overwrite commits it has not seen.

The Git host is an added actor. It holds remote branches and pull requests, may delete a head branch on merge, and keeps the merged head reachable. It knows nothing about local lanes. Merging or closing a pull request stays outside the model, as landing does.

### 12.3 The pull request class

Git adds two settings to section 3, Pull request and Base, and one class that uses them. A project declares which of its classes is its default class; one that runs only the pull request class makes it the default, so its branches carry no prefix.

| Setting | Pull request class |
|---|---|
| Marker | Set by the project |
| Runtime | On demand, when the change needs the running application |
| Runners | A person or a script; with an agent harness, a live session (section 13) |
| Safe copy | A remote reference, or the head of a merged pull request |
| Finish rule | Its pull request merged or closed |
| Pull request | Required before the lane can finish |
| Base | The pull request's target on the Git host; the default branch before the pull request exists |

The safe copy covers every landing method: after a merge commit the lane's commits are on the base itself; after a squash or a rebase they are on no branch at all once the Git host deletes the head branch, and only the merged pull request's head still contains them. Uncommitted changes are in no safe copy, so teardown refuses them.

The lane's local branch, its remote branch and its pull request head carry the same name. A lane that pushes to a branch of another name breaks identity (I6): nothing that looks up the pull request by name will find it.

### 12.4 Sync with base

Sync brings a lane up to date with its base, so the work is tested against the branch it will land on. It runs as part of prep, at create, at every resume and at every other prep trigger an integration adds (section 13.4), and never in the middle of a stretch of work. It is the catch-up that I7 leaves to an integration: its source of truth is the Git host.

#### Catch-up method

A lane with commits of its own catches up in one of two ways. The landing methods the repository allows decide which one. The lane tool picks the least destructive method that keeps every allowed landing method possible.

| Landing methods allowed | Catch-up | Why |
|---|---|---|
| Squash, merge commit, or both | **Merge the base in** | Nothing is rewritten. The lane tool never pushes over a published branch, and a reviewer's commits on it stay where they are. Under squash the catch-up merges disappear on landing. Under merge commit they become part of the base's history |
| Rebase, alone or with others | **Replay the lane onto the base** | A rebase landing needs a linear branch, and the Git host may refuse one with merge commits. Replaying rewrites the branch. A published lane is then pushed with a push that refuses to overwrite commits it has not seen |

A repository that does not want catch-up merges in its history turns off merge-commit landing. A repository that does not want its published branches rewritten turns off rebase landing. The repository makes this choice in the Git host's settings. The lane tool reads it from there on every sync, not from its own configuration.

#### Outcomes

Every run ends in exactly one outcome, reported in one line. Held changes nothing and names the one step that moves the lane forward.

| Situation | Outcome | What the lane tool does |
|---|---|---|
| The lane already contains its base and everything on its remote branch | **Current** | Nothing |
| The lane has no commits of its own | **Moved** | Moves the branch to the base. Uncommitted changes are kept |
| The lane has commits of its own and catches up by merge | **Merged** | Merges in the commits its remote branch has and the worktree lacks, then merges the base in. The next push is a plain push |
| The lane has commits of its own and catches up by replay | **Replayed** | Replays the lane's local commits onto its remote branch first, so no other person's commits are lost, then replays the lane onto the base. For a published lane, it says that the next push must refuse to overwrite commits it has not seen |
| The lane tool cannot reach the Git host (offline, not authenticated, client missing) | **Held** | Nothing. Names what is missing |
| A catch-up is needed and the worktree has uncommitted changes | **Held** | Nothing. Asks for a commit, and a work-in-progress commit is fine |
| The lane catches up by replay and has merge commits of its own | **Held** | Nothing, because a replay would flatten them. Names the two ways forward, a replay on the human's word (section 12.6) or landing the pull request by another method |
| The catch-up conflicts | **Held** | Restores the worktree as it was, lists the conflicting files and names the step to resolve them |
| The branch's prefix matches no declared class | **Held** | Nothing. Names the way forward: declare the class |

#### Rules

- On every run, sync asks the Git host for the base and for the allowed landing methods, and trusts no earlier answer. A pull request's target and the repository's settings can change at any time. Sync therefore needs the network. Without it the outcome is Held. Sync never falls back to the default branch, to a remembered base or to a default catch-up method (I7, I9).
- Sync never loses a commit. A merge catch-up cannot lose one. A replay first brings in whatever the remote branch has, and its push refuses to overwrite anything it has not seen.
- When a stacked lane's parent has landed, the Git host retargets the lane's pull request, and the parent's base becomes the lane's base. What happens next depends on how the parent landed.
  - **Parent landed by merge commit.** The parent's commits are now on the base, unchanged. Either catch-up applies without extra steps.
  - **Parent squashed or rebased, catch-up by merge.** Merging the base in brings the parent's new commits. The lane already holds the same changes as the parent's original commits, so the merge is clean except where the parent changed after the lane branched from it.
  - **Parent squashed or rebased, catch-up by replay.** The lane still carries the parent's original commits, which no longer exist on the base. The lane tool reads the parent's merged head from the Git host and replays only the commits after it, which are the lane's own. No manual step is needed.

### 12.5 Added transitions and checks

| Transition | What Git adds |
|---|---|
| Create | The lane's branch starts from the remote base, not from the main worktree's local state |
| Prep | A check: no Git operation is in progress (merge, rebase, cherry-pick, revert). When it fails: stop, name the operation to finish or abort |
| Sync with base | A new transition, part of prep, owned by the lane tool (section 12.4) |
| Open pull request | A new transition, in a class that requires a pull request. Trigger: work finished. Checks: branch pushed; no pull request open for it yet |
| Finish | For the pull request class, the rule is read from the Git host on every ask and stored nowhere: the pull request is merged or closed, by whoever the repository's review process allows |
| Teardown | The safe-copy check becomes two: no uncommitted changes; every local commit on a remote or in a merged pull request head. The lane tool fetches the merged pull request's head from the Git host and checks containment against it, since after a squash or a rebase with the head branch deleted it is the only copy. When the Git host cannot be asked, teardown refuses (I9) |
| Lane worktree removed outside teardown | Also `git worktree remove`. Teardown by name then runs the same checks against the remaining branch |

A branch whose prefix matches no declared class is the unreadable class of I9: teardown refuses and sync is Held.

### 12.6 Flatten on replay

A replay catch-up over the lane's own merge commits flattens them without losing their changes (section 12.4). Sync does it only on the human's explicit word for that lane, as teardown does when it discards work (I1) or removes an unfinished lane (I4).

### 12.7 What this integration needs

| Dependency | Used for |
|---|---|
| Git, with worktrees | One worktree and one branch per lane; "contains" and "missing from every remote" for I1 |
| A web-based Git host, reachable over the network, with an API the lane tool can call | Pull request state for the finish rule (I4); the pull request's current target and the repository's allowed landing methods for sync; merged pull request heads for I1 |
| The Git host keeps a merged pull request's head reachable after deleting its branch, and lets the lane tool fetch it | I1 in a repository that allows squash or rebase. A repository that allows only merge commits does not need it |

Being unable to reach the Git host is not a degraded mode with its own rules: every step that needs it refuses (teardown) or is Held (sync), and says the Git host could not be asked (I9).

The checklist of section 10 gains these anomalous cases: the Git host unreachable, a lane whose branch has another name, a branch whose prefix matches no class.

## 13. Integrating an agent harness

This section adds an agent and the harness it runs in. Nothing in sections 1 to 10 changes. The harness is useful to the model in three ways: it can create lane worktrees, it knows when a session ends, and it can refuse an action before it happens.

### 13.1 Added terms

- **Agent harness.** The program the agent runs in. It may create and remove worktrees, mark them as in use, and offer hooks that run on its actions and at the end of a session.
- **Session.** One agent conversation, together with every subagent it launches. A subagent acts under its session and is never a runner or a writer of its own. A session may run several lanes at once.
- **Round.** One cycle of an agent's work in a lane, which ends with the work saved and a report to the human. With Git, saved means a commit pushed to the lane's remote branch.

### 13.2 What the harness binds

| Model term | With an agent harness |
|---|---|
| Runner | A live session is a third kind of runner. A class says whether it allows it |
| Writer | A session is a writer, and so it takes the writer seat. A session may be a lane's runner and its writer at once |
| Runner's end | A session's end is its end as a runner, so the lanes it runs pause. A session also pauses a lane it runs once the lane's finish rule is met, or earlier on its own judgement |
| Seat | The harness or the lane tool seats a session when it starts in a lane, and empties its seats when the session ends |

### 13.3 Added actors

| Actor | Does | Never does |
|---|---|---|
| Agent (in a session) | Creates lanes, starts a runtime only as the lane's class allows, may run and write in several lanes at once and delegate work in them to subagents, works in rounds, pauses its lanes, tears down its own finished lanes, runs housekeeping when asked | Discards work the safe copy does not hold, tears down a lane whose finish rule is not met, edits the main worktree, leaves a runtime running that no runner needs, starts a runtime it does not record as its own, acts on a lane running under another runner before the human has seen the warning (section 7.1), speaks for the human where a step takes the human's explicit word |
| Agent harness | Creates worktrees, marks them in use, offers to keep or remove them at session end, runs hooks | Knows nothing about runtime or data; its own removal is never trusted to be complete |

### 13.4 Added transitions and checks

| Transition | What the harness adds |
|---|---|
| Create | The agent may create the lane through the harness, on a human brief |
| Round | A new transition. Trigger: work done. Owner: the session that is the lane's writer. Checks: the session has the writer seat; the build and checks the project requires. When a check fails: report, and save a broken round only when asked |
| Pause | Also triggered by the session's end hook, and by the lane's finish rule being met, even while the session goes on in other lanes |
| Prep | Also runs when a session starts in a lane, before any work, so a lane that never resumes is still synced |
| Runner ends | A session exits, logs out or crashes. On a clean end, exactly the lanes that session runs pause. On a crash they become runaways |
| Lane worktree removed outside teardown | Also the harness's own removal, refused where the harness lets a hook refuse it |

### 13.5 Capabilities the harness may offer

| Capability | Needed by | Without it |
|---|---|---|
| The harness lets a hook refuse its worktree removal | I3 | Removal always produces Leftovers |
| A session signals its end, with a reason and its working directory | I5 | Every session end leaves a runaway |
| The harness records which session is in which worktree, and whether it is alive | I5, I12, section 7.1 | The lane tool must keep that record itself |
| Hooks on every way the agent writes files | I8, I12 | The main worktree rule is partly docs-only, and a session can write in a lane whose writer is someone else; the uncovered paths are named |

The checklist of section 10 gains these anomalous cases: a crashed session, a second session in the same lane, a session that runs several lanes, several live sessions of one project on one machine.

### 13.6 With Git as well

This is the common case. A round ends with a commit pushed to the lane's remote branch. In a class that requires a pull request, the agent opens it once, when the work is finished. The agent never discards unpushed work, and it tears down a lane only after its pull request is merged or closed.

## 14. Questions raised during the review

These were decisions, not gaps. None is open: each one is settled, or was left outside the concept on Eduardo's word of 2026-10-01 that the concept takes no question about implementation. Questions 1 to 9 keep the numbers they had before the model was made independent of Git and the harness.

1. **Review lanes** (Git). Outside the concept. The model already says a change somebody else needs goes into another lane (section 1, Writer), and that the lane's branch and its pull request carry its name (section 12.3). How a project runs review fixes is its implementation.
2. **Writers.** Settled: "one writer at a time" is a rule of the model (I12), not a setting. No class chooses who may write or how many; parallel work belongs in separate lanes.
3. **Lane data.** Outside the concept. Section 5 already says teardown destroys a lane's data. Whether a project exports any of it first is its own business.
4. **Where this document lives.** Outside the concept: it is a question of adoption.
5. **Repositories whose lanes are generated by an external package.** Outside the concept: it is a question of adoption.
6. **Stacked lanes before their pull request exists** (Git). Outside the concept. I7 already forbids guessing the base and I9 makes a step do nothing when its check cannot be made; which of the ways out a project takes is its implementation.
7. **Idle runtime.** Settled: outside the model. A runtime stops when its runner pauses it or ends; pausing one that sits unused is the implementation's strategy.
8. **Declaring classes.** Settled: in a file inside the project, next to its code; the model fixes neither its name nor its format (section 3).
9. **The word "lock".** Settled: the record is the lane's two seats, runner and writer (section 1; the record was first named the claim, the runner the holder), so it is not confused with the worktree lock of Git and of a harness.
10. **Telling a lane's changes from the main worktree's progress.** Settled: the model requires a recorded starting point (section 1, I7), and the implementation chooses how to record it.
11. **The class marker.** Settled: the class is read from the lane worktree's directory name, and how the marker is written is the implementation's choice (section 3).
12. **The name "pull request class".** Settled: kept for the class of section 12.3.
13. **The resting limit.** Settled: the model gives no default value. Each project sets it.
14. **Landing in the plain class.** Settled: two lanes that changed the same file are the project's business, like every other part of landing.

## Appendix A. Bindings

Each repository fills in its rows; sections 1 to 10 of the model never name these tools. The binding of the lane-model project itself is `docs/binding.md`. A binding is part of that repository's docs, not of the model, and moves there once the model is adopted.

| Term | Bettrbyus | Bettr Bowl website | Bettr Manager |
|---|---|---|---|
| Worktree location | `.claude/worktrees/` | `.claude/worktrees/` | `../bettr-manager-worktrees/` |
| Git host | GitHub, via `gh` | GitHub, via `gh` | GitHub, via `gh` |
| Landing methods allowed | Squash and merge commit, so catch-up by merge | Unverified | Merge commit by doctrine, but rebase is still allowed (B10), so catch-up by replay until rebase is turned off |
| Lane classes | Pull request class only, as the default class | Pull request class only, as the default class | No default class: no lane is unmarked. Undeclared, used by prefix: `worktree/<lane>` (close to the pull request class: runtime, pull request required) and `self-improvement/<topic>` (no runtime, the pull request stays a draft); a prototype lane with no pull request was also used (`input-borders`) |
| Lane name | Two to four lowercase words joined by dashes (`AGENTS.md` section 1) | Unverified | A slug after the prefix (`worktree/<lane>`, `self-improvement/<topic>`); its rule is unverified |
| Binding restrictions | Lanes are opt-in per clone since PR #216 (2026-10-01, `scripts/lane.sh method`); without them, work happens in the checkout and none of this model applies. With them, one lane per session (`AGENTS.md` section 1); the session-end hook pauses the lane of the working directory, which is correct only under that restriction | One lane per session | None; one orchestrator session may run any number of lanes |
| Agent harness | Claude Code (EnterWorktree, ExitWorktree, exit prompt, worktree locks, hooks) | Claude Code | Claude Code; the orchestrator session is the runner of every lane it opens, builder subagents write in them under charters that name the path, harness worktree isolation is blocked |
| Seats | The harness's worktree lock, which records a session; no runner is recorded | The harness's worktree lock | None; the orchestrator's session ledger names lanes and subagents, and is lost with the session's scratchpad |
| Lane tool | `scripts/lane.sh` (`prep`, `up`, `down`, `sweep`, `list`, `teardown`) | `scripts/lane.sh` (`prep`, `serve`, `down`, `list`, `teardown`) | `seasoned-skills` (`provision`, `teardown`, `sweep`) |
| Runtime | Next dev server; local Supabase stack | Static build served on a lane port | Dev server, graphile-worker |
| Data | Supabase containers and volumes, generated Supabase workdir | None beyond the build output | Postgres databases per lane, MinIO bucket |
| Dependencies | Docker Desktop, npm packages | npm packages (lane and main checkout) | Postgres, MinIO, pnpm packages |
| Identity derivation | `Bettrbyus-lane-<name>`, shortened by the Supabase CLI to 40 characters | Port per lane | Hashed ports, `bettr_wt_<slug>` databases, `bettr-wt-<slug>` bucket |
| Pause | `down` (`sweep` pauses every lane at once) | `down` | None. The session-end sweep (`prompt_input_exit` and `logout` only) sends SIGTERM to every `node` and `pnpm` process whose working directory is under the worktrees root, whichever session started it |
| Housekeeping run by | Eduardo's `start-my-day` skill, on a schedule Eduardo set up (launchd, 08:56), Housekeeping step 2 | The same skill, Site review step 5 | Nobody |
| The human's word to discard work (I1) | `teardown --force` | `teardown --force` | None (teardown checks only uncommitted changes) |
| The human's word to tear down an unfinished lane (I4) | `teardown --ignore-pr` | None | None |

## Appendix B. Conformance on 2026-09-30

Where each repository stands. Bettrbyus is shown on `main` after PR #198 merged (2026-09-30, 1fe8097); the website from its `AGENTS.md` on `origin/main` (its `lane.sh` and hooks were not read); Bettr Manager from the 2026-09-28 survey and the 2026-09-30 research (`../2026-09-30-bettr-manager-lanes.md`). "Docs" means the rule is written but no code enforces it. Gap ids refer to the lane lifecycle map of 2026-09-28 (`G` Bettrbyus, `B` Bettr Manager).

| Invariant | Bettrbyus `main` | Website | Bettr Manager |
|---|---|---|---|
| I1 work never lost | Holds (G5, fixed by #194) | Holds (also accepts files already on `main`) | Broken: uncommitted changes only (B3) |
| I2 refuse before destroy | Holds (G1 fixed by #198) | Holds for locks | Unverified |
| I3 one way out | Partial: harness removal refused by a hook; exit-prompt path unverified (G3) | Docs only | Broken (B1, B7) |
| I4 lane lives until its finish rule | Holds, lifted only on the human's word (G7) | Docs only | Broken (B1) |
| I5 nothing runs without a reason | Partial: pauses on session end (G2), can pause a lane another session uses; runaways from crashes not shown; side processes survive `down` (G17) | Unverified: no session-end pause found; servers left running are reported by the morning brief | Broken the other way: kills every lane's processes, including a live session's (B6), with several sessions live at once (2026-09-02); runtimes detached from their session on purpose (`setsid`, 2026-08-31); the worker survives teardown (B5) |
| I6 identity | Partial: G12 fixed; G4 open; hashed orphans unmatched by housekeeping | Unverified | Broken (B2) |
| I7 explicit starting point; with Git, explicit base and no lost commits | Partial: falls back to the default base when the Git host is unreachable; lanes pushing to another branch name get the wrong base; replays under squash-only, so published lanes are rewritten needlessly; leaves lanes with merge commits alone, as the model does only under replay | Always the default base; replays and force-pushes; landing methods unverified | Holds for create; no catch-up modelled; landing methods read from doctrine, not from the Git host |
| I8 main worktree not a workspace | Partial: file edit tools refused, shell writes not (G9, G10) | Broken by design (its section 2) | Docs only (B8) |
| I9 fail closed / still | Holds for teardown, broken for sync | Unverified | Broken: errors silenced (B6) |
| I10 Leftovers visible | Partial: prune added (G13); runaways, stale seats and remaining branches of hashed lanes not shown (G15, G16 open); no runner shown | Unverified | Broken (B2, B13); no runner recorded |
| I11 housekeeping no stronger | Broken until the skill edit (G8: the housekeeping step discards work on its own) | Same rule copied | No housekeeping (B1) |
| I12 one runner and writer, recoverable seats | Lock refused, no stale-lock path; only the session is recorded, not the runner | Lock refused, no stale-lock path | Not modelled: no seats; one mutating agent per worktree is doctrine only; provision proceeds on a worktree another session uses |
| I13 teardown removes all | Partial (G17 side processes) | Holds | Broken (B4, B5) |

The three repositories all run the pull request class under an agent harness, so I1, I4 and I7 are judged here as sections 12 and 13 extend them. No repository runs the plain class yet.

## Appendix C. Changes from V2

V3 started on 2026-10-06 as a copy of V2 as finished that day. Each change to V3 is a row below, decided or proposed.

### Carried over from V2

| Change | Where | Status |
|---|---|---|
| The default class applies only at create: a marker that matches no class never falls back to it. A project makes another class its default only while no lane exists under the bare name, since those lanes would otherwise change class without becoming new lanes | Section 3 rules, section 10 question 9 | Proposed 2026-10-04, follows from the row above and from "a lane keeps its class" |

### Changes

| Change | Where | Status |
|---|---|---|
| Finished is a predicate read live from the finish rule, not a state. The Finished node, its five edges and the Finish row go. Teardown's From is any living state | Sections 6 and 7, diagram | Decided 2026-10-08 (Q5). Fixes the deadlock of Running to Finished, the missing Finished to Leftover edge, and a stored result that contradicts 12.4 |
| Prep gains a third trigger under the harness: when a session starts in a lane. The Paused to Running edge reads "resume and prep" | Sections 1, 6, 7 and parked 12.4, 13.4 | Decided 2026-10-08 (Q6). A Prepared lane that never resumes was never synced again |
| A session pauses a lane once its finish rule is met, or earlier on its own judgement. "Work finished" goes | Parked 13.2, 13.4 | Decided 2026-10-08 (Q7) |
| A stale runner seat is replaced at Start runtime only when the runtime is down | I12 | Decided 2026-10-08 (Q17) |
| The safe-copy check fetches the merged pull request's head from the Git host | Parked 12.5, 12.7 | Decided 2026-10-08 (Q18) |
| The warning names the step that will refuse next | Section 7.1 | Decided 2026-10-08 (Q19) |
| Bettrbyus landing cell: squash and merge commit, so catch-up by merge | Appendix A | Decided 2026-10-08 (Q20) |
