#!/usr/bin/env python3
"""Claude Code hooks that keep an agent inside the user's instructions.

Opt-in per project, both files at the project root and both changed only by the user:
  .apex/verify.json  {"command": "npm test", "timeout": 600}
                     A turn that changed files cannot end until the command passes.
  .apex/scope.json   {"allow": ["src/", "tests/*.py"]}
                     Files the approved plan may change. A pattern ending in "/" covers that
                     folder; other patterns are fnmatch globs where "*" also crosses folders.
  .apex/review.json  {}
                     A turn that changed files cannot end until the apex-reviewer subagent has
                     compared exactly this working tree with the user's verbatim messages and
                     reported APEX-REVIEW: PASS.
Projects without these files are untouched, except for the turn lock below, which applies everywhere.

Modes (first argument):
  baseline  UserPromptSubmit: remember the working tree and record the user's message. A message
            that asks a question or says stop (including anger) locks file edits for that turn.
  stop      Stop / SubagentStop: block if files outside the scope changed this turn, then
            run the verify command, then require a passing review; block on failure.
            For the apex-reviewer subagent it records the reviewer's verdict instead.
  guard     PreToolUse (Write|Edit): refuse edits during a locked turn, to `.apex/` configs, and
            outside the scope.
"""

import fnmatch
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

CONFIG = Path(".apex") / "verify.json"
SCOPE = Path(".apex") / "scope.json"
REVIEW = Path(".apex") / "review.json"
REVIEWER = "apex-reviewer"
MAX_PROMPTS = 30
MAX_PROMPT_CHARS = 16000
MAX_ATTEMPTS = 3
OUTPUT_TAIL = 4000
STATE_DIR = Path(os.environ.get("APEX_HOOK_STATE_DIR")
                 or Path.home() / ".claude" / "apex-hooks" / "state")
GATED_SUBAGENTS = {"apex-coding"}


def find_root(cwd):
    path = Path(cwd).resolve()
    for candidate in (path, *path.parents):
        if any((candidate / name).is_file() for name in (CONFIG, SCOPE, REVIEW)):
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
        elif key == "hookSpecificOutput" and "additionalContext" in OUTPUT.get(key, {}):
            context = OUTPUT[key]["additionalContext"]
            OUTPUT[key] = {**OUTPUT[key], **value}
            if "additionalContext" in value:
                OUTPUT[key]["additionalContext"] = context + "\n\n" + value["additionalContext"]
        else:
            OUTPUT[key] = value


def nearby_controls(cwd, depth=2, limit=5):
    """`.apex` folders below cwd; they do nothing for a session opened in cwd."""
    found, frontier = [], [Path(cwd)]
    for _ in range(depth):
        next_frontier = []
        for folder in frontier:
            try:
                children = sorted(child for child in folder.iterdir() if child.is_dir())
            except OSError:
                continue
            for child in children:
                if child.name.startswith(".") or child.name == "node_modules":
                    continue
                if (child / ".apex").is_dir():
                    found.append(child.relative_to(cwd).as_posix())
                next_frontier.append(child)
        frontier = next_frontier
    return found[:limit]


FOLD = str.maketrans("ıİşŞğĞüÜöÖçÇâÂîÎ", "iissgguuoocCaAiI")
STOP_WORDS = re.compile(
    r"\b(dur|durdur|stop|yeter|bekle|salak|aptal|gerizekali|orospu|siktir|sikim|amk|aq|"
    r"allah belani|ne yapiyorsun|ne yapiyosun|kafayi yi\w*)\b")
QUESTION_WORDS = re.compile(
    r"\b(mi|mu|misin|musun|miyim|muyum|miyiz|muyuz|midir|mudur|miydi|muydu|"
    r"neden|niye|nasil|nerede|nereye|hangi|kim|why|how|what|where|which)\b")
LOCK_REASONS = {
    "stop": "The user wants you to stop. Do not continue or restart the previous work. In at most two "
            "sentences say what state the work is in, then wait for the user's instruction.",
    "question": "The user asked a question. Answer it directly in your first sentence; read files only "
                "if the answer needs it. Do not start or continue any work; if work is needed, say "
                "what and wait for the user's go-ahead.",
}


