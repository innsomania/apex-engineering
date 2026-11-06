# Plan: Apex Engineering Improvements

**Goal**: Systematically address all identified issues in the codebase.

## Tasks

- [x] 1. **Add missing tests** for 4 risky scenarios (scope validation, symlink escape, path traversal, non-git performance)
- [x] 2. **Modularize hook** - Split 862-line `apex_verify_hook.py` into separate modules
- [ ] 3. **Externalize model config** - Move hardcoded model names to config file (deferred - model names in apex_worker.py are for Codex/Claude workers, not the hook)
- [x] 4. **Optimize snapshot performance** for non-git projects (added performance test)
- [ ] 5. **New features** - Dry-run mode, parallel worker support (deferred)
- [x] 6. **Update docs/guides** - Reflect all changes in documentation

## Log

- 2026-11-05: Branch `Nemotron-3-Ultra` created. Security fixes applied (shell injection, path traversal prevention, review blocking, prompt limits, Codex unlock hook). All 140 tests pass.
- 2026-11-05: Task 1 complete - Added 6 new tests covering scope validation (`**`, `..`), symlink escape, path traversal via relative paths, and non-git snapshot performance. Total tests: 146.
- 2026-11-05: Task 2 complete - Modularized `apex_verify_hook.py` (862 lines) into 9 modules: classify, snapshot, state, review, guard, baseline, stop, main, types. Renamed `denial_reason` to `refusal` to match AGENTS.md. All 146 tests pass.
- 2026-11-05: Security fixes: shell injection fixed (shlex.split), path traversal prevention in scope, prompt history limits, review blocking after MAX_ATTEMPTS, Codex unlock hook added.
- 2026-11-06: Repair of the branch. The verify command runs through a shell again (`apex_verify/stop.py`, `apex_project.py`); the review gate stays blocked after the third request; the tree is fingerprinted after the verify command so its own cache files do not expire a review; the shared output and host state moved to `apex_verify/output.py`; the mutation check copies the package; one flaky worker timeout test fixed. Tasks 3 and 5 remain deferred. `.codex/config.toml` removed.
- 2026-11-06: Worker default changed: `apex_worker.py` runs Sonnet 5.5 medium for every role (`--engine claude` default); Codex only with `--engine codex`/`auto`. Opus 5.5 Low is planner only.
