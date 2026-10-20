# Apex Engineering

A software engineering skill for Claude Code and Codex. It routes a task through
design, implementation, security review, and focused verification, and — where
the host allows it — it enforces that routing instead of asking the model to
remember it.

Supported technologies: C#/.NET, React, React Native, Dart, Swift/SwiftUI, and
C++. Other stacks fall back to the common workflow.

## Why enforcement, not instructions

Instruction files cannot make an agent honest about its own work. Apex's
useful part is therefore the three opt-in project controls, which the host runs
rather than the model:

- **Verify** — a turn that changed files cannot end until the project's real
  build or test command passes.
- **Scope** — edits outside the approved file list are refused, including ones
  made through the shell.
- **Review** — an independent subagent compares the working tree against your
  verbatim instructions before the turn may end.

The controls watch themselves: a turn in which the agent rewrites, creates, or
deletes the control files cannot end.

Everything else in this repository is guidance. It helps, but it proves
nothing. See [what has actually been verified](docs/verification.md), including
the one known limit.

## Layout

| Directory | Holds |
| --- | --- |
| `guides/` | What the agent reads while working: engineering, per-technology coding, test, security |
| `controls/` | The enforcing code: the project CLI, the Claude Code hooks, and the two subagents |
| `catalog/` | The record of third-party skills Apex relies on, and the rules for adding one |
| `tests/` | The suite, the live control check, the mutation check, and the evaluation runners |
| `docs/` | Install, verification, and past evaluations with their evidence |

`SKILL.md` is the entry point and loads only the guides a task needs.

## Install

```sh
python3 install.py install --host all
python3 install.py status --host all
```

Then start a new session. Full detail, including the project controls and host
sandbox behavior, is in [docs/install.md](docs/install.md).

## Develop

```sh
pip install -r requirements-dev.txt
ruff check .
mypy --ignore-missing-imports .
python3 -m unittest discover -s tests -p 'test_*.py'
```

Every source module passes `mypy --strict`, and GitHub Actions runs the same
checks on Python 3.11 to 3.14 across Linux and macOS. See
[CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE).
