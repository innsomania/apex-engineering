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

- The directories the agent loads hold only guidance. Records that described a
  component rather than changing a decision moved to `docs/`: the brain design
  proposal, the control-candidate comparison, the adapted public instruction
  patterns, the experimental controller's route-coverage matrix, and the dated
  MCP host observations.
- `Engineering/MCP_CONTROL.md` merged into `Integrations/MCP_CATALOG.md`, and
  `TOOLS.md` no longer repeats the probe commands, so MCP has one guidance file.
- `ARCHITECTURE_AND_DATA.md` dropped the textbook passages and kept the
  constraints, and `CONTROL_RUNTIME.md` lost two paragraphs it stated twice.
- Every loaded reference opens by saying which decision it changes, so the agent
  can stop reading a file that is not about its decision.
- The loaded tree is 31 files and 14,340 words, down from 35 and 17,734.

### Added
- `Test/run_mutation_check.py` disables each gate in a throwaway copy of the
  hook and requires the live check to notice, so the live check's own result
  means something. CI runs it on every push.

- `Engineering/PROJECT_MEMORY.md` gives the skill a way to not re-derive a
  project every session: a hot tier in the project's own instruction file,
  capped at about 300 words because the host loads it every turn, and a cold
  tier in one note per project in the user's vault, read only when opened. Both
  carry skeletons. `SKILL.md` names it before the investigation step, since a
  memory rule found afterwards is useless.
- `Engineering/Integrations/DOCKER.md` carries the Docker guidance that was
  sharing a file with the vault procedure.

- `Test/run_live_control_check.py` drives the hook through a real turn on a
  disposable project and asserts that the verify, scope, and review gates
  actually fire, which the branch-level suites do not establish. CI runs it on
  every push; it needs no model and no network.


- `LICENSE` (MIT), `CHANGELOG.md`, `CONTRIBUTING.md`, and `SECURITY.md`.
- `docs/VERIFICATION.md`, separating what a check proved from what it did not.
- A `ruff` lint gate and `mypy --strict` type checking, configured in
  `pyproject.toml` and pinned in `requirements-dev.txt`. Every source module
  passes both; `Test/` and the vendored skills are excluded for stated reasons.
- GitHub Actions runs lint, types, and the suite on Python 3.11 to 3.14 across
  Linux and macOS.

### Removed

- A diagnostic session transcript that carried a client project name and
  absolute home paths, and the .NET fixture's build output. Both are gone from
  the working tree and from git history. The event and stderr logs that
  evaluation reports cite are kept with the home path replaced.
- `Engineering/Tasks/apex.board.json` is untracked: it is per-machine
  configuration naming a personal vault note.

### Fixed
- The live check's assertions matched a single fragment of a block message, so
  one gate's block could satisfy another gate's claim. Disabling the scope
  sweep left the check passing because the review gate blocked instead and
  named the same file. Every expected fragment is now required.

- The task board configuration pointed at `/Users/<user>/Opsidian/...`, a
  literal path that cannot exist: the history rewrite in this release replaced
  the home directory in the working tree as well as in history, and untracking
  the file did not restore it. The board had silently failed to refresh since
  then, which the ledger is designed to survive — it warns on stderr and stays
  authoritative — so no task data was lost, only the exported note went stale.


- Markdown links left dangling by the moves, plus five that were already broken
  before them.
- Two closures bound a loop variable late, in the control evaluation and the
  host test, so either would have read a later iteration's value had the call
  been deferred.
- The Codex adapter and the coding bridge read `Popen` standard streams, and
  joined reader and writer threads, without checking the optionals their own
  types allow; `dispatch_tool_call` reached `.get` on a value it had not
  established was a mapping. Each was safe only by the order its conditions
  happened to evaluate in.
- `ask_for_prompt` could call a prompt provider that the fixture path leaves
  unset.
- The broker could duplicate a closed directory descriptor; it now reports a
  closed session like any other call after `close()`.

## [0.1.0] — 2026-10-15

First working version: the four working areas, per-technology coding guidance,
the installer for Codex and Claude Code, the verification, scope, and review
hooks, the persistent task ledger, the Codex coding bridge, and the integration
playbooks. Recorded evaluations for this version are in
[docs/VERIFICATION.md](docs/VERIFICATION.md).
