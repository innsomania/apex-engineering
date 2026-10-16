# Spec planning playbook

Apex plans in prose: the workflow says understand, inspect, decide, implement, verify, stop, but it
never names the individual steps of a particular job. A turn therefore has no natural stopping
point, and an approved plan reads as permission to do all of it. This playbook covers the external
component selected to produce that missing step list.

| Field | Value |
| --- | --- |
| Component | [cc-sdd](https://github.com/gotalab/cc-sdd) (`cc-sdd` on npm) |
| Version observed | 3.1.0 |
| License | MIT |
| Adopted as | its 17 skills, vendored under `Claude/skills/` |
| Status on this host | **installed globally through `install.py`** |

## What it produces

A phase sequence — discovery, requirements, design, tasks, implementation — where each phase writes
a file under `.kiro/specs/`. Two of those files are what Apex is missing:

- `tasks.md`: numbered, independently implementable tasks, each annotated with `_Boundary:_` (the
  component it may touch) and `_Depends:_` (what must land first).
- `design.md`: a File Structure Plan naming the directories and files the work will touch.

## Verified behavior

Installed into an empty git repository. Evidence:
[spec-planning-2026-10-16.log](../../Test/evidence/spec-planning-2026-10-16.log).

| Observation | Result |
| --- | --- |
| Files written | 50: 33 under `.claude/skills/`, 16 under `.kiro/settings/`, and `CLAUDE.md` |
| Skills installed | 17, listed in the evidence log |
| Claude Code hooks registered | **none** |
| User configuration touched | none |

## The limit that decides how it is used

It registers no hook. Every phase gate is a sentence asking the model to pause, and upstream
documents `-y` and `--auto` flags that remove the gates entirely. This is the same mechanism that
already failed: a model that reads "the plan is approved" as "do all of it" will read a phase gate
the same way. Upstream says as much, recommending that manual approvals be kept for production.

So cc-sdd is treated as a **planner, not a gate**. Its phase gates are not a control and must not
be described to the user as one. Apex's hooks remain the only enforcement.

| Layer | Owner | Mechanism |
| --- | --- | --- |
| What the steps are, and their file boundaries | cc-sdd | documents under `.kiro/specs/` |
| Which files may actually change | Apex `.apex/scope.json` | `PreToolUse` denial |
| Whether a turn may end | Apex `verify.json` and `review.json` | `Stop` denial |
| Whether a shell command may run | cc-safety-net | `PreToolUse` denial, see [Execution guard](EXECUTION_GUARD.md) |

The intended flow: cc-sdd's File Structure Plan becomes the `allow` list in `.apex/scope.json`, and
one entry in `tasks.md` is one Apex turn. That conversion is manual today; no converter is written.

## How it is installed here

Everything reaches the hosts through Apex, so cc-sdd is not run per project. Its 17 skills are
vendored under `Claude/skills/` with the upstream MIT licence beside them, and `install.py` links
each one into `~/.claude/skills/` next to the Apex skill. A global Apex install therefore carries
them, and `install.py uninstall` removes them again.

**Only the skills are taken.** The upstream installer also writes a project-root `CLAUDE.md`
declaring a `/kiro-*` workflow, and `.kiro/settings/` templates. Those are left out: the `CLAUDE.md`
would compete with the global instructions that route software work to Apex. The skills stay
available as commands without claiming ownership of any project.

The cost of vendoring is that upstream releases do not arrive on their own. Re-run
`npx cc-sdd@<version> --claude-code-skills --lang en` into an empty directory and copy the result
over `Claude/skills/`, then re-read this playbook's limits before trusting the new version.

## Conflicts that remain

1. **Two task records.** `Engineering/Tasks` and a spec's `.kiro/specs/` would both track the same
   work. One must be authoritative; the other goes stale and misleads.
2. **Two delegation models.** `kiro-impl` runs its own per-task implementer and reviewer; Apex has
   `apex-coding` and `apex-reviewer` behind the `Stop` hook. Running both nests one inside the
   other and reviews the same change twice.

Neither is resolved here. They surface only when a `/kiro-*` command is actually used.

## Rejected alternatives

| Candidate | Reason |
| --- | --- |
| [spec-kit](https://github.com/github/spec-kit) | A complete methodology that would replace Apex rather than feed it. |
| [superpowers](https://github.com/obra/superpowers) | Same: a full skills framework and methodology of its own. |
| [BMAD-METHOD](https://github.com/bmad-code-org/BMAD-METHOD) | Licensed `NOASSERTION`; role-based and aimed at teams. Resolve the license before any evaluation. |
| [claude-code-spec-workflow](https://github.com/Pimzino/claude-code-spec-workflow) | Last pushed 2025-09-07; over a year without a release while the host's hook and skill APIs moved. |
