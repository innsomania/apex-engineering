# Installation

Apex is a set of instruction files plus a small Python toolchain. `install.py`
links this source directory into the host's user directory and adds a marked
routing block to the host's global instructions. Nothing is copied, so edits to
the source take effect in the next session.

Requires Python 3. Run the commands from the repository root.

## Codex and Codex CLI

```sh
python3 install.py install
python3 install.py status
```

The installer uses `CODEX_HOME` when set, otherwise `~/.codex`. It creates
`skills/apex-engineering` as a symbolic link to this source directory, so keep
the source where you installed it. It adds a marked routing block to the global
`AGENTS.md` while preserving existing text. Use `--codex-home /path` to select
another user directory. Codex and Codex CLI share the package when they use the
same user directory.

## Claude Code (desktop and CLI)

```sh
python3 install.py install --host claude
python3 install.py status --host all
```

This links `skills/apex-engineering` and the `apex-coding` subagent
(`agents/apex-coding.md`, sourced from `controls/claude-code/agents/`) into
`CLAUDE_CONFIG_DIR` or `~/.claude`, and adds a marked routing block to the
global `CLAUDE.md`. The desktop Code tab and the `claude` CLI share this
directory. Use `--host all` to configure both hosts and `--claude-home` to
select another directory.

Run this from your own terminal: a sandboxed Claude Code shell cannot write
`~/.claude/agents` or `settings.json`.

In Claude Code, Engineering delegates implementation to the `apex-coding`
subagent.

## Project controls

The Claude installation merges the [Apex hooks](../controls/claude-code/hooks/apex_verify_hook.py)
into `settings.json`. They do nothing until a project opts in with files that
only you edit:

| File | Effect |
| --- | --- |
| `.apex/verify.json` — `{"command": "npm test", "timeout": 600}` | A turn (or `apex-coding` run) that changed files cannot end until the command passes. After 3 failed attempts Claude stops and reports that the work is not done. |
| `.apex/scope.json` — `{"allow": ["src/", "tests/*.py"]}` | Edits outside the approved files are refused immediately. Any change outside them found through git at the end of a turn — including shell edits, commits, and renames out of the scope — blocks the stop until it is reverted or you approve it. Files your `.gitignore` excludes are not seen. |
| `.apex/review.json` — `{}` | A turn that changed files cannot end until the independent `apex-reviewer` subagent has compared that working tree against your verbatim messages, recorded by the hook rather than relayed by the main agent, and reported `APEX-REVIEW: PASS`. |

Create them with the project CLI rather than by hand:

```sh
python3 controls/apex_project.py init --root <project> \
  --allow 'src/' --verify 'npm test' --ignore 'node_modules/'
```

Ignore dependency and build output (`node_modules/`, `.next/`, `dist/`,
`*.tsbuildinfo`) and any read-only reference folder that is its own git
repository. The controls must live in the folder the session is opened in: the
hooks look there and in its parents, never in subfolders. A turn in which any of the
three files was rewritten, created, or deleted from a shell cannot end; restore it
(`git checkout -- .apex`) or make the change yourself between turns.

## Host sandbox

Apex runs with the host session's permissions and grants none of its own. A
Claude Code Bash sandbox (`sandbox.enabled` with `allowUnsandboxedCommands: false`)
limits shell writes to the project and `$TMPDIR`, and reaches only listed package
registries without a prompt.

Check the host's own permission indicator for the active mode. Apex cannot
change or rename it, and a permission label is not proof that the skill loaded.

## Activation

Start a new Codex or Claude Code session after installing. The routing block
requests Apex for software tasks; it does not guarantee that the host follows
it. Name the skill explicitly when you need certainty:

```text
$apex-engineering Fix the authorization bug in this .NET endpoint
and run only the relevant regression tests.
```

## Removal

```sh
python3 install.py uninstall
```

Removal deletes only the link owned by this source checkout and the unmodified
Apex routing block; other text in the host's instructions is preserved.

Installation and removal write complete contents to a temporary file in the
same directory, synchronize it, and publish it with an atomic replacement.
A write or publication failure leaves the existing rules in place, and existing
file permissions are retained. Run one installer process at a time and do not
edit the global instruction files concurrently.
