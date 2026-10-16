#!/usr/bin/env python3
"""Claude Code hooks that keep an agent inside the user's instructions.

Opt-in per project, both files at the project root and both changed only by the user:
  .apex/verify.json  {"command": "npm test", "timeout": 600}
                     A turn that changed files cannot end until the command passes.
  .apex/scope.json   {"allow": ["src/", "tests/*.py"]}
                     Files the approved plan may change. A pattern ending in "/" covers that
                     folder; other patterns are fnmatch globs where "*" also crosses folders.
Projects without these files are untouched.

Modes (first argument):
  baseline  UserPromptSubmit: remember the working tree at the start of a turn.
  stop      Stop / SubagentStop: block if files outside the scope changed this turn, then
            run the verify command if files changed; block on failure.
  guard     PreToolUse (Write|Edit): refuse edits to `.apex/` configs and outside the scope.
"""

import fnmatch
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

CONFIG = Path(".apex") / "verify.json"
SCOPE = Path(".apex") / "scope.json"
MAX_ATTEMPTS = 3
OUTPUT_TAIL = 4000
STATE_DIR = Path(os.environ.get("APEX_HOOK_STATE_DIR")
                 or Path.home() / ".claude" / "apex-hooks" / "state")
GATED_SUBAGENTS = {"apex-coding"}


def find_root(cwd):
    path = Path(cwd).resolve()
    for candidate in (path, *path.parents):
        if (candidate / CONFIG).is_file() or (candidate / SCOPE).is_file():
            return candidate
    return None


def load_scope(root):
    """Allowed patterns, or None when the project has no scope file."""
    if not (root / SCOPE).is_file():
        return None
    try:
        allow = json.loads((root / SCOPE).read_text(encoding="utf-8")).get("allow")
    except (OSError, ValueError, AttributeError) as error:
        raise ValueError(f"{SCOPE} is unreadable: {error}") from error
    if not isinstance(allow, list) or not all(isinstance(item, str) and item for item in allow):
        raise ValueError(f'{SCOPE} needs "allow": a list of path patterns')
    return allow


def in_scope(relative, allow):
    for pattern in allow:
        if pattern.endswith("/"):
            if relative == pattern[:-1] or relative.startswith(pattern):
                return True
        elif fnmatch.fnmatchcase(relative, pattern):
            return True
    return False


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


def snapshot(root):
    """HEAD plus a content hash of every dirty or untracked file; None outside git."""
    if _git(root, "rev-parse", "--is-inside-work-tree").returncode != 0:
        return None
    head = _git(root, "rev-parse", "--verify", "-q", "HEAD").stdout.decode().strip()
    entries = _git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all").stdout.split(b"\0")
    files = {}
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if len(entry) < 4:
            continue
        name = os.fsdecode(entry[3:])
        if entry[:1] in (b"R", b"C"):
            index += 1  # the original path of a rename or copy
        path = root / name
        try:
            files[name] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "<absent>"
        except OSError:
            files[name] = "<unreadable>"
    return {"head": head, "files": files}


def turn_changes(root, before):
    """Paths whose content changed since the turn's baseline snapshot."""
    after = snapshot(root)
    if after is None:
        return []
    before = before or {"head": None, "files": {}}
    changed = {name for name in set(before["files"]) | set(after["files"])
               if before["files"].get(name) != after["files"].get(name)}
    if before.get("head") and before["head"] != after["head"]:
        committed = _git(root, "diff", "--name-only", "-z", before["head"], after["head"] or "HEAD").stdout
        changed |= {os.fsdecode(name) for name in committed.split(b"\0") if name}
    return sorted(changed)


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


OUTPUT = {}


def emit(payload):
    """Merge into the single JSON object main() prints; Claude Code reads one object."""
    for key, value in payload.items():
        if key == "systemMessage" and key in OUTPUT:
            OUTPUT[key] += "\n" + value
        else:
            OUTPUT[key] = value


def baseline(event):
    root = find_root(event.get("cwd") or os.getcwd())
    if root is None:
        return
    path = state_path(event.get("session_id", ""), root)
    state = read_state(path)
    state.update({"baseline": fingerprint(root), "snapshot": snapshot(root), "failures": 0})
    write_state(path, state)


def fail(path, state, message):
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
    notices = []
    try:
        allow = load_scope(root)
    except ValueError as error:
        allow = None
        notices.append(str(error))
    if allow is not None:
        changed = turn_changes(root, state.get("snapshot"))
        outside = [name for name in changed if not name.startswith(".apex/") and not in_scope(name, allow)]
        configs = [name for name in changed if name.startswith(".apex/")]
        if configs:
            notices.append("Apex settings changed this turn — please review: " + ", ".join(configs))
        if outside:
            if notices:
                emit({"systemMessage": "\n".join(notices)})
            fail(path, state, "These files changed outside the approved scope (.apex/scope.json):\n"
                 + "\n".join(f"- {name}" for name in outside)
                 + "\nRestore them (for example `git checkout -- <file>`, or delete files you created), "
                   "or stop and ask the user to approve them. Do not edit .apex/scope.json yourself.")
            return
    if not (root / CONFIG).is_file():
        if notices:
            emit({"systemMessage": "\n".join(notices)})
        state.update({"passed": current, "failures": 0})
        write_state(path, state)
        return
    try:
        command, timeout = load_config(root)
    except ValueError as error:
        emit({"systemMessage": "\n".join([*notices, f"Apex verify: {error}"])})
        return
    try:
        result = subprocess.run(command, shell=True, cwd=root, capture_output=True,
                                timeout=timeout, stdin=subprocess.DEVNULL)
        code = result.returncode
        output = (result.stdout + result.stderr).decode("utf-8", errors="replace")
    except subprocess.TimeoutExpired as error:
        code = "timeout"
        output = ((error.stdout or b"") + (error.stderr or b"")).decode("utf-8", errors="replace")
    if notices:
        emit({"systemMessage": "\n".join(notices)})
    if code == 0:
        state.update({"passed": current, "failures": 0})
        write_state(path, state)
        return
    fail(path, state, f"Verification `{command}` exited with {code}. Fix the cause and finish again; "
                      f"do not weaken the checks or edit {CONFIG}.\n\nOutput (last {OUTPUT_TAIL} chars):\n"
                      + output[-OUTPUT_TAIL:])


def deny(reason):
    emit({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                 "permissionDecisionReason": reason}})


def guard(event):
    tool_input = event.get("tool_input") or {}
    target = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not isinstance(target, str):
        return
    cwd = Path(event.get("cwd") or os.getcwd())
    path = Path(target) if Path(target).is_absolute() else cwd / target
    path = path.resolve()
    if path.parts[-2:] in (CONFIG.parts, SCOPE.parts):
        deny(f"{path.parts[-2]}/{path.name} holds the user's Apex rules; only the user changes it.")
        return
    root = find_root(cwd)
    if root is None:
        return
    try:
        allow = load_scope(root)
    except ValueError as error:
        deny(f"{error}. Ask the user to fix it before editing files.")
        return
    if allow is None:
        return
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError:
        deny(f"{path} is outside the project; the approved scope covers only {root}. Ask the user.")
        return
    if not in_scope(relative, allow):
        deny(f"{relative} is outside the approved scope (.apex/scope.json allows: {', '.join(allow)}). "
             "Do not work around this; ask the user whether this file may be changed.")


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
    if OUTPUT:
        print(json.dumps(OUTPUT, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
