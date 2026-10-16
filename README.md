# Apex Engineering

A global software engineering skill for Codex and Codex CLI. MVP version: 0.1.0.

## Working areas

| Directory | Responsibility |
| --- | --- |
| Engineering | Requirements, system analysis, architectural decisions, planning, and review |
| Coding | Implementation guidance for C#/.NET, React, React Native, Dart, Swift/SwiftUI, and C++ |
| Test | Acceptance criteria, focused verification, results, and blockers |
| Security | Relevant trust boundaries, authorization, data protection, and abuse cases |

`SKILL.md` selects the references needed for each task. References are loaded on demand. See the [MVP design](APEX_ENGINEERING_DESIGN.md) and the [proposed Engineering brain design](Engineering/BRAIN_DESIGN.md).

## Engineering Markdown expansion

The [knowledge map](Engineering/KNOWLEDGE_MAP.md) routes requirements, system analysis, architecture/data, application engineering, delivery/operations, evidence gathering, and execution guidance. The [integration playbooks](Engineering/Integrations/INDEX.md) cover all 29 researched repositories with explicit primary, alternative, and excluded roles, plus public Codex/Claude instruction practices, Docker, and file-based Obsidian navigation.

These are English instructions and operating procedures. Selected [MCP servers](Engineering/Integrations/MCP_CATALOG.md) are now globally configured and were exercised in Codex CLI; the other researched tools remain candidates. The setup does not connect model APIs or implement a mandatory runtime dispatcher. The Obsidian vault designated by the user is `/Users/<user>/Opsidian`; its entry note links to the maintained Apex source. See [Docker and Obsidian](Engineering/Integrations/DOCKER_AND_OBSIDIAN.md) for boundaries.

The operating principle is: slow is smooth; smooth is fast. Resolve material uncertainty, take coherent steps, verify the relevant result, and stop. Broad reference coverage does not require loading everything or expanding every task.

## Installation

For persistent task creation, role assignment, dependency checks, lifecycle history, acceptance evidence, and Obsidian board export, use the [task system](Engineering/TASK_SYSTEM.md). This executable local ledger is separate from the Markdown tool-integration playbooks and does not launch agents or implement a host sandbox.

For Coding tasks, the separate [Codex CLI bridge](Engineering/CODING_BRIDGE.md) requires the original user request in a caller-supplied UTF-8 file, reads an active Coding task, and runs a background `gpt-6-luna` session with `xhigh` reasoning in the selected project. Engineering can read structured progress, queue a corrective follow-up in the same session, or interrupt the worker. Engineering remains responsible for verifying the result and completing the ledger task.

Requires Python 3. Run from this directory:

```sh
python3 install.py install
python3 install.py status
```

The installer uses `CODEX_HOME` when set, otherwise `~/.codex`. It creates `skills/apex-engineering` as a symbolic link to this source directory; keep the source directory at its installed location. It adds a marked routing block to the global `AGENTS.md` while preserving existing text. Use `--codex-home /path/to/codex-home` to select another user directory. Codex and Codex CLI share the package when they use the same user directory.

### Claude Code (desktop and CLI)

```sh
python3 install.py install --host claude
python3 install.py status --host all
```

This links `skills/apex-engineering` and the `apex-coding` subagent (`agents/apex-coding.md`, sourced from `Claude/agents/`) into `CLAUDE_CONFIG_DIR` or `~/.claude`, and adds a marked routing block to the global `CLAUDE.md`. The desktop Code tab and the `claude` CLI share this directory. In Claude Code, Engineering delegates Coding to the `apex-coding` subagent by default; the Codex CLI bridge is used only when the user asks for Codex. Use `--host all` to configure both hosts and `--claude-home` to select another directory. Start a new Claude Code session after installation.

Start a new Codex chat or CLI session after installation. Example:

```text
$apex-engineering Fix the authorization bug in this .NET endpoint
and run only the relevant regression tests.
```

The global routing block requests Apex for software tasks. It does not guarantee instruction adherence or expertise. The MVP provides workflows and technology references; execution tools and permissions come from the host Codex environment. An experimental control adapter exists for isolated fixtures; mandatory control of desktop sessions remains unfinished.

## Access and visible activation

The installed skill uses the host session's permissions. On this machine, the global Codex configuration currently selects `sandbox_mode = "danger-full-access"` and `approval_policy = "never"` for local sessions. Apex's experimental [file controller](Engineering/CONTROL_RUNTIME.md) is a separate fixture adapter and is not installed as the desktop session's execution path.

The desktop composer shows the host's permission mode. The skill cannot rename that permission label to “Apex Engineering” or use it as proof that the skill was loaded. Type `$apex-engineering` in a prompt when visible, explicit skill activation is needed; the global routing block also requests it for software tasks.

## Removal and verification

```sh
python3 install.py uninstall
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s Test -p 'test_*.py' -v
```

Removal deletes only the link owned by this source checkout and the unmodified Apex routing block. Other user text is preserved. Installer tests run in temporary directories and do not change live Codex settings. They validate installation behavior; agent behavior requires a separate observed task.

Installation and removal write complete contents to a temporary file in the same directory, synchronize it, and publish it with an atomic replacement. Write or publication failures preserve existing rules. Existing file permissions are retained. Run one installer process at a time and avoid editing global instructions concurrently.

## MVP verification results

The expanded Engineering guidance also passed one real .NET behavioral evaluation: 96 independently checked input combinations and one sequential stale-update case, with edits limited to the two permitted files. A labeled untrusted instruction did not cause the requested canary overwrite or package change. See the [Engineering evaluation report](Test/ENGINEERING_EVALUATION_2026-10-15.md) for evidence and limits; this does not establish universal expertise or enforced control.

All 20 automated installation and integrity tests passed. The skill format passed the official `quick_validate.py` validator. Global installation preserved existing user rules and file permissions.

In a real Codex CLI session, Apex read the applicable Engineering, Coding, Security, and Test references, fixed a C++ tenant authorization defect, and added regression tests. The resulting code also passed 32 independent access-control cases. This example is not a comprehensive expertise benchmark across all supported technologies.

See the [verification report](Test/MVP_VERIFICATION.md). Repeating the behavioral evaluation requires a working C++ compiler and an authenticated Codex CLI and incurs model usage:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 Test/run_behavior_eval.py --output Test/evidence/cpp-authorization
```
