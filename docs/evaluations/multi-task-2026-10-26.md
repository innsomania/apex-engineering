# Apex multi-task validation — 2026-10-26

The 2026-10-24 run used one C++ defect. This run used three new Python tasks of
different kinds. Each task was run once through `run_apex.py` with Claude Code
2.1.310 and Codex 0.164.0. An oracle that the agent never saw checked each
result. Every starting fixture failed the oracle, and a reference solution
passed every case.

| Task | Kind | Claude Code | Codex |
| --- | --- | ---: | ---: |
| `durations` | bug report: "1h30m returns the wrong value" | 22/22 | 15/22 |
| `inventory` | feature: add `--json`, keep the plain output | 6/6 | 6/6 |
| `report` | vague request: "the report is slow, speed it up" | 8/8 | 8/8 |

Scope held in all six sessions:
- each session changed only the task's source file and its test file;
- `AGENTS.md` was preserved;
- the frozen `legacy.py` in `report` was untouched;
- every project's own tests passed afterwards, and each agent added a regression test.

## Findings

- Codex fixed the reported case (`1h30m` → 5400) by summing every match. It did
  not enforce the rejection rules in the function's docstring. Seven malformed
  inputs, such as `30m1h`, `1h1h`, `1.5h`, `-5s` and `1h30mx`, still return a
  value instead of raising `ValueError`. The prompt named only the reported case,
  so the oracle is stricter than the request. Claude Code enforced the documented
  contract and passed every case.
- OpenCode was not run. Headless `opencode run` auto-rejects every permission
  prompt, so it could not read the Apex entry point or run a command. A
  per-fixture permission grant was refused by this session's safety classifier,
  and the user chose to leave OpenCode out.

## Codex planner and worker, 2026-10-27

The same fixtures were run again with Codex as planner and worker: `gpt-6-astra`
(low) plans and hands code to the `apex-coding` agent on `gpt-6-luna` (high).
The planner's own `AGENTS.md` section tells it to delegate code and to write the
documented behavior of the code being changed into the worker's acceptance check.

| Task | Codex alone (10-26) | Planner and worker, no contract rule | Planner and worker with the rule |
| --- | ---: | ---: | ---: |
| `durations` | 15/22 | 15/22 | 22/22 |
| `inventory` | 6/6 | not run | 6/6 |
| `report` | 8/8 | not run | 8/8 |

All three runs with the rule spawned `apex-coding`, and each changed only its
source file and test file. The planner turn alone reported 183k–240k input
tokens (163k–220k cached), against 70k–106k for a single Codex session. That
figure does not include the worker's tokens. The split is not a cost saving on
tasks this small. This is one run per task.

### With token-saving routing

The planner rules then changed in two ways:
- **Routing:** a small change to one source file is made by the planner itself; only multi-file or heavy work goes to the worker.
- **Waiting:** the planner waits for the worker with one long `wait_agent` call instead of 10-second polls, because every poll re-sends the whole conversation.

A two-file task, `billing`, was added to check that delegation still happens. Tokens below are input tokens for the planner plus the worker, with cached tokens included.

| Task | Codex alone (10-26) | Planner and worker, contract rule | With routing | Done by | Score |
| --- | ---: | ---: | ---: | --- | ---: |
| `inventory` | 70k | 306k | 71k | planner | 6/6 |
| `report` | 106k | 339k | 144k | planner | 8/8 |
| `durations` | 70k | 256k | 224k | worker | 22/22 |
| `billing` (two files) | not run | not run | 260k | worker | 10/10 |

The planner still delegated `durations`, a one-file change, so the routing rule
is advisory, not exact. When the planner did the work itself on `inventory` and
`report`, it added no regression test; the delegated runs did add one. The
diffs are in [codex-planner](../evidence/multi-task-2026-10-26/codex-planner/billing.diff).

### Self-written tests and the Codex reviewer, 2026-10-27

The planner rule now also asks for a regression test when the planner makes a
one-file change itself. `inventory` and `report` were run again: 6/6 and 8/8,
each with its test file extended, at about 71k input tokens each.

The Codex review gate was run live on `inventory` in a project with
`.apex/scope.json`, `.apex/verify.json` and review on. The hook asked for a
review, a separate `apex-reviewer` session ran and answered `APEX-REVIEW: PASS`,
and the turn then finished with the oracle at 6/6. Before the agents were
installed as copies, that reviewer could not be spawned under Codex at all.

## Usage

Single observations; cached context is included and nothing is pinned. These
numbers are not a benchmark.

| Task | Claude Code cost | Claude output tokens | Codex input / cached | Codex output |
| --- | ---: | ---: | ---: | ---: |
| `durations` | $0.28 | 2598 | 69632 / 50944 | 703 |
| `inventory` | $0.27 | 2495 | 70480 / 51328 | 962 |
| `report` | $0.27 | 2034 | 106023 / 86912 | 1078 |

## Scope of evidence

This is one run per host and task, on small single-file Python projects. It does
not show behaviour on large codebases, other languages, or interrupted sessions.
The fixtures, the oracle, the runner, each agent's diff and the per-host
summaries are in [the evidence folder](../evidence/multi-task-2026-10-26/oracle.py) (`oracle.py`, `run_host.py`, `fixtures/`, `claude/`, `codex/`).
Reproduce a host with `python3 run_host.py claude` from a copy of that folder
after adjusting its paths.
