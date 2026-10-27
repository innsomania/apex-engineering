# Host support

Apex has one shared workflow (`SKILL.md` and task-specific guides). The host
provides the model, tools, permissions, and optional runtime enforcement.
Apex adapts to the project; specialist guides are not a restriction on which
projects can use it.

| Host | Installation | Apex runtime controls |
| --- | --- | --- |
| Codex | `--host codex` | Existing hook and reviewer adapter; requires host activation and project configuration |
| Claude Code | `--host claude` | Existing hook and agent adapter; requires project configuration |
| OpenCode | `--host opencode` | Guidance only; no Apex hook adapter |
| Other tools, including Monocode | `--host portable --portable-home <directory>` | Guidance only; manually connect the host to the entry point |

OpenCode locations follow its official [skills](https://docs.opencode.ai/docs/skills/)
and [rules](https://docs.opencode.ai/docs/rules/) documentation. No Monocode-specific
configuration or runtime compatibility is claimed. Portable files require a host
that can read Markdown instructions and the referenced files.

Scope is enforced in two layers. A pre-edit guard refuses a write outside
`.apex/scope.json` before it happens, but it only sees the host's edit tools:
`Write`/`Edit` in Claude Code and `apply_patch` in Codex. A shell command can
still write anywhere; Codex workers often edit through `exec_command`. The Stop
and SubagentStop check compares the whole tree with the turn's start, so any
out-of-scope change, however it was made, keeps the turn or worker from
finishing until it is reverted or the user approves it.

## Execution contract

1. Read the user's task and relevant project rules; establish a bounded outcome.
2. Inspect only the evidence needed to choose the smallest correct change.
3. Use available tools and reuse context; delegate only when justified and allowed.
4. Implement within authorization, preserving existing user changes.
5. Run the narrowest meaningful verification; report infrastructure blockers.
6. Report results honestly and stop. A user stop takes precedence immediately.

Host limitations must be explicit. Without hooks, scope and verification are
behavioral guidance, not enforced barriers. Do not emulate a missing permission
or silently substitute unsupported tool APIs. Model selection and token budgets
belong to the host unless it exposes an authorized control.

## Evidence

Installer tests prove file routing, preservation, and removal in temporary
folders. They do not prove a model obeys the workflow. A live host evaluation
should use one small disposable task with a known outcome, verify its diff and
test result, and record host/model, tool calls, and token usage when available.
Do not claim measured savings or universal correctness from installation tests.

## Starting an Apex task

From this checkout:

```sh
python3 run_apex.py --task "Fix the specified bug and run its focused test" -- -C /path/to/project
```

For noninteractive runs, pass `exec` and its options after `--`. Use `--dry-run`
to inspect the exact argument list without starting a model. The launcher passes
the task as a literal argument and reads the shared entry point by absolute path.

This mode sets `skills.include_instructions=false` for that session, suppressing
the automatic skill catalog while explicitly routing the task to Apex. It does
not disable skill files, project instructions, permissions, hooks, or change the
model. Explicitly request any additional skill the task needs. Normal host
launching retains automatic skill discovery. No global configuration is written.
The setting is defined in the [Codex configuration schema](https://github.com/openai/codex/blob/main/codex-rs/core/config.schema.json).

The same launcher supports Claude Code and OpenCode with native arguments.
Run from the target project directory, using the absolute launcher path:

```sh
python3 /path/to/apex/run_apex.py --host claude --task "Fix the specified bug"
python3 /path/to/apex/run_apex.py --host opencode --task "Fix the specified bug"
python3 /path/to/apex/run_apex.py --host portable --task "Fix the specified bug"
```

Claude Code and OpenCode retain their native skill loading and permission
settings; Codex-only options are never passed to them. Portable mode prints an
explicit Apex task prompt for another host, including Monocode; it does not claim
that a particular unimplemented host adapter exists. Pass that prompt to a host
with access to this checkout. No model choice is imposed by the launcher.

For one small live check, `tests/run_behavior_eval.py --host <host> --output <dir>`
uses the same C++ fixture and independent oracle on each supported CLI. It uses
existing authentication. Claude allows only the fixture's read/edit and compile
commands; OpenCode uses its native auto-approval mode in the disposable fixture.
Neither evaluation changes global configuration. Missing prerequisites stop the
run. Host token accounting is not interchangeable; absent metrics remain unknown.
