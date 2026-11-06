#!/usr/bin/env python3
"""Run one approved task through a worker and write what it did.

The planner (Claude Code on Opus 5.5, low effort) keeps the plan and the checks and
never edits code; the worker only implements the task it is given.

By default (`--engine claude`) every role runs on Claude Code (`claude -p`) with
Sonnet 5.5 at medium effort, including `light`. Opus is never a worker. Codex runs
only with an explicit `--engine codex` (no fallback) or `--engine auto` (Codex, then
Claude if Codex's usage limit is hit). With a Codex engine each role picks a model:

  heavy    gpt-6.1-sol, medium effort: complex, multi-file, or hard-to-find work
  focused  gpt-6-luna, high effort: one clear feature, fix, or test
  ui       gpt-6.1-terra, medium effort: open the app and check screens, buttons, layouts
  light    gpt-6-luna, high effort: low-level work (rename, small text fix, config line)

With `--engine auto`, when Codex reports that its usage limit is hit, the same task
runs again through Claude Code on Sonnet 5.5 medium. Any other Codex failure is
reported as is; it does not switch engines.

    python3 apex_worker.py --project . --role heavy --task-file task.md --out result.json

The Codex worker runs `codex exec` in the project with the workspace-write sandbox,
so it can change only the project; the Claude worker runs in the project in auto
permission mode under the installed Apex hooks. The result file holds the engine,
why it fell back (if it did), the worker's final report, the files that changed,
the token usage, and the exit status. The planner must
still read the diff and run the acceptance check itself.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

SOURCE = Path(__file__).resolve().parents[1]
ROLES: dict[str, tuple[str, str]] = {
    "heavy": ("gpt-6.1-sol", "medium"),
    "focused": ("gpt-6-luna", "high"),
    "ui": ("gpt-6.1-terra", "medium"),
    "light": ("gpt-6-luna", "high"),
}
CLAUDE_ROLES: dict[str, tuple[str, str]] = {
    "heavy": ("claude-sonnet-5-5", "medium"),
    "focused": ("claude-sonnet-5-5", "medium"),
    "ui": ("claude-sonnet-5-5", "medium"),
    "light": ("claude-sonnet-5-5", "medium"),
}


def worker_prompt(task: str) -> str:
    return (
        f"You are the Apex worker for one approved task. Read {SOURCE / 'SKILL.md'} only as needed; "
        "it is a reference directory, not the project. The plan is already approved by the user: "
        "do not ask for plan approval, do not delegate to another agent, and do not plan other work. "
        "Implement exactly this task inside the current project, run its check, and finish with a short "
        "report: files changed, the check you ran and its result, and anything left undone.\n\nTask:\n" + task
    )


def worker_command(project: Path, model: str, effort: str, task: str) -> list[str]:
    return ["codex", "exec", "--json", "-s", "workspace-write", "--skip-git-repo-check",
            "-C", str(project), "-m", model, "-c", f"model_reasoning_effort={effort}",
            "-c", "skills.include_instructions=false", worker_prompt(task)]


def claude_command(model: str, effort: str, task: str) -> list[str]:
    return ["claude", "-p", "--model", model, "--effort", effort, "--permission-mode", "auto",
            "--output-format", "json", worker_prompt(task)]


def usage_limited(events: str) -> bool:
    """True when a `codex exec --json` stream failed because the account's usage limit is hit."""
    for line in events.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict) or event.get("type") not in ("error", "turn.failed"):
            continue
        error = event.get("error")
        message = event.get("message") or (error.get("message") if isinstance(error, dict) else "")
        if "usage limit" in str(message).lower():
            return True
    return False


def changed_files(project: Path) -> dict[str, str]:
    """Content hashes for changed Git paths, including untracked files and symlinks."""
    status = subprocess.run(["git", "status", "--porcelain=v1", "-z", "-uall"], cwd=project,
                            capture_output=True, check=False).stdout.split(b"\0")
    paths: set[bytes] = set()
    index = 0
    while index < len(status):
        entry = status[index]
        index += 1
        if len(entry) < 4:
            continue
        paths.add(entry[3:])
        if (entry[:2].strip().find(b"R") >= 0 or entry[:2].strip().find(b"C") >= 0) and index < len(status):
            paths.add(status[index])
            index += 1
    result: dict[str, str] = {}
    for encoded in paths:
        name = os.fsdecode(encoded)
        path = project / name
        try:
            content = b"symlink\0" + os.fsencode(os.readlink(path)) if path.is_symlink() else path.read_bytes()
            result[name] = hashlib.sha256(content).hexdigest()
        except (FileNotFoundError, IsADirectoryError):
            result[name] = "<absent>"
        except OSError:
            result[name] = "<unreadable>"
    return result


