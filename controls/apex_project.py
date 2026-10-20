#!/usr/bin/env python3
"""Turn on Apex controls for a project folder in one step.

The folder must be the one the Claude Code session is opened in: hooks look for `.apex`
in the session folder and its parents, never in subfolders. The tool makes that folder a
git repository (or requires it to be the root of an existing one), writes the three Apex
settings, adds ignore rules, records a baseline commit, and runs the verify command once
so a meaningless check is noticed immediately.

Only the project's own rules live in `.apex`; the hooks, reviewer and guides stay in this
checkout. `.apex/apex.json` points back here and records the format of the rules, so
`upgrade` can bring every project forward when the format changes.

Commands:
  init     enable verify, scope and review for a project folder
  suggest  propose a verify command and scope from the project's build files (writes nothing)
  list     find the projects that use Apex and show their format
  upgrade  add or update `.apex/apex.json`; the rules themselves are never changed

Example:
  python3 apex_project.py init --root "/path/to/project" \
      --allow store/src/ --allow store/public/ \
      --verify "cd store && npm run lint" --ignore row/ --ignore store/node_modules/
"""

import argparse
import json
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

DEFAULT_IGNORES = (".DS_Store",)
SOURCE = Path(__file__).resolve().parents[1]
MANIFEST = "apex.json"
FORMAT = 1  # 0 is a project from before the manifest: the same three rule files, no apex.json
RULES = ("verify.json", "scope.json", "review.json")
# Folders that hold a project's own work; build output and dependencies are never in the scope.
SOURCE_DIRS = ("src", "app", "apps", "lib", "packages", "backend", "frontend", "server", "client",
               "Sources", "Tests", "tests", "test", "spec", "docs", "public", "pages", "components")
SKIP_DIRS = {"node_modules", ".git", "build", "dist", "bin", "obj", ".venv", "venv", "Pods", ".next",
             ".dart_tool", "DerivedData", "target", "Library"}
NPM_PLACEHOLDER = "no test specified"


def git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=check)


def ensure_repository(root: Path) -> bool:
    probe = git(root, "rev-parse", "--show-toplevel", check=False)
    if probe.returncode == 0:
        top = Path(probe.stdout.strip()).resolve()
        if top != root:
            raise ValueError(f"{root} is inside the git repository {top}. Use {top} as --root, "
                             "or open the Claude Code session there.")
        return False
    git(root, "init", "-q")
    return True


def ensure_ignores(root: Path, patterns: Sequence[str]) -> list[str]:
    path = root / ".gitignore"
    existing = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    missing = [pattern for pattern in dict.fromkeys(patterns) if pattern not in existing]
    if missing:
        text = "\n".join(existing + missing) + "\n"
        path.write_text(text.lstrip("\n"), encoding="utf-8")
    return missing


def init(root: str, allow: Sequence[str], verify: str, timeout: int, review: bool,
         ignores: Sequence[str]) -> dict[str, Any]:
    project = Path(root).expanduser().resolve()
    if not project.is_dir():
        raise ValueError(f"{project} is not a folder")
    if (project / ".apex").exists():
        raise ValueError(f"{project / '.apex'} already exists; edit or remove it yourself first")
    if not allow:
        raise ValueError("give at least one --allow pattern (the files the work may change)")
    if not verify.strip():
        raise ValueError("--verify must run the project's real build or tests")
    created = ensure_repository(project)
    added = ensure_ignores(project, [*DEFAULT_IGNORES, *ignores])
    apex = project / ".apex"
    apex.mkdir()
    (apex / "scope.json").write_text(json.dumps({"allow": allow}, indent=2) + "\n", encoding="utf-8")
    (apex / "verify.json").write_text(json.dumps({"command": verify, "timeout": timeout}, indent=2) + "\n",
                                      encoding="utf-8")
    if review:
        (apex / "review.json").write_text("{}\n", encoding="utf-8")
    write_manifest(project)
    git(project, "add", "-A")
    identity = [] if git(project, "config", "user.email", check=False).stdout.strip() else \
        ["-c", "user.name=Apex", "-c", "user.email=apex@localhost"]
    git(project, *identity, "commit", "-q", "--allow-empty", "-m", "Apex baseline: controls enabled")
    # The verify command is the project's own shell command, supplied by the user.
    check = subprocess.run(verify, shell=True, cwd=project, capture_output=True, text=True,  # noqa: S602
                           timeout=timeout, check=False)
    return {"root": str(project), "git_initialized": created, "ignored": added, "allow": allow,
            "verify": verify, "verify_exit_code": check.returncode,
            "verify_output_tail": (check.stdout + check.stderr)[-1500:], "review": review}


