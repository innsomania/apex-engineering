# Contributing

This is a personal project, but the checks below are what a change has to pass
before it lands — including a change you make to your own copy six months from
now.

## Checks

The same three run locally and in CI, in this order:

```sh
pip install -r requirements-dev.txt
ruff check .
mypy --ignore-missing-imports .
python3 -m unittest discover -s tests -p 'test_*.py'
```

A fourth check proves the controls actually fire, rather than that the hook's
branches work:

```sh
python3 tests/run_live_control_check.py --output artifacts/live-controls.json
```

It builds a disposable git project, turns the controls on through
`apex_project.py`, and then calls the hook exactly as Claude Code does, in
order: an out-of-scope edit is refused, a failing verify blocks the stop and
counts the attempt, a passing verify still demands the review, a `FAIL` verdict
blocks and quotes the finding, a `PASS` verdict releases the turn, a write made
through the shell is still caught, a question turn locks edits, and the gates
survive an agent that rewrites or deletes `.apex/` or renames a file out of the
scope from a shell. Every observation must pass. It runs no model and needs no
network.

A fifth proves that fourth check is not blind:

```sh
python3 tests/run_mutation_check.py --output artifacts/mutations.json
```

It disables one gate at a time in a throwaway copy of the hook and requires the
live check to report the matching failure. A surviving mutation means the live
check does not cover that gate, and is a defect in the check, not in the hook.
Keep its `MUTATIONS` list in step with the gates.

### Coverage

Coverage needs subprocess tracing, because every gate runs as a subprocess, and
an **absolute** `source`, because the tests run the tools from temporary
directories:

```sh
pip install coverage
printf 'import coverage; coverage.process_startup()\n' \
  > "$(python3 -c 'import site;print(site.getsitepackages()[0])')/zz-coverage.pth"
cat > .coveragerc <<EOF
[run]
branch = True
parallel = True
source = $PWD/controls
relative_files = False
EOF
export COVERAGE_PROCESS_START="$PWD/.coveragerc"
python3 -m coverage run -m unittest discover -s tests -p 'test_*.py'
python3 -m coverage run tests/run_live_control_check.py
python3 -m coverage combine && python3 -m coverage report --skip-empty --sort=cover
```

A relative `source` silently reports near-zero for anything run from another
directory. The measured figures are in
[docs/verification.md](docs/verification.md).

Run them from the repository root. Every test should pass. `ruff` and `mypy`
are pinned in `requirements-dev.txt` so a local run and CI agree on what counts
as a finding; bumping either is a deliberate change, because a new release
rejects different code.

Every source module passes `mypy --strict`. `tests/` is excluded, which
`pyproject.toml` explains. Tests that need a .NET or C++ toolchain skip when
those are unavailable, so a clean run inside a sandbox is normal — read the
skip reasons rather than assuming full coverage.

`pytest` runs the same suite, which is what `.apex/verify.json` uses. The suite
itself stays plain `unittest`.

## What belongs where

The directory a file lives in decides whether the agent loads it, so the
boundary matters more than it looks:

- `guides/` holds what the agent reads while working. Keep each file short and
  each statement actionable.
- `controls/` holds the code that enforces the gates: the project CLI and the
  Claude Code hooks and subagents.
- `catalog/` records which third-party skills are installed, from where, and why.
- `tests/` holds the suites, the live check, the mutation check, and the
  evaluation runners.
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

`controls/claude-code/hooks/apex_verify_hook.py` is what makes the verify, scope,
and review gates real. A change to it needs a test in `tests/test_verify_hook.py` that
fails without the change. Weakening a gate to make a turn finish is the one
thing this repository exists to prevent.
