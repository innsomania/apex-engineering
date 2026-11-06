# Apex Verify Hook - Modular implementation
# This package contains the split components of apex_verify_hook.py

from .baseline import (
    baseline,
    control_digest,
    find_root,
    load_config,
    load_scope,
    map_problems,
    nearby_controls,
    offer_setup,
    tampered_controls,
)
from .classify import LOCK_REASONS, classify
from .guard import claude_own_file, deny, edit_targets, guard, refusal
from .main import main
from .review import (
    fail,
    finish,
    instructions_path,
    last_verdict,
    record_review,
    require_review,
    reviewer_verdict,
    write_instructions,
)
from .snapshot import fingerprint, in_scope, snapshot, turn_changes
from .state import (
    lock_path,
    read_lock,
    read_state,
    report_locked_changes,
    set_turn_lock,
    state_path,
    turn_lock,
    write_state,
)
from .stop import stop, unlock

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
