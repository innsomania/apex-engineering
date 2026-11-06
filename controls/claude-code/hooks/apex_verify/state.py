"""State persistence for hook turn tracking."""

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from .classify import LOCK_REASONS, QUESTION_NOTE, STATUS_NOTE, classify
from .output import emit
from .snapshot import fingerprint
from .types import State

STATE_DIR = Path(os.environ.get("APEX_HOOK_STATE_DIR")
                 or Path.home() / ".claude" / "apex-hooks" / "state")


def root_pointer(session_id: str) -> Path:
    return STATE_DIR / f"{hashlib.sha256(session_id.encode()).hexdigest()[:24]}.root"


def remembered_root(session_id: str) -> Path | None:
    """The project root this session had at its last prompt, if it still exists."""
    try:
        root = Path(root_pointer(session_id).read_text(encoding="utf-8").strip())
    except OSError:
        return None
    return root if root.is_dir() else None


def state_path(session_id: str, root: Path) -> Path:
    key = hashlib.sha256(f"{session_id}\0{root}".encode()).hexdigest()[:24]
    return STATE_DIR / f"{key}.json"


def read_state(path: Path) -> State:
    try:
        state: object = json.loads(path.read_text(encoding="utf-8"))
        return state if isinstance(state, dict) else {}
    except (OSError, ValueError):
        return {}


def write_state(path: Path, state: State) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state), encoding="utf-8")
    os.replace(temporary, path)


def lock_path(session_id: str) -> Path:
    return STATE_DIR / f"{hashlib.sha256(session_id.encode()).hexdigest()[:24]}.lock"


def set_turn_lock(event: dict[str, Any]) -> None:
    """Lock file edits for this turn when the user said stop; note a question or status check."""
    prompt = event.get("prompt")
    kind = classify(prompt) if isinstance(prompt, str) else None
    path = lock_path(event.get("session_id", ""))
    if kind != "stop":
        path.unlink(missing_ok=True)
        note = {"status": STATUS_NOTE, "question": QUESTION_NOTE}.get(kind or "")
        if note:
            emit({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": f"Apex: {note}"}})
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    cwd = event.get("cwd") or os.getcwd()
    try:
        tree = fingerprint(Path(cwd))
    except (OSError, subprocess.SubprocessError):
        tree = None
    path.write_text(json.dumps({"kind": kind, "cwd": cwd, "tree": tree}), encoding="utf-8")
    emit({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                 "additionalContext": f"Apex: {LOCK_REASONS[kind]} File edits are "
                                                       "blocked for this turn."}})


def read_lock(session_id: str) -> State | None:
    """The lock record {"kind", "cwd", "tree"} for this turn, or None."""
    try:
        lock: object = json.loads(lock_path(session_id).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return lock if isinstance(lock, dict) and lock.get("kind") in LOCK_REASONS else None


def turn_lock(session_id: str) -> str | None:
    lock = read_lock(session_id)
    kind: str | None = lock["kind"] if lock else None
    return kind


def report_locked_changes(event: dict[str, Any]) -> None:
    """Edits are refused during a locked turn, but shell commands can still change files."""
    lock = read_lock(event.get("session_id", ""))
    if not lock or lock.get("tree") is None:
        return
    try:
        current = fingerprint(Path(lock.get("cwd") or os.getcwd()))
    except (OSError, subprocess.SubprocessError):
        return
    if current != lock["tree"]:
        emit({"systemMessage": "Apex: files changed during a turn in which edits were locked "
                               f"(the user's message was a {lock['kind']}). Please review them."})
