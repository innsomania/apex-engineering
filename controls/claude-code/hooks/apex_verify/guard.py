"""Guard: pre-tool-use edit/refusal logic."""

import os
import re
from pathlib import Path
from typing import Any

from .baseline import find_root, load_scope
from .classify import LOCK_REASONS
from .output import emit
from .snapshot import in_scope
from .state import turn_lock

PATCH_FILE = re.compile(r"^\*\*\* (?:Add File|Update File|Delete File|Move to): (.+?)\s*$", re.MULTILINE)

CONFIG = Path(".apex") / "verify.json"
SCOPE = Path(".apex") / "scope.json"
REVIEW = Path(".apex") / "review.json"


def edit_targets(tool_input: dict[str, Any]) -> list[str]:
    """The files an edit tool call writes: one path, or every file a Codex patch touches."""
    target = tool_input.get("file_path") or tool_input.get("notebook_path")
    if isinstance(target, str):
        return [target]
    patch = tool_input.get("command")
    return PATCH_FILE.findall(patch) if isinstance(patch, str) else []


def claude_own_file(path: Path) -> bool:
    """Claude Code's plan and memory files, which live outside every project."""
    claude = (Path.home() / ".claude").resolve()
    try:
        parts = path.relative_to(claude).parts
    except ValueError:
        return False
    return (len(parts) >= 2 and parts[0] == "plans") or (
        len(parts) >= 4 and parts[0] == "projects" and parts[2] == "memory")


def refusal(event: dict[str, Any], cwd: Path, target: str) -> str | None:
    """Why the edit of one file is refused, or None when it may go ahead."""
    path = Path(target) if Path(target).is_absolute() else cwd / target
    path = path.resolve()
    lock = turn_lock(event.get("session_id", ""))
    if lock and not claude_own_file(path):
        return f"File edits are blocked for this turn. {LOCK_REASONS[lock]}"
    if path.parts[-2:] in (CONFIG.parts, SCOPE.parts, REVIEW.parts):
        return f"{path.parts[-2]}/{path.name} holds the user's Apex rules; only the user changes it."
    root = find_root(cwd)
    if root is None:
        return None
    try:
        allow = load_scope(root)
    except ValueError as error:
        return f"{error}. Ask the user to fix it before editing files."
    if allow is None:
        return None
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError:
        if claude_own_file(path):
            return None
        return f"{path} is outside the project; the approved scope covers only {root}. Ask the user."
    if not in_scope(relative, allow):
        return (f"{relative} is outside the approved scope (.apex/scope.json allows: {', '.join(allow)}). "
                "Do not work around this; ask the user whether this file may be changed.")
    return None


def guard(event: dict[str, Any]) -> None:
    tool_input = event.get("tool_input")
    targets = edit_targets(tool_input) if isinstance(tool_input, dict) else []
    cwd = Path(event.get("cwd") or os.getcwd())
    for target in targets:
        reason = refusal(event, cwd, target)
        if reason:
            deny(reason)
            return


def deny(reason: str) -> None:
    emit({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                 "permissionDecisionReason": reason}})
