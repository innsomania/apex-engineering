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
