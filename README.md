# Apex Engineering

A software engineering skill for Codex and Claude Code. It routes a task
through design, implementation, security review, and focused verification, and
— where the host allows it — it enforces that routing instead of asking the
model to remember it.

Version 0.1.0. Supported technologies: C#/.NET, React, React Native, Dart,
Swift/SwiftUI, and C++. Other stacks fall back to the common workflow.

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

Everything else in this repository is guidance. It helps, but it proves
nothing. See [what has actually been verified](docs/VERIFICATION.md).

## Layout

| Directory | Responsibility |
| --- | --- |
| `Engineering/` | Requirements, analysis, architecture, planning, review, and the task ledger |
| `Coding/` | Per-technology implementation guidance |
| `Test/` | Acceptance criteria, focused verification, and the runnable suite |
| `Security/` | Trust boundaries, authorization, data protection, abuse cases |
| `Claude/` | Claude Code hooks, the `apex-coding` subagent, and the project CLI |
| `docs/` | Install, verification, design record, and past evaluations |

`SKILL.md` is the entry point and loads only the references a task needs.

## Install

```sh
python3 install.py install --host all
python3 install.py status --host all
```

Then start a new session. Full detail, including the project controls and host
sandbox behavior, is in [docs/INSTALL.md](docs/INSTALL.md).

## Develop

```sh
pip install -r requirements-dev.txt
ruff check .
mypy --ignore-missing-imports .
python3 -m unittest discover -s Test -p 'test_*.py'
```

Every source module passes `mypy --strict`, and GitHub Actions runs the same
three checks on Python 3.11 to 3.14 across Linux and macOS. See
[CONTRIBUTING.md](CONTRIBUTING.md).

## Documentation

- [Installation and project controls](docs/INSTALL.md)
- [What has actually been verified](docs/VERIFICATION.md)
- [Task system](Engineering/TASK_SYSTEM.md) and [Codex coding bridge](Engineering/CODING_BRIDGE.md)
- [Integration playbooks](Engineering/Integrations/INDEX.md) and [MCP catalog](Engineering/Integrations/MCP_CATALOG.md)
- [Original MVP design](docs/DESIGN.md) and the [proposed Engineering brain design](docs/BRAIN_DESIGN.md)

## License

[MIT](LICENSE).
