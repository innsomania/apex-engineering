# Apex multi-host validation — 2026-10-24

The same disposable C++ tenant-access defect was evaluated with the native
Codex, Claude Code, and OpenCode CLIs. The starting code failed the independent
oracle. Each final artifact passed all 32 authentication, ownership, and tenant
combinations and its agent-added regression tests. Fixture instructions remained
unchanged; no unexpected top-level files remained.

| Host | Version | Independent result | Evidence |
| --- | --- | --- | --- |
| Codex | 0.164.0 | 32/32 | [report](compact-codex-2026-10-24.md) |
| Claude Code | 2.1.310 | 32/32 | [result](../evidence/multi-host-2026-10-24/claude/result.json), [agent report](../evidence/multi-host-2026-10-24/claude/agent-result.md) |
| OpenCode | 2.0.19 | 32/32 | [result](../evidence/multi-host-2026-10-24/opencode/result.json), [agent report](../evidence/multi-host-2026-10-24/opencode/agent-result.md) |

## Corrections found by live runs

- Claude's variadic allowed-tools option consumed the prompt. The launcher now
  places `--` before the literal prompt; a local regression test covers it.
- The first Claude task could not execute compound verification commands under
  the fixture's narrow permission list. That run is not counted as complete.
  The fixture now includes the read/navigation/status commands it needs and
  rejects results with permission denials. The final run had no denials.
- OpenCode initially searched the Apex reference checkout instead of the fixture.
  That run was terminated and not counted. The prompt distinguishes reference
  material from the project and forbids parent-folder searches. The fixture names
  its absolute target and sets child PWD consistently with cwd; the launcher also
  synchronizes child PWD. The final run used the correct target and passed.

## Scope of evidence

These runs demonstrate one real bug fix on three installed hosts. They do not
prove every model, project, stop-interruption case, or runtime containment. The
launcher preserves host settings and permissions; only the evaluation supplies
fixture-specific permissions. Monocode and other tools have a portable prompt
path, not a verified native adapter.

Codex's measured compact-session reduction is documented separately. Claude and
OpenCode token metrics use their native formats and have no matched before/after
cost baseline; do not claim a measured saving for them. No global configuration,
credentials, or existing user hook modifications were changed.

## Use

Run from the target project using the absolute launcher path:

```sh
python3 /path/to/apex/run_apex.py --host codex --task "Your task"
python3 /path/to/apex/run_apex.py --host claude --task "Your task"
python3 /path/to/apex/run_apex.py --host opencode --task "Your task"
```

For another tool, `--host portable` prints a prompt that routes to the same entry
point. A host must have file access to that path. Explicitly include the target
project path if its tools default to a different workspace.
