"""Baseline: turn initialization, project detection, setup offering."""

import hashlib
import importlib.util
import json
import os
import re
import shlex
import subprocess
from pathlib import Path
from typing import Any

from .classify import classify as classify_mod
from .output import emit
from .review import write_instructions
from .snapshot import fingerprint, snapshot
from .state import read_state, root_pointer, set_turn_lock, state_path, write_state

CONFIG = Path(".apex") / "verify.json"
SCOPE = Path(".apex") / "scope.json"
REVIEW = Path(".apex") / "review.json"
REVIEWER = "apex-reviewer"
PLAN = "PLAN.md"
MAX_ATTEMPTS = 3
OUTPUT_TAIL = 4000
STATE_DIR = Path(os.environ.get("APEX_HOOK_STATE_DIR")
                 or Path.home() / ".claude" / "apex-hooks" / "state")
GATED_SUBAGENTS = {"apex-coding"}
# How each host's main agent starts the reviewer; Codex starts custom agents by name.
SPAWN = {"claude": f"run the {REVIEWER} subagent (Agent tool, subagent_type \"{REVIEWER}\")",
         "codex": f"spawn the {REVIEWER} custom agent (agent_type \"{REVIEWER}\")"}


MAPS = ("AGENTS.md", "CLAUDE.md")
MAP_SECTION = re.compile(r"^## Where things are\n(.*?)(?=^## |\Z)", re.M | re.S)
MAP_PATH = re.compile(r"`([\w./*-]+/[\w./*-]*|[\w.*-]+\.\w+)`")
MAP_NAME = re.compile(r"`(\w+)\(\)`")



def find_root(cwd: str | Path) -> Path | None:
    path = Path(cwd).resolve()
    for candidate in (path, *path.parents):
        if any((candidate / name).is_file() for name in (CONFIG, SCOPE, REVIEW)):
            return candidate
    return None


def load_scope(root: Path) -> list[str] | None:
    """Allowed patterns, or None when the project has no scope file."""
    if not (root / SCOPE).is_file():
        return None
    try:
        allow = json.loads((root / SCOPE).read_text(encoding="utf-8")).get("allow")
    except (OSError, ValueError, AttributeError) as error:
        raise ValueError(f"{SCOPE} is unreadable: {error}") from error
    if not isinstance(allow, list) or not all(isinstance(item, str) and item for item in allow):
        raise ValueError(f'{SCOPE} needs "allow": a list of path patterns')
    # Reject patterns that could enable path traversal (e.g., "**", "*..*", "..")
    for pattern in allow:
        if "**" in pattern or ".." in pattern:
            raise ValueError(f'{SCOPE} pattern "{pattern}" is not allowed: "**" and ".." are forbidden')
    return allow


def load_config(root: Path) -> tuple[str, float]:
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


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, timeout=30, check=False)


def control_digest(root: Path) -> dict[str, str]:
    """Content hash of each Apex settings file; "<absent>" when it does not exist."""
    digest: dict[str, str] = {}
    for name in (CONFIG, SCOPE, REVIEW):
        try:
            digest[name.as_posix()] = hashlib.sha256((root / name).read_bytes()).hexdigest()
        except OSError:
            digest[name.as_posix()] = "<absent>"
    return digest


def tampered_controls(root: Path, state: dict[str, Any]) -> list[str]:
    """Settings files that differ from the turn's baseline; none when there was no baseline."""
    before = state.get("controls")
    if not isinstance(before, dict):
        return []
    now = control_digest(root)
    return sorted(name for name in now if before.get(name, "<absent>") != now[name])


def map_problems(root: Path) -> list[str]:
    """Paths and functions the project map names that no longer exist."""
    problems: list[str] = []
    for name in MAPS:
        try:
            text = (root / name).read_text(encoding="utf-8")
        except OSError:
            continue
        section = MAP_SECTION.search(text)
        if not section:
            continue
        for target in MAP_PATH.findall(section.group(1)):
            found = any(root.glob(target)) if "*" in target else (root / target).exists()
            if not found:
                problems.append(f"{name}: `{target}` does not exist")
        for function in MAP_NAME.findall(section.group(1)):
            search = _git(root, "grep", "--untracked", "-q", "-w", "-e", function, "--", ".",
                          *(f":!{m}" for m in MAPS))
            if search.returncode == 1:  # 0 is found; anything else means git could not search
                problems.append(f"{name}: `{function}()` is not found in the code")
    return problems


def nearby_controls(cwd: str | Path, depth: int = 2, limit: int = 5) -> list[str]:
    """`.apex` folders below cwd; they do nothing for a session opened in cwd."""
    found: list[str] = []
    frontier = [Path(cwd)]
    for _ in range(depth):
        next_frontier: list[Path] = []
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


PROJECT_TOOL = Path(__file__).resolve().parents[3] / "apex_project.py"


