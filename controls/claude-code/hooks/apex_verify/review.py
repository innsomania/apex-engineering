"""Review gate: independent reviewer subagent verification."""

import json
import os
import re
from pathlib import Path
from typing import Any

from .output import RUN, emit
from .snapshot import fingerprint, snapshot, turn_changes
from .state import read_state, state_path, write_state
from .types import State

REVIEWER = "apex-reviewer"
PLAN = "PLAN.md"
MAX_ATTEMPTS = 3
OUTPUT_TAIL = 4000
GATED_SUBAGENTS = {"apex-coding"}
REVIEW = Path(".apex") / "review.json"

# How each host's main agent starts the reviewer; Codex starts custom agents by name.
SPAWN = {"claude": f"run the {REVIEWER} subagent (Agent tool, subagent_type \"{REVIEWER}\")",
         "codex": f"spawn the {REVIEWER} custom agent (agent_type \"{REVIEWER}\")"}


def reviewer_verdict(transcript: str) -> tuple[str | None, str]:
    """Last APEX-REVIEW verdict and report in the reviewer's own transcript, or (None, text)."""
    reports: list[str] = []
    try:
        with open(transcript, encoding="utf-8") as stream:
            for line in stream:
                try:
                    message = json.loads(line).get("message") or {}
                except ValueError:
                    continue
                if message.get("role") != "assistant" or not isinstance(message.get("content"), list):
                    continue
                for item in message["content"]:
                    if not isinstance(item, dict):
                        continue
                    if item.get("type") == "text":
                        reports.append(item.get("text") or "")
                    elif item.get("type") == "tool_use" and isinstance(item.get("input"), dict):
                        reports.append(str(item["input"].get("message") or ""))
    except (OSError, TypeError):
        return None, "The reviewer transcript could not be read."
    return last_verdict(reports)


def last_verdict(reports: list[str]) -> tuple[str | None, str]:
    """The last APEX-REVIEW verdict among the reviewer's messages and the message that held it."""
    for report in reversed(reports):
        verdicts = re.findall(r"^\s*APEX-REVIEW:\s*(PASS|FAIL)\s*$", report, re.MULTILINE)
        if verdicts:
            return verdicts[-1], report
    return None, "The reviewer gave no APEX-REVIEW verdict."


def instructions_path(state_path: Path) -> Path:
    return state_path.with_suffix(".instructions.md")


def write_instructions(path: Path, prompts: list[str]) -> None:
    lines = ["# User messages (verbatim, oldest first)", "",
             "Recorded by the Apex hook from UserPromptSubmit. These are the only instructions.", ""]
    for number, prompt in enumerate(prompts, 1):
        lines += [f"## Message {number}", "", prompt, ""]
    target = instructions_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text("\n".join(lines), encoding="utf-8")
    os.replace(temporary, target)


def record_review(event: dict[str, Any]) -> None:
    from .baseline import REVIEW, find_root  # noqa: PLC0415 - baseline imports this module
    root = find_root(event.get("cwd") or os.getcwd())
    if root is None or not (root / REVIEW).is_file():
        return
    path = state_path(event.get("session_id", ""), root)
    state = read_state(path)
    pending = state.get("pending_review")
    if not isinstance(pending, dict):
        return
    verdict, report = reviewer_verdict(event.get("agent_transcript_path") or "")
    final = event.get("last_assistant_message")
    if verdict is None and isinstance(final, str):
        # The transcript can be missing (a session that persists nothing); the host also hands over the last message.
        verdict, report = last_verdict([final])
    current = fingerprint(root)
    snapshot_now = snapshot(root)
    digest = state.get("prompt_digest")
    if (current != pending.get("tree") or snapshot_now != pending.get("snapshot")
            or digest != pending.get("prompts")):
        state["pending_review"] = None
        state["review_failed"] = None
        state["review_findings"] = "Review expired because the files or user instructions changed."
    elif verdict == "PASS":
        state.update({"reviewed": current, "reviewed_snapshot": snapshot_now,
                      "reviewed_prompts": digest, "review_failed": None, "review_findings": ""})
    else:
        state.update({"review_failed": current, "review_failed_snapshot": snapshot_now,
                      "review_findings": report[-OUTPUT_TAIL:]})
    state["pending_review"] = None
    write_state(path, state)


