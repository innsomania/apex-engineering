# Apex Coding bridge

`coding_bridge.py` starts a background Codex CLI process for one active ledger task assigned to Coding. It runs in the selected project directory and exposes status, follow-up, stop, and event-log commands through a local Unix socket.

## Requirements

- Python 3 with its standard library.
- The `codex` executable on `PATH`, already installed and authenticated for the current user.
- An initialized Apex task ledger and a task whose state is `active` and role is `Coding`.

The bridge does not create or modify ledger records. It reads the selected task through SQLite's read-only mode and includes its title, scope, and acceptance criteria in the initial prompt alongside the caller-supplied original user request.

## Commands

Run these from the Apex Engineering directory, replacing the example paths and task ID:

```sh
python3 Engineering/coding_bridge.py start \
  --project /absolute/path/to/project \
  --task-id APX-0123456789abcdef0123456789abcdef \
  --store Engineering/Tasks/apex.sqlite3 \
  --request-file /absolute/path/to/original-request.txt
```

`--request-file` is required. Supply a nonempty UTF-8 regular file no larger than 64 KiB. Preserve the user's wording exactly, including the original language. If the request refers to screenshots, mockups, or other assets, include their project paths or durable references in the file after the verbatim request. The bridge rejects missing, empty, invalid UTF-8, oversized, directory, and FIFO inputs before it creates a session or launches a process. It does not strip or truncate valid request text.

The command prints a short session ID after the supervisor and first Codex process start. The default session root is `~/.codex/apex-coding-sessions`. Supply `--state-dir /absolute/path/to/session-root` on each command to use another root.

```sh
python3 Engineering/coding_bridge.py status SESSION_ID
python3 Engineering/coding_bridge.py instruct SESSION_ID --text 'Please address the remaining acceptance criterion.'
python3 Engineering/coding_bridge.py events SESSION_ID
python3 Engineering/coding_bridge.py stop SESSION_ID
```

`status` returns structured state, including phase, Codex thread ID, model and reasoning effort, latest agent message, turn count, queue depth, event-log path, and the original request snapshot path and SHA-256. The snapshot is stored in the private session directory with mode `0600`. `events` returns each parsed JSONL event with its line number; malformed lines are included with their raw text and parse error. `instruct` accepts a trusted corrective follow-up of up to 64 KiB. Up to eight follow-ups may wait behind the running turn; a full queue rejects new instructions. A queued follow-up runs after the current turn completes. `stop` is the interruption control: it closes intake, discards queued turns, terminates the active Codex process group, and waits for the supervisor to persist `stopped`.

Engineering reads `status` for routine progress and uses `events` when the exact command, file change, or failure matters. A worker message is a report, not proof: inspect the changed files and run the focused acceptance check before completing the ledger task. The existing Obsidian task board is an exported view of the ledger; it is not a live transcript of Coding sessions.

The same session root and ID are required to control a session. Session directories are retained after stop or failure so Engineering can inspect state and logs.

## Control flow

1. `start` reads and validates the bounded original-request file before creating a session or launching any process. It validates the selected project directory and reads the task ledger record without writing to the database. It rejects missing, inactive, or non-Coding tasks.
2. The bridge creates a short UUID session directory with mode `0700`; state, original-request snapshot, event, and stderr files use mode `0600`. It records the snapshot's SHA-256 and path in session status. It starts a detached Python supervisor and sends the initial prompt over a pipe, never through a shell or process argument. The prompt includes the request verbatim and the ledger contract. It says the original requirements constrain interpretation, the contract bounds Coding's scope, and an unresolved conflict must be reported to Engineering rather than silently replaced with a different design.
3. The supervisor launches `codex exec --json --skip-git-repo-check -m gpt-6-luna` with `model_reasoning_effort="xhigh"`, `sandbox_mode="danger-full-access"`, and `approval_policy="never"`. The initial command also uses `-C PROJECT`; both initial and resumed processes use the project as their working directory. Prompts are sent on stdin. The session is not ephemeral.
4. Codex stdout is appended to the private JSONL event log and parsed to persist the thread ID, turn count, and latest agent message. A turn succeeds only after exactly one `turn.completed` event and a zero process exit; missing or repeated completion events fail the session and discard queued follow-ups. The supervisor serializes accepted follow-ups, resuming the exact thread ID first reported by `thread.started`.
5. Engineering inspects the outcome and verifies the acceptance criteria. The bridge never marks a ledger task completed.

Startup errors, malformed JSONL, nonzero Codex exits, unavailable control sockets, and supervisor failures are reported in command errors or persisted session state. A failed turn is not retried automatically. If the supervisor is no longer reachable while state says it was active, `status` marks that record `disconnected`; queued follow-ups are reported as potentially undelivered.

## Limitations

- This runs a background Codex CLI process; it does not open or claim a terminal GUI tab.
- `danger-full-access` is the requested Codex setting. A full-access worker can access files in the selected project and the session files. Session permissions reduce casual access by other local users but do not create a security boundary against the worker, another process running as the same user, or project code. Prompt scope is guidance, not enforcement.
- The request file is caller-supplied, not authenticated or sandboxed. Its SHA-256 identifies the stored snapshot; it does not prove who supplied the text or that the text is authoritative. The request does not change Codex permissions.
- The bridge does not copy Codex configuration or secrets into its session directory. The Codex process uses the current user's installed CLI and authentication environment.
- Accepted follow-ups live in supervisor memory until run. If the supervisor exits unexpectedly, its last persisted state remains available, but queued text is not recovered or automatically retried.
- Unix domain socket path-length limits apply. Use a short `--state-dir` path if socket startup fails with a path-length error.
- Stopping sends termination signals to the active Codex process group and escalates if needed. It cannot guarantee cancellation of descendants that detach into another process group, and it does not roll back file changes the worker already made.
- Carry visual requirements and reference-specific fidelity constraints into acceptance criteria. The bridge does not validate visual fidelity. Compare the reference asset with the rendered result at the relevant viewport and state before claiming a visual match.

## Focused verification

Run the fake-executable tests; they do not invoke a real model:

```sh
python3 -m unittest Test.test_coding_bridge -v
```

Observed on October 15, 2026: [7 focused bridge tests passed](../Test/evidence/coding-bridge-unit-2026-10-15.log). A [live isolated project run](../Test/evidence/coding-bridge-live-postfix-2026-10-15.json) used `gpt-6-luna` with `xhigh`, changed one fixture file, completed two turns with the same Codex thread ID, passed the independently run focused test, and ended in `stopped`. These results cover the tested macOS CLI path and fixture; they do not prove correctness for every project or tool route.