def summarize(events: str) -> dict[str, Any]:
    """Final report and token usage from a `codex exec --json` event stream."""
    report = ""
    usage: dict[str, Any] | None = None
    for line in events.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        item = event.get("item") or {}
        if event.get("type") == "item.completed" and item.get("type") == "agent_message":
            report = str(item.get("text", ""))
        if event.get("type") == "turn.completed":
            usage = event.get("usage")
    return {"report": report, "usage": usage}


def summarize_claude(output: str) -> dict[str, Any]:
    """Final report and token usage from `claude -p --output-format json`."""
    try:
        result = json.loads(output)
    except ValueError:
        return {"report": output.strip()[-2000:], "usage": None}
    if not isinstance(result, dict):
        return {"report": "", "usage": None}
    return {"report": str(result.get("result") or ""), "usage": result.get("usage")}


def run(command: list[str], project: Path, timeout: float) -> tuple[str, str, int]:
    try:
        done = subprocess.run(command, cwd=project, capture_output=True, text=True,
                              stdin=subprocess.DEVNULL, timeout=timeout, check=False)
        return done.stdout, done.stderr, done.returncode
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout.decode(errors="replace") if isinstance(error.stdout, bytes) else (error.stdout or "")
        stderr = error.stderr.decode(errors="replace") if isinstance(error.stderr, bytes) else (error.stderr or "")
        return stdout, stderr or f"Worker timed out after {timeout:g} seconds.", -1
    except OSError as error:
        return "", str(error), -1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--role", choices=sorted(ROLES), required=True)
    parser.add_argument("--task-file", type=Path, required=True, help="the task, its files and its check")
    parser.add_argument("--out", type=Path, required=True, help="where to write the result JSON")
    parser.add_argument("--model", help="override the role's model")
    parser.add_argument("--effort", help="override the role's reasoning effort")
    parser.add_argument("--timeout", type=float, default=1800)
    parser.add_argument("--engine", choices=("auto", "codex", "claude"), default="claude",
                        help="claude: Sonnet 5.5 medium for every role, no Codex (default); "
                             "codex: Codex only, no fallback; "
                             "auto: Codex, then Claude if Codex's usage limit is hit. Opus is never a worker")
    parser.add_argument("--dry-run", action="store_true", help="print the first command without starting a model")
    args = parser.parse_args()
    project = args.project.resolve()
    task = args.task_file.read_text(encoding="utf-8")
    engine = "claude" if args.engine == "claude" else "codex"
    # --model and --effort apply to the engine asked for; a fallback uses the Claude role defaults.
    model, effort = (CLAUDE_ROLES if engine == "claude" else ROLES)[args.role]
    model, effort = args.model or model, args.effort or effort
    command = (claude_command(model, effort, task) if engine == "claude"
               else worker_command(project, model, effort, task))
    if args.dry_run:
        print(json.dumps(command, ensure_ascii=False, indent=2))
        return 0
    before = changed_files(project)
    start = time.monotonic()
    stream, stderr, code = run(command, project, args.timeout)
    fallback = None
    if engine == "codex" and args.engine == "auto" and code != 0 and usage_limited(stream + "\n" + stderr):
        fallback = "codex usage limit"
        codex_error = stderr or stream[-2000:]
        engine, (model, effort) = "claude", CLAUDE_ROLES[args.role]
        stream, stderr, code = run(claude_command(model, effort, task), project, args.timeout)
        if codex_error:
            stderr = f"Codex fallback reason: {codex_error}\n{stderr}".rstrip()
    summary = summarize_claude(stream) if engine == "claude" else summarize(stream)
    if code != 0 and not summary["report"].strip():
        summary["report"] = (stderr or stream)[-2000:]
    result = {"role": args.role, "engine": engine, "model": model, "effort": effort, "fallback": fallback,
              "exit": code, "seconds": round(time.monotonic() - start), "changed": sorted(
                  name for name, digest in changed_files(project).items() if before.get(name) != digest),
              "stderr": stderr, **summary}
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("role", "engine", "model", "fallback", "exit", "seconds", "changed")},
                     ensure_ascii=False))
    return 0 if code == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
