# Apex Engineering

One engineering workflow (`SKILL.md` and `guides/`) plus runtime controls for Claude Code and Codex.

## Where things are
- `SKILL.md`: entry point (task contract, stages, work loop). `guides/`: engineering, coding (per stack), test, security.
- `controls/claude-code/hooks/apex_verify_hook.py`: the only hook; modes `baseline` (UserPromptSubmit), `guard` (PreToolUse), `stop` (Stop/SubagentStop), `unlock`; host is argv[2] (`claude`|`codex`).
  - Prompt classification and question/stop lock: `classify()`, `set_turn_lock()`.
  - Pre-edit scope refusal: `guard()` → `refusal()`, `edit_targets()`; Codex patches parsed by `PATCH_FILE`.
  - Turn-end scope check: `stop()` → `turn_changes()` (snapshot diff, catches shell edits) + `in_scope()`.
  - Verify command: `load_config()` reads `.apex/verify.json` (`CONFIG`); run in `stop()`; `MAX_ATTEMPTS` = 3.
  - Review gate: `require_review()`, `record_review()`, `reviewer_verdict()`; reviewer agent `apex-reviewer`.
  - Control tamper check: `control_digest()`, `tampered_controls()`.
- `controls/apex_project.py`: per-project `.apex/` setup (init, suggest, list, upgrade).
- Agents: `controls/claude-code/agents/*.md`, `controls/codex/agents/*.toml` (same instructions; a test keeps them equal).
- `install.py`: links skill, writes hooks, copies Codex agents (`configure()`, `merge_hooks()`).
- `run_apex.py`: starts a host session with the Apex prompt.
- `tests/`: unittest suites (`tests/test_*.py`) and live/mutation runners (`tests/run_*.py`).

## Checks
`python3 -m unittest discover -s tests`; `python3 tests/run_mutation_check.py`; ruff + mypy from requirements-dev.txt.