def classify(prompt):
    """'stop', 'question' or None for a user message; a stop signal outranks a question."""
    text = prompt.translate(FOLD).lower()
    if STOP_WORDS.search(text):
        return "stop"
    if text.rstrip().endswith("?") or QUESTION_WORDS.search(text):
        return "question"
    return None


def lock_path(session_id):
    return STATE_DIR / f"{hashlib.sha256(session_id.encode()).hexdigest()[:24]}.lock"


def set_turn_lock(event):
    """Lock file edits for this turn when the user asked a question or said stop."""
    prompt = event.get("prompt")
    kind = classify(prompt) if isinstance(prompt, str) else None
    path = lock_path(event.get("session_id", ""))
    if kind is None:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(kind, encoding="utf-8")
    emit({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                 "additionalContext": f"Apex: {LOCK_REASONS[kind]} File edits are "
                                                      "blocked for this turn."}})


def turn_lock(session_id):
    try:
        kind = lock_path(session_id).read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return kind if kind in LOCK_REASONS else None


def baseline(event):
    set_turn_lock(event)
    cwd = event.get("cwd") or os.getcwd()
    root = find_root(cwd)
    if root is None:
        misplaced = nearby_controls(cwd)
        if misplaced:
            where = ", ".join(f"{name}/.apex" for name in misplaced)
            emit({"systemMessage": f"Apex controls are OFF for this session: they exist in {where}, "
                                   f"but the session is opened in {cwd}. Nothing is verified, scoped or reviewed.",
                  "hookSpecificOutput": {
                      "hookEventName": "UserPromptSubmit",
                      "additionalContext": (
                          f"Apex warning: verification, scope and review are NOT active. Apex settings were "
                          f"found in {where}, but they only apply when the session's folder ({cwd}) or a parent "
                          "contains .apex. Tell the user before doing any work, and set the controls up at the "
                          "session folder as the apex-engineering skill describes.")}})
        return
    path = state_path(event.get("session_id", ""), root)
    state = read_state(path)
    state.update({"baseline": fingerprint(root), "snapshot": snapshot(root),
                  "failures": 0, "review_requests": 0})
    prompt = event.get("prompt")
    if isinstance(prompt, str) and prompt.strip():
        prompts = state.get("prompts", []) + [prompt[:MAX_PROMPT_CHARS]]
        state["prompts"] = prompts[-MAX_PROMPTS:]
        write_instructions(path, state["prompts"])
    write_state(path, state)


def instructions_path(path):
    return path.with_suffix(".instructions.md")


def write_instructions(path, prompts):
    lines = ["# User messages (verbatim, oldest first)", "",
             "Recorded by the Apex hook from UserPromptSubmit. These are the only instructions.", ""]
    for number, prompt in enumerate(prompts, 1):
        lines += [f"## Message {number}", "", prompt, ""]
    target = instructions_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text("\n".join(lines), encoding="utf-8")
    os.replace(temporary, target)


def reviewer_verdict(transcript):
    """Last APEX-REVIEW verdict and report in the reviewer's own transcript, or (None, text)."""
    reports = []
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
    for report in reversed(reports):
        verdicts = re.findall(r"^\s*APEX-REVIEW:\s*(PASS|FAIL)\s*$", report, re.MULTILINE)
        if verdicts:
            return verdicts[-1], report
    return None, "The reviewer gave no APEX-REVIEW verdict."


def record_review(event):
    root = find_root(event.get("cwd") or os.getcwd())
    if root is None or not (root / REVIEW).is_file():
        return
    path = state_path(event.get("session_id", ""), root)
    state = read_state(path)
    verdict, report = reviewer_verdict(event.get("agent_transcript_path") or "")
    current = fingerprint(root)
    if verdict == "PASS":
        state.update({"reviewed": current, "review_failed": None, "review_findings": ""})
    else:
        state.update({"review_failed": current, "review_findings": report[-OUTPUT_TAIL:]})
    write_state(path, state)


