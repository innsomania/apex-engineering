# Persistent task system

Use [tasks.py](tasks.py) for durable multi-step software work, explicit task tracking, or work that will resume across sessions. Small one-step questions do not require a task record. The ledger is local SQLite, using Python's standard library; no database service or model API is required. Markdown boards are generated views of that ledger.

## Current Apex locations

- Tool: `/Users/<user>/Desktop/Apex Engineering/Engineering/tasks.py`
- Ledger: `/Users/<user>/Desktop/Apex Engineering/Engineering/Tasks/apex.sqlite3`
- Project label: `Apex Engineering`
- Obsidian board: `/Users/<user>/Opsidian/Apex Tasks.md`, refreshed automatically after every ledger change (configured in `Engineering/Tasks/apex.board.json`)

The ledger contains the authoritative task state and event history. Export is an explicit snapshot, not continuous synchronization. Read the ledger when resuming; do not infer live state from an old board. Keep unrelated projects in distinct project labels or separate ledgers. Never overwrite an existing ledger to initialize a session.

## Automatic board refresh

A ledger at `NAME.sqlite3` refreshes its Markdown board when `NAME.board.json` exists beside it, for example `{"output": "/Users/<user>/Opsidian/Apex Tasks.md", "project": "Apex Engineering"}`. Every committed `create`, `assign`, lifecycle transition, and `evidence` command then re-exports the board; `project` is optional. A board failure (such as an unowned destination note) never undoes the task change: the CLI prints a warning on stderr and the ledger stays authoritative. Without the config file nothing is exported automatically, and `export` remains available for manual snapshots.

## Task contract

Every task requires a project, title, bounded scope, at least one unique acceptance criterion, and one role: Engineering, Coding, Test, or Security. Engineering is the default owner for initial triage. Assign an implementation or verification task to its appropriate role before starting it. Role assignment records responsibility; it does not spawn an agent or authenticate a person.

Dependencies must already exist in the same project and cannot be cancelled. Dependencies are fixed after creation, preventing cycles through the creation API. A later requirement or changed scope belongs in a new task with explicit links, not a silent rewrite of acceptance criteria.

Use separate dependent tasks when work genuinely has separate owners or deliverables. Do not mechanically create four records for every small change. Work completion and project completion are different: a completed component does not complete the parent product's missing capabilities.

## Lifecycle

| Command | Allowed current state | Effect |
| --- | --- | --- |
| create | New task | Queue with stable ID and creation history |
| start | queued | Become active only when all dependencies are completed |
| review | active | Submit the work for acceptance evidence |
| evidence | review | Record pass/fail for one criterion with file hash, summary, and reviewer role |
| complete | review | Require passing evidence for every criterion and unchanged evidence files |
| rework | review | Return to active and invalidate current evidence |
| block | queued, active, review | Record the blocking reason |
| pause | queued, active, review, blocked | Record a pause reason |
| resume | blocked, paused | Require a continuation reason; return to queue and clear stale evidence |
| assign | queued, blocked, paused | Change responsible role with a reason |
| cancel | Any nonterminal state | Preserve history and close the task with a reason |

Completed and cancelled records reject further lifecycle/evidence/assignment changes through the API. `show` exposes the full history. `list --ready` returns queued tasks whose dependencies are all completed, in creation order. Two concurrent `start` calls cannot both claim the same task. Choosing a ready task is still subject to the user's scope and authorization.

## Commands

Use the absolute tool and store paths when working outside the Apex directory. The following commands assume the Apex directory is the current working directory. Initialize only a new ledger:

```sh
python3 Engineering/tasks.py --store Engineering/Tasks/apex.sqlite3 init
python3 Engineering/tasks.py --store Engineering/Tasks/apex.sqlite3 list --project 'Apex Engineering' --ready
python3 Engineering/tasks.py --store Engineering/Tasks/apex.sqlite3 create --project 'Apex Engineering' --title 'Fix the requested behavior' --scope 'Only the affected module and tests' --role Coding --criterion 'The requested behavior passes its focused regression test' --criterion 'Relevant denial cases preserve protected state'
```

Use the returned `APX-...` ID in subsequent commands; `TASK_ID` below stands for that actual ID. Add `--depends-on` once per prerequisite when creating a task.

```sh
python3 Engineering/tasks.py --store Engineering/Tasks/apex.sqlite3 start TASK_ID
python3 Engineering/tasks.py --store Engineering/Tasks/apex.sqlite3 review TASK_ID
python3 Engineering/tasks.py --store Engineering/Tasks/apex.sqlite3 evidence TASK_ID --criterion 1 --result pass --file /absolute/path/to/test-result.log --summary 'Observed relevant regression result' --reviewer Test
python3 Engineering/tasks.py --store Engineering/Tasks/apex.sqlite3 evidence TASK_ID --criterion 2 --result pass --file /absolute/path/to/denial-result.log --summary 'Observed relevant denial result' --reviewer Security
python3 Engineering/tasks.py --store Engineering/Tasks/apex.sqlite3 complete TASK_ID
python3 Engineering/tasks.py --store Engineering/Tasks/apex.sqlite3 export --project 'Apex Engineering' --output '/Users/<user>/Opsidian/Apex Tasks.md'
```

These are usage examples, not instructions to invent test logs. Store actual evidence in a durable location; temporary evidence may disappear before completion. A failing or missing criterion keeps a task incomplete. The tool verifies recorded results and file integrity; a human or agent must evaluate whether the evidence actually supports the criterion. It does not execute tests or judge arbitrary prose.

## Resume, stop, and failure

After interruption, inspect `list` and `show`. An active record may represent interrupted work; inspect saved artifacts and reconcile actual state before acting. Never assume the previous tool finished. A blocked or paused task needs a new applicable user instruction or resolved prerequisite before resumption. The CLI reason is a record of that event, not proof of authorization.

If the user says stop, stop immediately. Do not run a ledger or export command afterward. On a later authorized continuation, reconcile the record and append the pause/resume reason if needed. Task state is not a host cancellation mechanism.

On ledger/permissions/storage errors, report the blocker; do not repair infrastructure or silently switch stores. Mutations use SQLite transactions. Export publishes a complete file atomically and refuses to replace an unmarked note. Avoid simultaneous exports to the same destination; snapshots may otherwise overwrite each other. No automatic deletion, deployment, or publishing is performed.

## Scope of guarantees

The CLI enforces its state transitions, dependency gates, and evidence requirements. Direct database writes can bypass them; the ledger is not a security boundary or tamper-proof audit system. Reviewer names are recorded roles, not independently authenticated approvals. Completed-task evidence hashes describe the completion-time checks, not permanent immutability of external files.

This tool is a task ledger and queue, not an autonomous scheduler. It does not itself launch agents, connect external repositories, or restrict arbitrary Codex tools. The separate [Coding bridge](CODING_BRIDGE.md) can read an active Coding task and start a Codex CLI worker; Engineering still owns dispatch and acceptance. See [execution control](EXECUTION_CONTROL.md) for the remaining host control limits.
