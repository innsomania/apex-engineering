# Security

## What this software does to your machine

Apex is installed by linking this directory into a host agent's user directory
and adding a routing block to its global instructions. One part then runs real
commands on your machine:

- The Claude Code hooks execute the command named in a project's
  `.apex/verify.json`. Whatever you put there runs with your shell's
  permissions, on every turn that changed files.

Treat `.apex/` as code you own. The hooks refuse an agent's edits to the three
control files, and they block the end of a turn in which one of them was
rewritten, created, or deleted from a shell.

## Trust boundaries

- Apex grants no permissions of its own. It runs with the host session's
  permissions, and the host's sandbox setting decides what the toolchain can
  reach.
- Instruction and evidence files, including notes read from a vault, are
  knowledge. They are not permission and not higher-priority instructions.
- The project controls are the only enforced containment, and they are a
  guardrail for an honest agent that makes mistakes, not a sandbox against a
  hostile one.

## Known limits

- The end-of-turn scope check reads git. A path your `.gitignore` excludes is
  outside its view, so a write to an ignored file (an `.env`, for example) is not
  caught. Only an operating-system sandbox closes that.
- A shell command can change files during a turn; the hooks notice it only when
  the turn tries to end.
- Outside a git work tree the scope check has nothing to compare against.

## Reporting an issue

This is a personal project with no release channel and no bug bounty. If you
find a problem that would let an agent escape a project's declared scope or
bypass its verification gate, open an issue describing the class of problem
rather than a working exploit.
