#!/usr/bin/env python3
"""Run one approved task through a Codex worker and write what it did.

The planner (for example Claude Code on Opus) keeps the plan and the checks; the
worker only implements the task it is given. Each role picks a model:

  heavy    gpt-6.1-sol, medium effort: complex, multi-file, or hard-to-find work
  focused  gpt-6-luna, high effort: one clear feature, fix, or test
  ui       gpt-6.1-terra, medium effort: open the app and check screens, buttons, layouts

    python3 apex_worker.py --project . --role heavy --task-file task.md --out result.json

The worker runs `codex exec` in the project with the workspace-write sandbox, so
it can change only the project. The result file holds the worker's final report,
the files that changed, the token usage, and the exit status. The planner must
still read the diff and run the acceptance check itself.
"""

import argparse
import json
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


def changed_files(project: Path) -> list[str]:
    status = subprocess.run(["git", "status", "--porcelain", "-uall"], cwd=project,
                            capture_output=True, text=True, check=False).stdout
    return sorted(line[3:] for line in status.splitlines() if line.strip())


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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--role", choices=sorted(ROLES), required=True)
    parser.add_argument("--task-file", type=Path, required=True, help="the task, its files and its check")
    parser.add_argument("--out", type=Path, required=True, help="where to write the result JSON")
    parser.add_argument("--model", help="override the role's model")
    parser.add_argument("--effort", help="override the role's reasoning effort")
    parser.add_argument("--timeout", type=float, default=1800)
    parser.add_argument("--dry-run", action="store_true", help="print the command without starting Codex")
    args = parser.parse_args()
    project = args.project.resolve()
    model, effort = ROLES[args.role]
    model, effort = args.model or model, args.effort or effort
    command = worker_command(project, model, effort, args.task_file.read_text(encoding="utf-8"))
    if args.dry_run:
        print(json.dumps(command, ensure_ascii=False, indent=2))
        return 0
    before = set(changed_files(project))
    start = time.monotonic()
    try:
        run = subprocess.run(command, cwd=project, capture_output=True, text=True,
                             stdin=subprocess.DEVNULL, timeout=args.timeout, check=False)
        stream, code = run.stdout, run.returncode
    except subprocess.TimeoutExpired as error:
        stream, code = error.stdout.decode() if isinstance(error.stdout, bytes) else (error.stdout or ""), -1
    result = {"role": args.role, "model": model, "effort": effort, "exit": code,
              "seconds": round(time.monotonic() - start),
              "changed": sorted(set(changed_files(project)) - before), **summarize(stream)}
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("role", "model", "exit", "seconds", "changed")}, ensure_ascii=False))
    return 0 if code == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
