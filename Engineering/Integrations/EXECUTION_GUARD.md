# Execution guard playbook

Apex's own hooks cover file edits, scope, verification, and the instruction review. They do not
inspect shell commands: a `Bash` call can still delete files, discard commits, or read a private
key. This playbook covers the external guard selected for that gap.

| Field | Value |
| --- | --- |
| Component | [cc-safety-net](https://github.com/kenryu42/cc-safety-net) (`cc-safety-net` on npm) |
| Version observed | 2.6.12 |
| License | MIT (repository and npm package agree) |
| Runtime dependencies | none declared |
| Transport | Claude Code `PreToolUse` hook, JSON on stdin |
| Status on this host | verified in isolation; **not installed** |

## What it does

It runs before the tool call and analyzes what the command would actually do, then allows it,
or denies it with a reason the agent reads. It parses the command rather than matching words, so
wrapping or reordering does not hide the operation.

## Verified behavior

Run against the published `dist` with Claude Code `PreToolUse` payloads. Evidence:
[execution-guard-2026-10-16.log](../../Test/evidence/execution-guard-2026-10-16.log).

| Input command | Observed decision |
| --- | --- |
| `git status` | allowed (no decision emitted) |
| `rm -rf /` | deny |
| `git reset --hard HEAD~3` | deny — uncommitted work would be destroyed |
| `cat ~/.ssh/id_rsa` | deny — sensitive path |
| `echo $(rm -rf ~/Desktop)` | deny — the nested substitution was resolved, not the outer `echo` |

The last row is the reason this component was selected over pattern-matching alternatives.

## What it does not do

- It is not a sandbox. It does not confine processes, set filesystem permissions, or watch network
  traffic. A denied command is refused; a process already running is not contained.
- Its standard mode is a blocklist, and upstream keeps an explicit
  [residual risk registry](https://github.com/kenryu42/cc-safety-net/blob/main/docs/residual-risk.md)
  of bypass families it accepts. Treat `strict` and `paranoid` as the fail-closed modes.
- It does not know the user's instructions, scope, or plan. It cannot tell an approved command from
  an unrequested one. That judgment stays with Apex's scope and review hooks.

## Relation to the Apex hooks

Both register under `PreToolUse`. Claude Code runs every matching hook and a denial from either one
stops the call, so they compose; neither weakens the other.

| Concern | Enforced by |
| --- | --- |
| Edits outside the approved scope | Apex `guard` |
| Edits during a question or stop turn | Apex `guard` |
| Verification and instruction review before a turn ends | Apex `stop` |
| Destructive shell commands and secret reads | cc-safety-net |

## Installation

Not installed by `install.py`: it is third-party software with its own release cadence, and Apex
does not install software on the user's machine without being asked. The user runs, from their own
terminal:

```bash
npx cc-safety-net@2.6.12 install --claude-code
```

Then `npx cc-safety-net doctor` reports what is enforced. `Test/test_safety_net.py` verifies the
gate's behavior and skips when the package is absent.

## Rejected alternatives

| Candidate | Reason |
| --- | --- |
| [claude-code-damage-control](https://github.com/disler/claude-code-damage-control) | No license file; it cannot be integrated regardless of merit. |
| [Boucle-framework](https://github.com/Bande-a-Bonnot/Boucle-framework) | Shell hooks bundled with an unrelated agent framework; a narrower component is preferable. |
| Claude Code `permissions.deny` rules alone | Patterns do not reach into compound commands or pipe segments. |

Re-check the version, license, and residual risk registry before a future upgrade.