def write_manifest(project: Path) -> None:
    manifest = {"source": str(SOURCE), "format": FORMAT}
    (project / ".apex" / MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def read_format(apex: Path) -> int:
    """The rule format of a `.apex` folder: 0 without a manifest; ValueError when unreadable."""
    path = apex / MANIFEST
    if not path.exists():
        return 0
    try:
        version = json.loads(path.read_text(encoding="utf-8")).get("format")
    except (OSError, ValueError, AttributeError) as error:
        raise ValueError(f"{path} is not a valid Apex manifest: {error}") from error
    if not isinstance(version, int) or version < 1:
        raise ValueError(f"{path} has no valid format number")
    return version


def describe(apex: Path) -> dict[str, Any]:
    entry: dict[str, Any] = {"root": str(apex.parent), "rules": [name for name in RULES if (apex / name).is_file()]}
    try:
        entry["format"] = read_format(apex)
        entry["current"] = entry["format"] == FORMAT
    except ValueError as error:
        entry.update({"format": None, "current": False, "error": str(error)})
    return entry


def find_projects(bases: Sequence[str], depth: int = 4) -> list[dict[str, Any]]:
    """Every `.apex` folder under the bases, skipping dependency and build folders."""
    found: list[dict[str, Any]] = []
    frontier = [Path(base).expanduser().resolve() for base in bases]
    for _ in range(depth + 1):
        next_frontier: list[Path] = []
        for folder in frontier:
            if (folder / ".apex").is_dir():
                found.append(describe(folder / ".apex"))
            try:
                children = sorted(folder.iterdir())
            except OSError:
                continue
            next_frontier += [child for child in children if child.is_dir() and not child.is_symlink()
                              and child.name not in SKIP_DIRS and not child.name.startswith(".")]
        frontier = next_frontier
    return found


def upgrade(root: str) -> dict[str, Any]:
    """Bring one project's `.apex` to the current format without touching its rules."""
    apex = Path(root).expanduser().resolve() / ".apex"
    if not apex.is_dir():
        raise ValueError(f"{apex} does not exist; use init")
    before = read_format(apex)
    if before > FORMAT:
        raise ValueError(f"{apex} uses format {before}, newer than this checkout ({FORMAT}); update Apex")
    rules = {name: (apex / name).read_bytes() for name in RULES if (apex / name).is_file()}
    write_manifest(apex.parent)
    if {name: (apex / name).read_bytes() for name in RULES if (apex / name).is_file()} != rules:
        raise RuntimeError("upgrade changed a rule file")  # cannot happen; the rules are only read
    return {"root": str(apex.parent), "from": before, "to": FORMAT, "rules": sorted(rules)}


def npm_command(root: Path) -> str | None:
    try:
        scripts = json.loads((root / "package.json").read_text(encoding="utf-8")).get("scripts") or {}
    except (OSError, ValueError, AttributeError):
        return None
    runner = "pnpm" if (root / "pnpm-lock.yaml").exists() else "yarn" if (root / "yarn.lock").exists() else "npm"
    steps = [f"{runner} run {name}" for name in ("lint", "typecheck", "build", "test")
             if isinstance(scripts.get(name), str) and NPM_PLACEHOLDER not in scripts[name]]
    return " && ".join(steps) or None


def suggest(root: str) -> dict[str, Any]:
    """A verify command and scope read from the project's build files, for the user to confirm."""
    project = Path(root).expanduser().resolve()
    names = {child.name for child in project.iterdir()} if project.is_dir() else set()
    pubspec = ((project / "pubspec.yaml").read_text(encoding="utf-8", errors="replace")
               if "pubspec.yaml" in names else "")
    flutter = "flutter" if "flutter:" in pubspec else "dart"
    # A project can mix stacks (a .NET backend beside an npm workspace); every one found is checked.
    detected = (
        ("dotnet", "dotnet build && dotnet test" if any(n.endswith((".sln", ".slnx", ".csproj")) for n in names)
         else None),
        ("node", npm_command(project) if "package.json" in names else None),
        (flutter, f"{flutter} analyze && {flutter} test" if pubspec else None),
        ("swift", "swift build && swift test" if "Package.swift" in names else None),
        ("cmake", "cmake -S . -B build && cmake --build build && ctest --test-dir build"
         if "CMakeLists.txt" in names else None),
        ("python", "python3 -m pytest" if names & {"pyproject.toml", "setup.py"} else None),
    )
    found = [(kind, command) for kind, command in detected if command]
    verify = " && ".join(command for _kind, command in found) or None
    kind = "+".join(kind for kind, _command in found) or "unknown"
    # Names as they are on disk: on a case-insensitive disk "tests" would also match "Tests".
    allow = [f"{name}/" for name in SOURCE_DIRS if name in names and (project / name).is_dir()]
    return {"root": str(project), "kind": kind, "verify": verify, "allow": allow}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    start = commands.add_parser("init", help="enable verify, scope and review for a project folder")
    start.add_argument("--root", required=True, help="the folder the Claude Code session is opened in")
    start.add_argument("--allow", action="append", default=[], help="file pattern the work may change; repeat")
    start.add_argument("--verify", required=True, help="command that builds or tests the project")
    start.add_argument("--timeout", type=int, default=600)
    start.add_argument("--no-review", dest="review", action="store_false")
    start.add_argument("--ignore", action="append", default=[], help=".gitignore pattern to add; repeat")
    commands.add_parser("suggest", help="propose verify and scope for a project").add_argument("--root", required=True)
    finder = commands.add_parser("list", help="find projects that use Apex")
    finder.add_argument("bases", nargs="*", default=[str(Path.home() / "Desktop")])
    commands.add_parser("upgrade", help="bring a project's .apex to the current format").add_argument(
        "--root", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "suggest":
            print(json.dumps(suggest(args.root), ensure_ascii=False, indent=2))
            return 0
        if args.command == "list":
            projects = find_projects(args.bases)
            print(json.dumps(projects, ensure_ascii=False, indent=2))
            return 0 if all(entry["current"] for entry in projects) else 3
        if args.command == "upgrade":
            print(json.dumps(upgrade(args.root), ensure_ascii=False, indent=2))
            return 0
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
