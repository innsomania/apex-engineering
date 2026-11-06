"""Stop: turn end handling, verification, review gating."""

import os
import subprocess
from typing import Any

from .baseline import (
    CONFIG,
    OUTPUT_TAIL,
    find_root,
    load_config,
    load_scope,
    map_problems,
    tampered_controls,
)
from .output import emit
from .review import GATED_SUBAGENTS, REVIEWER, fail, finish, record_review
from .snapshot import fingerprint, in_scope, turn_changes
from .state import lock_path, read_state, remembered_root, report_locked_changes, state_path, turn_lock


def stop(event: dict[str, Any]) -> None:
    if event.get("hook_event_name") == "SubagentStop":
        if event.get("agent_type") == REVIEWER:
            record_review(event)
            return
        if event.get("agent_type") not in GATED_SUBAGENTS:
            return
    if event.get("hook_event_name") != "SubagentStop":
        report_locked_changes(event)
    if turn_lock(event.get("session_id", "")) == "stop":
        return
    session_id = event.get("session_id", "")
    root = find_root(event.get("cwd") or os.getcwd()) or remembered_root(session_id)
    if root is None:
        return
    path = state_path(session_id, root)
    state = read_state(path)
    tampered = tampered_controls(root, state)
    if tampered:
        fail(path, state, "Apex settings changed during this turn:\n" + "\n".join(f"- {name}" for name in tampered)
             + "\nDo not restore or discard these files automatically; preserve existing user changes and ask the user "
               "to make any requested control change themselves.")
        return
    current = fingerprint(root)
    prompt_digest = state.get("prompt_digest")
    if current is not None and current == state.get("baseline"):
        return  # nothing changed this turn, or this exact tree already passed
    if (current is not None and current == state.get("passed")
            and state.get("passed_prompts") == prompt_digest):
        return
    if (current is not None and state.get("verified") == current
            and state.get("verified_prompts") == state.get("prompt_digest")):
        finish(root, path, state, current, event)  # checks passed in a subagent; review still due
        return
    notices: list[str] = []
    try:
        allow = load_scope(root)
    except ValueError as error:
        allow = None
        notices.append(str(error))
    if allow is not None:
        changed = turn_changes(root, state.get("snapshot"))
        outside = [name for name in changed if not name.startswith(".apex/") and not in_scope(name, allow)]
        if outside:
            if notices:
                emit({"systemMessage": "\n".join(notices)})
            fail(path, state, "These files changed outside the approved scope (.apex/scope.json):\n"
                 + "\n".join(f"- {name}" for name in outside)
                 + "\nPreserve existing user changes. If you cannot identify a safe correction, stop and ask the user "
                   "whether these files may be changed. Do not edit .apex/scope.json yourself.")
            return
    stale = map_problems(root)
    if stale:
        fail(path, state, "The project map is out of date:\n" + "\n".join(f"- {item}" for item in stale)
             + "\nUpdate the \"Where things are\" section to match the code, then finish again.")
        return
    if not (root / CONFIG).is_file():
        if notices:
            emit({"systemMessage": "\n".join(notices)})
        finish(root, path, state, current, event)
        return
    try:
        command, timeout = load_config(root)
    except ValueError as error:
        emit({"systemMessage": "\n".join([*notices, f"Apex verify: {error}"])})
        return
    try:
        # The verify command is the project's own shell command, supplied by the user.
        result = subprocess.run(command, shell=True, cwd=root, capture_output=True,  # noqa: S602
                                timeout=timeout, stdin=subprocess.DEVNULL, check=False)
        code: int | str = result.returncode
        output = (result.stdout + result.stderr).decode("utf-8", errors="replace")
    except subprocess.TimeoutExpired as error:
        code = "timeout"
        output = ((error.stdout or b"") + (error.stderr or b"")).decode("utf-8", errors="replace")
    except OSError as error:
        code = "error"
        output = f"The verify command could not be started: {error}"
    if notices:
        emit({"systemMessage": "\n".join(notices)})
    if code == 0:
        # The command may have written files (caches, build output); the tree it leaves is the one reviewed.
        finish(root, path, state, fingerprint(root), event)
        return
    fail(path, state, f"Verification `{command}` exited with {code}. Fix the cause and finish again; "
                      f"do not weaken the checks or edit {CONFIG}.\n\nOutput (last {OUTPUT_TAIL} chars):\n"
                      + output[-OUTPUT_TAIL:])


def unlock(event: dict[str, Any]) -> None:
    """PostToolUse ExitPlanMode: the user approved a plan, so this turn may edit files."""
    lock_path(event.get("session_id", "")).unlink(missing_ok=True)
