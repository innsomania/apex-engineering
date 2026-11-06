#!/usr/bin/env python3
"""Claude Code and Codex hooks - thin wrapper using modular apex_verify package."""

import sys
from pathlib import Path

# Add the apex_verify package to sys.path
PACKAGE_DIR = Path(__file__).parent / "apex_verify"
sys.path.insert(0, str(PACKAGE_DIR.parent))

# Re-export everything from the modular package for backward compatibility
from apex_verify import (  # noqa: E402
    LOCK_REASONS,
    baseline,
    classify,
    claude_own_file,
    control_digest,
    deny,
    edit_targets,
    fail,
    find_root,
    fingerprint,
    finish,
    guard,
    in_scope,
    instructions_path,
    last_verdict,
    load_config,
    load_scope,
    lock_path,
    main,
    map_problems,
    nearby_controls,
    offer_setup,
    read_lock,
    read_state,
    record_review,
    refusal,
    report_locked_changes,
    require_review,
    reviewer_verdict,
    set_turn_lock,
    snapshot,
    state_path,
    stop,
    tampered_controls,
    turn_changes,
    turn_lock,
    unlock,
    write_instructions,
    write_state,
)

__all__ = [
    "LOCK_REASONS",
    "baseline",
    "classify",
    "claude_own_file",
    "control_digest",
    "deny",
    "edit_targets",
    "fail",
    "find_root",
    "fingerprint",
    "finish",
    "guard",
    "in_scope",
    "instructions_path",
    "last_verdict",
    "load_config",
    "load_scope",
    "lock_path",
    "main",
    "map_problems",
    "nearby_controls",
    "offer_setup",
    "read_lock",
    "read_state",
    "record_review",
    "refusal",
    "report_locked_changes",
    "require_review",
    "reviewer_verdict",
    "set_turn_lock",
    "snapshot",
    "state_path",
    "stop",
    "tampered_controls",
    "turn_changes",
    "turn_lock",
    "unlock",
    "write_instructions",
    "write_state",
]

if __name__ == "__main__":
    raise SystemExit(main())
