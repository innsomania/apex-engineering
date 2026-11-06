# Apex Engineering

One engineering workflow for LLM coding agents, plus runtime controls that make
the agent follow it. Apex works with **Claude Code** and **Codex** (enforced),
**OpenCode** (guidance), and any other tool that can read Markdown (portable).

Apex is built like Lego: a small core that every task uses, and parts that load
only when a task needs them. A one-line fix costs almost nothing extra; a new
project gets the full process.

## What it does

| Part | What it gives you |
| --- | --- |
| **Stages** | Large work goes idea → plan → *your approval* → coding one task at a time → check → final review. Small work goes straight to coding. |
| **Clear requests** | A vague request gets at most five focused questions with options; a request that bundles several goals is split, and you pick where to start. |
| **Needs brief** | For a new project or feature: who it is for, must-haves, scenarios, edge cases, out of scope, risks, and how you will know it is done. |
| **Current technology** | New work uses the current stable release, checked at its official source with URL and date. Outdated dependencies in an existing project are named and offered as a separate upgrade, never changed unasked. |
| **Planner and worker** | A planner model plans and checks; a worker model writes the code. Small one-file changes stay with the planner to save tokens. |
| **Project map** | A short "where things are" section in `AGENTS.md`/`CLAUDE.md`, so the agent stops searching the whole project every session. |
| **PLAN.md** | The task list, the current stage, and one log line per day, so work continues across sessions. |
| **Controls** | The host, not the model, enforces scope, verification, review, and an up-to-date map. |

## Why enforcement, not instructions

An instruction file cannot make an agent honest about its own work. Apex's core
is therefore a set of opt-in project controls that the host runs through hooks:

- **Verify:** a turn that changed files cannot end until the project's real
  build or test command passes.
- **Scope:** edits outside the approved files are refused before they happen,
  and any out-of-scope change, including one made through the shell, blocks the
  end of the turn.
- **Review:** an independent reviewer agent compares the change with your
  verbatim instructions before the turn may end.
- **Map:** a turn cannot end while the project map names a file or function
  that no longer exists.
- **Questions and stops:** when you ask a question, the agent answers instead of
  editing; when you say stop, it stops. A bare "is it done?" does not halt work.

The controls watch themselves: a turn in which the agent rewrites, creates, or
deletes the control files cannot end. Everything else in this repository is
guidance: it helps, but it proves nothing on its own.

## How a large task flows

```text
You: "Build me an offline notes app with React Native."

1. Idea       needs brief + stack choice (versions checked at the source)
2. Plan       tasks of one concern each, with a check per task
3. Approval   the agent stops and waits for you
4. Coding     one task at a time; the next starts only after the last check passes
5. Check      the project's verify command (enforced)
6. Review     the whole change against your words (enforced)

Progress: Plan ✅ · Coding 2/4 · Check ⏳ · Review –
```

## Requirements

- Python 3.11 or newer.
- Git.
- Claude Code and/or the Codex CLI, signed in.

## Install

```sh
git clone https://github.com/innsomania/apex-engineering.git
cd apex-engineering
python3 install.py install --host all     # or --host claude / --host codex
python3 install.py status --host all
```

The installer links this checkout into `~/.claude` and `~/.codex`, adds the hooks
and agents, and adds a marked block to your global `CLAUDE.md`/`AGENTS.md`
without touching your own text. Codex runs new hooks only after you trust them:
open Codex and review them with `/hooks`. Start a new session afterwards. Full
detail: [docs/install.md](docs/install.md).

To remove it:

```sh
python3 install.py uninstall --host all
```

## Turn on the controls in a project

The controls are opt-in per project. In a git project without `.apex/`, the hook
offers setup once. You can also run:

```sh
python3 /path/to/apex/controls/apex_project.py suggest --root .
python3 /path/to/apex/controls/apex_project.py init --root . --allow src/ --allow tests/ --verify "npm test"
```