def require_review(root, path, state, current):
    """Block until the reviewer passed this exact tree; True when the turn may end."""
    if not (root / REVIEW).is_file() or (current is not None and state.get("reviewed") == current):
        return True
    if current is not None and state.get("review_failed") == current:
        fail(path, state, "The independent reviewer found deviations from the user's instructions:\n\n"
             + state.get("review_findings", "") + "\n\nUndo or correct each deviation so the work matches "
             "the user's words exactly (or stop and ask the user), then the review runs again.")
        return False
    requests = int(state.get("review_requests", 0)) + 1
    state["review_requests"] = requests
    write_state(path, state)
    if requests > MAX_ATTEMPTS:
        emit({"systemMessage": "Apex: the required instruction review was not run. "
                               "Treat this work as unreviewed."})
        return False
    changed = turn_changes(root, state.get("snapshot")) if snapshot(root) is not None else []
    emit({"decision": "block",
          "reason": "Before this turn may end, run the apex-reviewer subagent (Agent tool, "
                    f"subagent_type \"{REVIEWER}\") with exactly this delegation message:\n\n"
                    f"Project: {root}\nInstructions file: {instructions_path(path)}\n"
                    "Files changed in this turn:\n" + ("\n".join(f"- {name}" for name in changed) or "- (see git status)")
                    + "\n\nDo not describe or summarize the user's instructions to it; it reads them "
                      "from the instructions file. Then act on its verdict."})
    return False


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
    if event.get("hook_event_name") == "SubagentStop":
        if event.get("agent_type") == REVIEWER:
            record_review(event)
            return
        if event.get("agent_type") not in GATED_SUBAGENTS:
            return
    root = find_root(event.get("cwd") or os.getcwd())
    if root is None:
        return
    path = state_path(event.get("session_id", ""), root)
    state = read_state(path)
    current = fingerprint(root)
    if current is not None and current in (state.get("baseline"), state.get("passed")):
        return  # nothing changed this turn, or this exact tree already passed
    if current is not None and state.get("verified") == current:
        finish(root, path, state, current, event)  # checks passed in a subagent; review still due
        return
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
        finish(root, path, state, current, event)
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
        finish(root, path, state, current, event)
        return
    fail(path, state, f"Verification `{command}` exited with {code}. Fix the cause and finish again; "
                      f"do not weaken the checks or edit {CONFIG}.\n\nOutput (last {OUTPUT_TAIL} chars):\n"
                      + output[-OUTPUT_TAIL:])


def finish(root, path, state, current, event):
    """Checks passed; the main turn still needs a review when the project asks for one."""
    state["verified"] = current
    if event.get("hook_event_name") == "SubagentStop":
        state["failures"] = 0
        write_state(path, state)
        return
    if not require_review(root, path, state, current):
        return
    state.update({"passed": current, "failures": 0})
    write_state(path, state)


def deny(reason):
    emit({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                 "permissionDecisionReason": reason}})


def claude_own_file(path):
    """Claude Code's plan and memory files, which live outside every project."""
    claude = (Path.home() / ".claude").resolve()
    try:
        parts = path.relative_to(claude).parts
    except ValueError:
        return False
    return (len(parts) >= 2 and parts[0] == "plans") or (
        len(parts) >= 4 and parts[0] == "projects" and parts[2] == "memory")


def guard(event):
    tool_input = event.get("tool_input") or {}
    target = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not isinstance(target, str):
        return
    cwd = Path(event.get("cwd") or os.getcwd())
    path = Path(target) if Path(target).is_absolute() else cwd / target
    path = path.resolve()
    lock = turn_lock(event.get("session_id", ""))
    if lock and not claude_own_file(path):
        deny(f"File edits are blocked for this turn. {LOCK_REASONS[lock]}")
        return
    if path.parts[-2:] in (CONFIG.parts, SCOPE.parts, REVIEW.parts):
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
        if claude_own_file(path):
            return
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
