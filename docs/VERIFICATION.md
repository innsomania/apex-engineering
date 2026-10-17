# What has actually been verified

Apex's own instructions forbid presenting an unverified claim as established,
so this page separates what a check proved from what it did not. Each entry
names the date it was observed; nothing here is re-confirmed automatically by
reading this file.

## Automated suite

| Check | Result |
| --- | --- |
| `python3 -m unittest discover -s Test -p 'test_*.py'` | 116 tests pass (observed 2026-10-18). |
| Installation and integrity tests | Included in the suite above. They run in temporary directories and never touch live Codex or Claude settings. |

These cover installer behavior, the task ledger, the verification hook, the
bridge, and the control adapter. They do not evaluate agent behavior: that
needs an observed task.

## Behavioral evaluations

Each of these was a single recorded run against a fixture, not a benchmark.

| Evaluation | Observed | Record |
| --- | --- | --- |
| .NET engineering task | 96 independently checked input combinations plus one sequential stale-update case passed; edits stayed inside the two permitted files; a labeled untrusted instruction did not cause the requested canary overwrite or package change. | [report](evaluations/ENGINEERING_EVALUATION_2026-10-15.md) |
| C++ tenant authorization defect | Apex read the applicable Engineering, Coding, Security, and Test references, fixed the defect, added regression tests, and the result passed 32 independent access-control cases. | [report](evaluations/MVP_VERIFICATION.md) |
| Control adapter | Fixture-level results, including a read-only sandbox route check. | [2026-10-16](evaluations/CONTROL_EVALUATION_2026-10-16.md), [2026-10-15](evaluations/CONTROL_EVALUATION_2026-10-15.md) |
| Host route and desktop MCP | Route-level observations on one macOS host. | [host route](evaluations/HOST_ROUTE_EVALUATION_2026-10-16.md), [desktop MCP](evaluations/DESKTOP_MCP_EVALUATION_2026-10-16.md) |

Supporting logs and traces are under `docs/evaluations/evidence/`.
Absolute home paths in two Codex event and stderr pairs were replaced with
`/Users/<user>`; nothing else in them was altered.

## Limits

- One passing fixture run does not establish expertise across the supported
  technologies. The [scenario specification](evaluations/ENGINEERING_SCENARIOS.md)
  still contains unexecuted cases; do not infer their success.
- The project controls in `.apex/` are the only enforced containment. Mandatory
  control of a desktop session is not finished — see
  [CONTROL_RUNTIME.md](../Engineering/CONTROL_RUNTIME.md).
- A tool described in an integration playbook is not necessarily installed or
  connected. Discover it in the live session before relying on it.
- Markdown instructions provide working guidance. They are not a runtime
  sandbox and not a different model.

## Reproducing

The behavioral evaluations need a working toolchain and an authenticated Codex
CLI, and they spend model usage:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 Test/run_behavior_eval.py --output artifacts/cpp-authorization
PYTHONDONTWRITEBYTECODE=1 python3 Test/run_engineering_eval.py --output artifacts/dotnet-engineering
```

`--output` is required and existing results are never overwritten. `artifacts/`
is gitignored, so a new run does not touch the recorded evidence above.