def offer_setup(cwd: Path) -> None:
    """Once per git project without `.apex`: ask the agent to offer setup; the user decides."""
    try:
        top = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=cwd, capture_output=True,
                             text=True, timeout=10, check=False)
    except (OSError, subprocess.SubprocessError):
        return
    if top.returncode != 0 or Path(top.stdout.strip()).resolve() != cwd.resolve() or (cwd / ".apex").exists():
        return
    marker = STATE_DIR / "offered" / hashlib.sha256(str(cwd.resolve()).encode()).hexdigest()[:24]
    if marker.exists():
        return
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(str(cwd.resolve()), encoding="utf-8")
    spec = importlib.util.spec_from_file_location("apex_project", PROJECT_TOOL)
    if spec is None or spec.loader is None:
        return
    tool = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(tool)
        proposal = tool.suggest(str(cwd))
    except (OSError, ValueError, SyntaxError):
        return
    command = ["python3", str(PROJECT_TOOL), "init", "--root", str(cwd)]
    command += [arg for pattern in proposal["allow"] for arg in ("--allow", pattern)]
    if proposal["verify"]:
        command += ["--verify", proposal["verify"]]
    emit({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": (
        "Apex: this git project has no Apex controls (verify, scope, review). After answering the user's "
        "message, offer them once, in one short paragraph, to enable the controls, showing this proposal "
        f"read from the project's build files ({proposal['kind']}):\n  scope: "
        f"{', '.join(proposal['allow']) or '(none found; ask which folders the work may change)'}\n  verify: "
        f"{proposal['verify'] or '(none found; ask for the command that builds or tests the project)'}\n"
        "Run the setup only after the user agrees, with their corrections:\n  "
        + " ".join(shlex.quote(part) for part in command)
        + "\nIf they decline, do not offer again.")}})
    if top.returncode != 0 or Path(top.stdout.strip()).resolve() != cwd.resolve() or (cwd / ".apex").exists():
        return
    marker = STATE_DIR / "offered" / hashlib.sha256(str(cwd.resolve()).encode()).hexdigest()[:24]
    if marker.exists():
        return
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(str(cwd.resolve()), encoding="utf-8")
    spec = importlib.util.spec_from_file_location("apex_project", PROJECT_TOOL)
    if spec is None or spec.loader is None:
        return
    tool = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(tool)
        proposal = tool.suggest(str(cwd))
    except (OSError, ValueError, SyntaxError):
        return
    command = ["python3", str(PROJECT_TOOL), "init", "--root", str(cwd)]
    command += [arg for pattern in proposal["allow"] for arg in ("--allow", pattern)]
    if proposal["verify"]:
        command += ["--verify", proposal["verify"]]
    emit({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": (
        "Apex: this git project has no Apex controls (verify, scope, review). After answering the user's "
        "message, offer them once, in one short paragraph, to enable the controls, showing this proposal "
        f"read from the project's build files ({proposal['kind']}):\n  scope: "
        f"{', '.join(proposal['allow']) or '(none found; ask which folders the work may change)'}\n  verify: "
        f"{proposal['verify'] or '(none found; ask for the command that builds or tests the project)'}\n"
        "Run the setup only after the user agrees, with their corrections:\n  "
        + " ".join(shlex.quote(part) for part in command)
        + "\nIf they decline, do not offer again.")}})


MAX_PROMPTS = 50
MAX_PROMPT_CHARS = 20000


def baseline(event: dict[str, Any]) -> None:
    set_turn_lock(event)
    cwd = event.get("cwd") or os.getcwd()
    prompt = event.get("prompt")
    if isinstance(prompt, str) and classify_mod(prompt) == "stop":
        return
    root = find_root(cwd)
    session_id = event.get("session_id", "")
    if root is None:
        root_pointer(session_id).unlink(missing_ok=True)
        misplaced = nearby_controls(cwd)
        if not misplaced:
            offer_setup(Path(cwd))
        # If there are misplaced controls, always warn (regardless of git status)
        # If no misplaced controls, only warn for git projects
        if not misplaced:
            try:
                top = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=cwd, capture_output=True,
                                     text=True, timeout=10, check=False)
                is_git = (top.returncode == 0 and Path(top.stdout.strip()).resolve() == Path(cwd).resolve())
            except (OSError, subprocess.SubprocessError):
                is_git = False
            if not is_git:
                return
        # Check if marker was set (offer already made this session)
        marker = STATE_DIR / "offered" / hashlib.sha256(str(Path(cwd).resolve()).encode()).hexdigest()[:24]
        if marker.exists():
            return
        # Emit warning
        where = ", ".join(f"{name}/.apex" for name in misplaced) if misplaced else f"(none in subdirectories of {cwd})"
        emit({"systemMessage": f"Apex controls are OFF for this session: they exist in {where}, "
                               f"but the session is opened in {cwd}. Nothing is verified, scoped or reviewed.",
              "hookSpecificOutput": {
                  "hookEventName": "UserPromptSubmit",
                  "additionalContext": (
                      "Apex warning: no Apex controls (verification, scope and review are NOT active). "
                      "Apex settings were "
                      f"found in {where}, but they only apply when the session's folder ({cwd}) or a parent "
                      "contains .apex. Tell the user before doing any work, and set the controls up at the "
                      "session folder as the apex-engineering skill describes.")}})
        return
    root_pointer(session_id).parent.mkdir(parents=True, exist_ok=True)
    root_pointer(session_id).write_text(str(root), encoding="utf-8")
    path = state_path(session_id, root)
    state = read_state(path)
    state.update({"baseline": fingerprint(root), "snapshot": snapshot(root), "controls": control_digest(root),
                  "failures": 0, "review_requests": 0})
    if isinstance(prompt, str) and prompt.strip():
        old_digest = state.get("prompt_digest")
        prompts = [*state.get("prompts", []), prompt[:MAX_PROMPT_CHARS]]
        if len(prompts) > MAX_PROMPTS:
            prompts = prompts[-MAX_PROMPTS:]
        state["prompts"] = prompts
        write_instructions(path, state["prompts"])
        state["prompt_digest"] = hashlib.sha256("\0".join(prompts).encode()).hexdigest()
        if old_digest != state["prompt_digest"]:
            state.update({"pending_review": None, "review_failed": None,
                          "review_failed_snapshot": None, "review_findings": ""})
    write_state(path, state)