| File | Effect |
| --- | --- |
| `.apex/scope.json` | `{"allow": ["src/", "tests/*.py"]}`: the only files the agent may change. `PLAN.md` is always allowed. |
| `.apex/verify.json` | `{"command": "npm test", "timeout": 600}`: must pass before a turn may end; after 3 failures the agent stops and says the work is not done. |
| `.apex/review.json` | `{}`: turns on the independent review. |

Only you change these files. The agent is blocked from editing them.

## Planner and worker setup

Apex ships the worker agents; you choose the planner model.

| Host | Planner (your setting) | Worker (shipped) |
| --- | --- | --- |
| Claude Code | e.g. Opus with low effort | `apex-coding` on Sonnet, medium effort |
| Codex | e.g. `model = "gpt-6-astra"`, `model_reasoning_effort = "low"` in `config.toml` | `apex-coding` on `gpt-6-luna`, high effort |

A Claude planner can also use Codex as its worker through
`controls/apex_worker.py`, which runs one approved task in the Codex sandbox and
writes the report, changed files and token usage to a JSON file:

| Role | Model | For |
| --- | --- | --- |
| `heavy` | `gpt-6.1-sol`, medium | complex or multi-file work |
| `focused` | `gpt-6-luna`, high | one clear feature, fix, or test |
| `ui` | `gpt-6.1-terra`, medium | opening the app and checking screens and layouts |

Tell the planner when to delegate in your own part of `CLAUDE.md` or
`~/.codex/AGENTS.md`, outside the Apex block. Keep one model selected in the app
(the planner) and write everything to it; it calls the worker itself.

## Run a task from the command line

From your target project, use the absolute path to this checkout:

```sh
python3 /path/to/apex/run_apex.py --host claude --task "Fix the reported bug"
python3 /path/to/apex/run_apex.py --host codex --task "Fix the reported bug"
python3 /path/to/apex/run_apex.py --host portable --task "..."   # prints a prompt for any other tool
```

## Evidence

Every claim below comes from live runs whose fixtures, oracles, and diffs are in
`docs/evidence/` and `docs/evaluations/` (start with [multi-task](docs/evaluations/multi-task-2026-10-26.md)). Each
is a small number of runs, not a benchmark.

- Codex, Claude Code, and OpenCode each fixed a C++ tenant-access bug and passed
  an independent 32-case oracle.
- On four Python tasks, the Claude planner and worker passed 38/38 oracle cases
  (three tasks) and the Codex planner and worker 46/46 (four tasks), every run
  inside scope.
- On a real bug in the open-source `humanize` library, both setups passed the
  maintainers' hidden regression test and the full suite.
- A 183-word project map cut a question's input tokens by 60–70% and removed a
  wrong answer.
- Small one-file tasks run by the planner alone used about 71k input tokens,
  against 306k–339k when every task was delegated.

See [what has actually been verified](docs/verification.md) and its limits.

## Limits

- Hooks run only in Claude Code and Codex. Elsewhere, Apex is guidance.
- A shell command can write outside scope; it is caught at the end of the turn,
  not before it runs.
- Rules such as "delegate only multi-file work" steer the model; they are not
  exact.
- The evidence comes from small and medium tasks.

## Repository layout

| Path | Holds |
| --- | --- |
| `SKILL.md` | The entry point: task contract, stages, how to talk to the user, work loop |
| `guides/` | Engineering, per-stack coding, test, and security guides, loaded on demand |
| `controls/` | The hook, the project CLI, and the Claude Code and Codex agents |
| `install.py`, `run_apex.py` | Installer and task launcher |
| `catalog/` | Third-party skills Apex relies on, and the rules for adding one |
| `tests/` | Unit tests, the live control check, and the mutation check |
| `docs/` | Install guide, host support, verification, evaluations and evidence |
| `AGENTS.md` | This repository's own project map (`CLAUDE.md` imports it) |

## Develop

```sh
pip install -r requirements-dev.txt
ruff check .
mypy .
python3 -m unittest discover -s tests
python3 tests/run_mutation_check.py
```

GitHub Actions runs the tests on Python 3.11 to 3.14 on Linux and on 3.14 on
macOS. `main` is protected: changes land only through pull requests. See
[CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE).
