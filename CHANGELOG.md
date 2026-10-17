# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project
follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Evaluation reports, their evidence, and the repository research snapshot moved
  from `Test/` and `Engineering/` to `docs/`, so the directories the agent loads
  hold only guidance and runnable code.
- The task system and Obsidian playbook describe locations relative to the skill
  directory instead of stating one machine's absolute paths as fact.
- `README.md` covers what Apex is, how to install it, and where to read more.
  Installation detail moved to `docs/INSTALL.md` and verification claims to
  `docs/VERIFICATION.md`, each observation dated and attributed.
- Generated evaluation runs default to a gitignored `artifacts/` directory.

### Added

- `LICENSE` (MIT), `CHANGELOG.md`, `CONTRIBUTING.md`, and `SECURITY.md`.
- `docs/VERIFICATION.md`, separating what a check proved from what it did not.

### Removed

- A diagnostic session transcript that carried a client project name and
  absolute home paths, and the .NET fixture's build output. Both are gone from
  the working tree and from git history. The event and stderr logs that
  evaluation reports cite are kept with the home path replaced.
- `Engineering/Tasks/apex.board.json` is untracked: it is per-machine
  configuration naming a personal vault note.

### Fixed

- Markdown links left dangling by the moves, plus five that were already broken
  before them.

## [0.1.0] — 2026-10-15

First working version: the four working areas, per-technology coding guidance,
the installer for Codex and Claude Code, the verification, scope, and review
hooks, the persistent task ledger, the Codex coding bridge, and the integration
playbooks. Recorded evaluations for this version are in
[docs/VERIFICATION.md](docs/VERIFICATION.md).
