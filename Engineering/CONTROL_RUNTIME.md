# Experimental execution controller

Read this only when asked to run a Codex turn with exact file permissions. It
decides one thing: what you may claim about containment, and the answer is
very little.

**Status: experimental, opt-in CLI. Not enabled as a global control boundary.**
Live fixture evidence references Codex CLI 0.162.0 and certifies no other
version. The Codex desktop app does not route its tools through this adapter
and receives no containment from it.

## What it does

A trusted caller supplies a project root and exact, independent read and write
permission lists. [control.py](control.py) brokers UTF-8 file reads and writes
against those lists, rejecting traversal, links, special files, oversized
files, exhausted budgets, and unknown operations; writes replace whole files
atomically. [codex_control.py](codex_control.py) starts an isolated stdio App
Server on the existing Codex login, requests read-only and no-network
sandboxing, disables configured MCP servers and selected native tools,
verifies the effective restrictions, and exposes only `apex_file`.

Two entrypoints use the same policy arguments. Paths must be canonical
relative file paths, unique within each list. The lists are independent: a file
is readable only when given to `--allow-read` and writable only when given to
`--allow-write`. Neither entrypoint grants whole-project access.

One turn:

```sh
python3 Engineering/controlled_cli.py \
  --project-root /absolute/path/to/project \
  --allow-read README.md --allow-write README.md \
  --prompt 'Update the introduction in README.md.'
```

Interactive, successive turns on one controlled thread:

```sh
python3 Engineering/apex_host.py \
  --project-root /absolute/path/to/project \
  --allow-read README.md --allow-write README.md \
  --prompt 'Update the introduction in README.md.'
```

Type `:quit` or `:stop` between turns to close the session. Ctrl+C during a
turn closes broker admission and requests `turn/interrupt`; at the prompt it
closes the session. A malformed or unexpected App Server message stops the
session and closes admission.

## Stop semantics

The supervisor marks the broker stopped and requests `turn/interrupt`. File
dispatch and broker stop are serialized: no operation is admitted after the
stop event, though an already admitted one may finish. Completed writes are
never rolled back. A stopped broker cannot resume; a trusted caller must start
a new session. The stop event is polled at up to 50 ms intervals, which is not
an instantaneous OS kill.

## What you may not claim

- The broker does not contain another process running as the same OS user,
  direct Python access to its private fields, or a concurrent malicious
  directory rename by an external process.
- The App Server sandbox is read-only, which restricts writes. It does not
  establish read confidentiality, and native reads are not contained.
- A tool or command outside the broker is not made safe by policy text. Routes
  the tests do not exercise are uncovered.
- A model refusal, or an unchanged canary without an observed command failure,
  is inconclusive — not evidence of denial.

Use this feature only where those limits are acceptable, and keep protected
production operations disabled in it. Which routes the tests cover, what the
modules contain, and how to re-run the evaluation are recorded in
[the coverage record](../docs/CONTROL_RUNTIME_COVERAGE.md).
