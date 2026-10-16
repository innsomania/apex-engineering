#!/usr/bin/env python3
"""Claude Code hooks: a turn that changed files cannot end until the project's checks pass.

Opt-in per project: create `.apex/verify.json` at the project root, for example
{"command": "npm test", "timeout": 600}. Projects without that file are untouched.

Modes (first argument):
  baseline  UserPromptSubmit: remember the working-tree fingerprint at the start of a turn.
  stop      Stop / SubagentStop: if files changed this turn, run the command; block on failure.
  guard     PreToolUse (Write|Edit): refuse edits to `.apex/verify.json`.
"""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

CONFIG = Path(".apex") / "verify.json"
MAX_ATTEMPTS = 3
OUTPUT_TAIL = 4000
STATE_DIR = Path(os.environ.get("APEX_HOOK_STATE_DIR")
                 or Path.home() / ".claude" / "apex-hooks" / "state")
GATED_SUBAGENTS = {"apex-coding"}


def find_root(cwd):
    path = Path(cwd).resolve()
    for candidate in (path, *path.parents):
        if (candidate / CONFIG).is_file():
            return candidate
    return None


def load_config(root):
    try:
        config = json.loads((root / CONFIG).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ValueError(f"{CONFIG} is unreadable: {error}") from error
    command = config.get("command") if isinstance(config, dict) else None
    if not isinstance(command, str) or not command.strip():
        raise ValueError(f'{CONFIG} needs a non-empty "command"')
    timeout = config.get("timeout", 600)
    if not isinstance(timeout, (int, float)) or timeout <= 0:
        raise ValueError(f'{CONFIG} "timeout" must be a positive number of seconds')
    return command, timeout


def _git(root, *args):
    return subprocess.run(["git", *args], cwd=root, capture_output=True, timeout=30)


def fingerprint(root):
    """Hash of HEAD, tracked changes and untracked files; None outside a git work tree."""
    if _git(root, "rev-parse", "--is-inside-work-tree").returncode != 0:
        return None
    digest = hashlib.sha256()
    head = _git(root, "rev-parse", "--verify", "-q", "HEAD")
    digest.update(head.stdout)
    digest.update(_git(root, "diff", "--binary", *(["HEAD"] if head.returncode == 0 else [])).stdout)
    digest.update(_git(root, "diff", "--binary", "--cached").stdout)
    untracked = _git(root, "ls-files", "--others", "--exclude-standard", "-z").stdout
    for name in filter(None, untracked.split(b"\0")):
        path = root / os.fsdecode(name)
        digest.update(name)
        if path.is_file() and not path.is_symlink():
            try:
                digest.update(hashlib.sha256(path.read_bytes()).digest())
            except OSError:
                pass
    return digest.hexdigest()


def state_path(session_id, root):
    key = hashlib.sha256(f"{session_id}\0{root}".encode()).hexdigest()[:24]
    return STATE_DIR / f"{key}.json"


def read_state(path):
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        return state if isinstance(state, dict) else {}
    except (OSError, ValueError):
        return {}


def write_state(path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state), encoding="utf-8")
    os.replace(temporary, path)


def emit(payload):
    print(json.dumps(payload, ensure_ascii=False))


def baseline(event):
    root = find_root(event.get("cwd") or os.getcwd())
    if root is None:
        return
    path = state_path(event.get("session_id", ""), root)
    state = read_state(path)
    state.update({"baseline": fingerprint(root), "failures": 0})
    write_state(path, state)


def stop(event):
    if event.get("hook_event_name") == "SubagentStop" and event.get("agent_type") not in GATED_SUBAGENTS:
        return
    root = find_root(event.get("cwd") or os.getcwd())
    if root is None:
        return
    path = state_path(event.get("session_id", ""), root)
    state = read_state(path)
    current = fingerprint(root)
    if current is not None and current in (state.get("baseline"), state.get("passed")):
        return  # nothing changed this turn, or this exact tree already passed
    try:
        command, timeout = load_config(root)
    except ValueError as error:
        emit({"systemMessage": f"Apex verify: {error}"})
        return
    try:
        result = subprocess.run(command, shell=True, cwd=root, capture_output=True,
                                timeout=timeout, stdin=subprocess.DEVNULL)
        code = result.returncode
        output = (result.stdout + result.stderr).decode("utf-8", errors="replace")
    except subprocess.TimeoutExpired as error:
        code = "timeout"
        output = ((error.stdout or b"") + (error.stderr or b"")).decode("utf-8", errors="replace")
    if code == 0:
        state.update({"passed": current, "failures": 0})
        write_state(path, state)
        return
    failures = int(state.get("failures", 0)) + 1
    state["failures"] = failures
    write_state(path, state)
    if failures >= MAX_ATTEMPTS:
        emit({"systemMessage": f"Apex verify: `{command}` still fails after {failures} attempts. "
                               "The work is NOT done; Claude was allowed to stop so you can decide."})
        return
    tail = output[-OUTPUT_TAIL:]
    emit({"decision": "block",
          "reason": (f"Apex verification failed (attempt {failures}/{MAX_ATTEMPTS}): `{command}` exited "
                     f"with {code}. The task is not done. Fix the cause and finish again; do not "
                     "apologize, do not claim completion, and do not weaken the checks or edit "
                     f"{CONFIG}. If it cannot be fixed within scope, say exactly what blocks it.\n\n"
                     f"Output (last {OUTPUT_TAIL} chars):\n{tail}")})


def guard(event):
    tool_input = event.get("tool_input") or {}
    target = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not isinstance(target, str):
        return
    path = Path(target)
    if not path.is_absolute():
        path = Path(event.get("cwd") or os.getcwd()) / path
    if path.resolve().parts[-2:] == CONFIG.parts:
        emit({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": f"{CONFIG} defines how Apex verifies work; only the user changes it."}})


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    mode = argv[0] if argv else ""
    try:
        event = json.load(sys.stdin)
    except ValueError:
        event = {}
    if not isinstance(event, dict):
        event = {}
    handler = {"baseline": baseline, "stop": stop, "guard": guard}.get(mode)
    if handler is None:
        print(f"usage: {Path(__file__).name} baseline|stop|guard", file=sys.stderr)
        return 1
    handler(event)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
