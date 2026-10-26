#!/usr/bin/env python3
"""Start a host-native task with explicit Apex engineering guidance."""

import argparse
import json
import os
from pathlib import Path

SOURCE = Path(__file__).resolve().parent


def task_prompt(task: str) -> str:
    return (
        f"Use Apex Engineering: read {SOURCE / 'SKILL.md'} first, then only references "
        "needed for this task. This is a reference directory, not the target project. "
        "Use the session working directory as the target unless the user specifies another. "
        "Keep searches and changes within that target; do not search parent folders. "
        "Preserve all user and project rules. Other skills remain "
        "available when explicitly requested or needed, but do not load another general "
        "workflow for the same task.\n\nUser task:\n" + task
    )


def codex_command(task: str, arguments: list[str]) -> list[str]:
    # A per-session setting: no global config, model, permission, or hook changes.
    return ["codex", "-c", "skills.include_instructions=false", *arguments, task_prompt(task)]


def host_command(host: str, task: str, arguments: list[str]) -> list[str]:
    if host == "codex":
        return codex_command(task, arguments)
    if host == "claude":
        return ["claude", *arguments, "--", task_prompt(task)]
    if host == "opencode":
        return ["opencode", "run", *arguments, task_prompt(task)]
    raise ValueError(f"Unsupported host: {host}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", choices=("codex", "claude", "opencode", "portable"), default="codex")
    parser.add_argument("--task", required=True, help="user task, passed as one literal argument")
    parser.add_argument("--dry-run", action="store_true", help="print argv without starting a model")
    parser.add_argument("host_args", nargs=argparse.REMAINDER,
                        help="Host arguments after --; run from the target project directory")
    args = parser.parse_args()
    arguments = args.host_args[1:] if args.host_args[:1] == ["--"] else args.host_args
    if args.host == "portable":
        if arguments:
            parser.error("portable mode prints a prompt and does not accept host arguments")
        print(task_prompt(args.task))
        return
    command = host_command(args.host, args.task, arguments)
    if args.dry_run:
        print(json.dumps(command, ensure_ascii=False, indent=2))
        return
    os.environ["PWD"] = str(Path.cwd())
    os.execvp(command[0], command)


if __name__ == "__main__":
    main()