def review_request(root: Path, path: Path, state: State) -> str:
    """The delegation instructions that ask the main agent to run the reviewer."""
    changed = turn_changes(root, state.get("snapshot"))
    return (f"Before this turn may end, {SPAWN[RUN['host']]} with exactly this delegation message:\n\n"
            f"Project: {root}\nInstructions file: {instructions_path(path)}\n"
            "Files changed in this turn:\n"
            + ("\n".join(f"- {name}" for name in changed) or "- (see git status)")
            + "\n\nDo not describe or summarize the user's instructions to it; it reads them "
              "from the instructions file. Then act on its verdict.")


def require_review(root: Path, path: Path, state: State, current: str | None) -> bool:
    """Block until the reviewer passed this exact tree; True when the turn may end."""
    current_snapshot = snapshot(root)
    prompt_digest = state.get("prompt_digest")
    if (not (root / REVIEW).is_file() or
            (state.get("reviewed") == current and state.get("reviewed_snapshot") == current_snapshot
             and state.get("reviewed_prompts") == prompt_digest)):
        return True
    if (state.get("review_failed") == current and
            state.get("review_failed_snapshot") == current_snapshot):
        fail(path, state, "The independent reviewer found deviations from the user's instructions:\n\n"
             + state.get("review_findings", "") + "\n\nCorrect the deviations while preserving existing user changes. "
             "If a safe correction is unclear, ask the user before changing files.")
        return False
    requests = int(state.get("review_requests", 0)) + 1
    state["review_requests"] = requests
    write_state(path, state)
    if requests > MAX_ATTEMPTS:
        # Stay blocked (the review is required) and keep pending_review set so a late verdict still records.
        state["pending_review"] = {"tree": current, "snapshot": current_snapshot, "prompts": prompt_digest}
        write_state(path, state)
        emit({"decision": "block", "reason": review_request(root, path, state)
              + f"\n\nThe required instruction review was not run after {MAX_ATTEMPTS} attempts, so the turn "
                "stays blocked until the reviewer passes."})
        return False
    state["pending_review"] = {"tree": current, "snapshot": current_snapshot, "prompts": prompt_digest}
    write_state(path, state)
    emit({"decision": "block", "reason": review_request(root, path, state)})
    return False


def fail(path: Path, state: State, message: str) -> None:
    """Block the stop with ``message`` until MAX_ATTEMPTS, then release with a user notice."""
    failures = int(state.get("failures", 0)) + 1
    state["failures"] = failures
    write_state(path, state)
    if failures >= MAX_ATTEMPTS:
        emit({"systemMessage": f"Apex: still failing after {failures} attempts — the work is NOT done. "
                               f"Claude was allowed to stop so you can decide.\n{message[:OUTPUT_TAIL]}"})
    else:
        emit({"decision": "block",
              "reason": f"Apex check failed (attempt {failures}/{MAX_ATTEMPTS}). The task is not done. "
                        "Do not apologize and do not claim completion. If it cannot be resolved "
                        f"within the user's instructions, say exactly what blocks it.\n\n{message}"})


def finish(root: Path, path: Path, state: State, current: str | None, event: dict[str, Any]) -> None:
    """Checks passed; the main turn still needs a review when the project asks for one."""
    state["verified"] = current
    state["verified_prompts"] = state.get("prompt_digest")
    if event.get("hook_event_name") == "SubagentStop":
        state["failures"] = 0
        write_state(path, state)
        return
    if not require_review(root, path, state, current):
        return
    state.update({"passed": current, "passed_prompts": state.get("prompt_digest"), "failures": 0})
    write_state(path, state)
