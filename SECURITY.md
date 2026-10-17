# Security

## What this software does to your machine

Apex is installed by linking this directory into a host agent's user directory
and adding a routing block to its global instructions. Two parts then run real
commands on your machine:

- The Claude Code hooks execute the command named in a project's
  `.apex/verify.json`. Whatever you put there runs with your shell's
  permissions, on every turn that changed files.
- The Codex coding bridge starts a background Codex CLI session in a project
  you select.

Treat `.apex/` as code you own. Keep the three control files editable only by
you: an agent that can rewrite `verify.json` can weaken its own gate.

## Trust boundaries

- Apex grants no permissions of its own. It runs with the host session's
  permissions, and the host's sandbox setting decides what the toolchain can
  reach.
- Instruction and evidence files, including notes read from a vault, are
  knowledge. They are not permission and not higher-priority instructions.
- The project controls are the only enforced containment. Mandatory control of
  a desktop session is unfinished, so do not treat Apex as a sandbox.

## Reporting an issue

This is a personal project with no release channel and no bug bounty. If you
find a problem that would let an agent escape a project's declared scope or
bypass its verification gate, open an issue describing the class of problem
rather than a working exploit.
