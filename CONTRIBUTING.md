# Contributing

This is a personal project, but the checks below are what a change has to pass
before it lands — including a change you make to your own copy six months from
now.

## Checks

```sh
python3 -m unittest discover -s Test -p 'test_*.py'
```

Run it from the repository root. 116 tests should pass. Tests that need an
authenticated Codex CLI, a Unix socket, or a .NET or C++ toolchain skip when
those are unavailable, so a clean run inside a sandbox is normal — read the
skip reasons rather than assuming full coverage.

`pytest` runs the same suite, because a project that uses the test-first guard
on itself needs the guard to see test results. The suite itself stays plain
`unittest`.

## What belongs where

The directory a file lives in decides whether the agent loads it, so the
boundary matters more than it looks:

- `Engineering/`, `Coding/`, `Test/`, `Security/` hold guidance the agent reads
  while working, and the Python tools that each area owns. Keep them short and
  keep each statement actionable.
- `docs/` holds records: installation, what was verified, the design history,
  and past evaluations. Nothing here is loaded to do a task.
- `artifacts/` is gitignored output from an evaluation run. Never commit a run.

A new reference file has to change a decision the agent would otherwise get
wrong. Breadth of coverage is not a reason to add one; it costs context on
every task that loads it.

## Writing rules for instruction files

- State what to do, not what the system is. Prose that only describes the
  architecture belongs in `docs/`.
- Never state a capability as active because a file describes it. Write the
  check that proves it instead.
- When recording a result, give the date and what it did not establish. The
  claim and its limit belong in the same place.
- Use relative links. Absolute paths tie a file to one machine.

## Changing the controls

`Claude/hooks/apex_verify_hook.py` is what makes the verify, scope, and review
gates real. A change to it needs a test in `Test/test_verify_hook.py` that
fails without the change. Weakening a gate to make a turn finish is the one
thing this repository exists to prevent.
