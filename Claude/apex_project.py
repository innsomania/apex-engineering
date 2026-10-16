#!/usr/bin/env python3
"""Turn on Apex controls for a project folder in one step.

The folder must be the one the Claude Code session is opened in: hooks look for `.apex`
in the session folder and its parents, never in subfolders. The tool makes that folder a
git repository (or requires it to be the root of an existing one), writes the three Apex
settings, adds ignore rules, records a baseline commit, and runs the verify command once
so a meaningless check is noticed immediately.

Example:
  python3 apex_project.py init --root "/path/to/project" \
      --allow store/src/ --allow store/public/ \
      --verify "cd store && npm run lint" --ignore row/ --ignore store/node_modules/
"""

import argparse
import json
from pathlib import Path
import subprocess
import sys

DEFAULT_IGNORES = (".DS_Store",)


def git(root, *args, check=True):
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=check)


def ensure_repository(root):
    probe = git(root, "rev-parse", "--show-toplevel", check=False)
    if probe.returncode == 0:
        top = Path(probe.stdout.strip()).resolve()
        if top != root:
            raise ValueError(f"{root} is inside the git repository {top}. Use {top} as --root, "
                             "or open the Claude Code session there.")
        return False
    git(root, "init", "-q")
    return True


def ensure_ignores(root, patterns):
    path = root / ".gitignore"
    existing = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    missing = [pattern for pattern in dict.fromkeys(patterns) if pattern not in existing]
    if missing:
        text = "\n".join(existing + missing) + "\n"
        path.write_text(text.lstrip("\n"), encoding="utf-8")
    return missing


def init(root, allow, verify, timeout, review, ignores):
    root = Path(root).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"{root} is not a folder")
    if (root / ".apex").exists():
        raise ValueError(f"{root / '.apex'} already exists; edit or remove it yourself first")
    if not allow:
        raise ValueError("give at least one --allow pattern (the files the work may change)")
    if not verify.strip():
        raise ValueError("--verify must run the project's real build or tests")
    created = ensure_repository(root)
    added = ensure_ignores(root, [*DEFAULT_IGNORES, *ignores])
    apex = root / ".apex"
    apex.mkdir()
    (apex / "scope.json").write_text(json.dumps({"allow": allow}, indent=2) + "\n", encoding="utf-8")
    (apex / "verify.json").write_text(json.dumps({"command": verify, "timeout": timeout}, indent=2) + "\n",
                                      encoding="utf-8")
    if review:
        (apex / "review.json").write_text("{}\n", encoding="utf-8")
    git(root, "add", "-A")
    identity = [] if git(root, "config", "user.email", check=False).stdout.strip() else \
        ["-c", "user.name=Apex", "-c", "user.email=apex@localhost"]
    git(root, *identity, "commit", "-q", "--allow-empty", "-m", "Apex baseline: controls enabled")
    check = subprocess.run(verify, shell=True, cwd=root, capture_output=True, text=True, timeout=timeout)
    return {"root": str(root), "git_initialized": created, "ignored": added, "allow": allow,
            "verify": verify, "verify_exit_code": check.returncode,
            "verify_output_tail": (check.stdout + check.stderr)[-1500:], "review": review}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    start = commands.add_parser("init", help="enable verify, scope and review for a project folder")
    start.add_argument("--root", required=True, help="the folder the Claude Code session is opened in")
    start.add_argument("--allow", action="append", default=[], help="file pattern the work may change; repeat")
    start.add_argument("--verify", required=True, help="command that builds or tests the project")
    start.add_argument("--timeout", type=int, default=600)
    start.add_argument("--no-review", dest="review", action="store_false")
    start.add_argument("--ignore", action="append", default=[], help=".gitignore pattern to add; repeat")
    args = parser.parse_args(argv)
    try:
        result = init(args.root, args.allow, args.verify, args.timeout, args.review, args.ignore)
    except (ValueError, OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        detail = getattr(error, "stderr", "") or ""
        print(f"Apex project setup failed: {error} {detail}".strip(), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["verify_exit_code"] != 0:
        print("Warning: the verify command fails right now; the next turn that changes files must fix it.",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
