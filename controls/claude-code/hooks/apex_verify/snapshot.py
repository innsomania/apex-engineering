"""Filesystem snapshot and fingerprinting for change detection."""

import contextlib
import fnmatch
import hashlib
import os
import subprocess
from pathlib import Path

from .types import State


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, timeout=30, check=False)


def fingerprint(root: Path) -> str | None:
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
        if path.is_symlink():
            digest.update(b"symlink\0" + os.fsencode(os.readlink(path)))
        elif path.is_file():
            with contextlib.suppress(OSError):
                digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def snapshot(root: Path) -> State | None:
    """Hash dirty/untracked Git paths, or a bounded project walk outside Git."""
    files: dict[str, str] = {}
    if _git(root, "rev-parse", "--is-inside-work-tree").returncode != 0:
        ignored = {".git", ".hg", ".svn", ".venv", "venv", "node_modules", "__pycache__",
                   ".pytest_cache", ".mypy_cache", ".ruff_cache", ".next", "dist", "build"}
        for folder, dirs, names in os.walk(root, followlinks=False):
            base = Path(folder)
            links = [name for name in dirs if (base / name).is_symlink()]
            for name in links:
                path = base / name
                files[path.relative_to(root).as_posix()] = hashlib.sha256(
                    b"symlink\0" + os.fsencode(os.readlink(path))).hexdigest()
            dirs[:] = sorted(name for name in dirs if name not in ignored and name != ".apex"
                             and name not in links)
            for name in sorted(names):
                path = base / name
                relative = path.relative_to(root).as_posix()
                if relative == ".apex" or relative.startswith(".apex/"):
                    continue
                try:
                    if path.is_symlink():
                        value = b"symlink\0" + os.fsencode(os.readlink(path))
                    elif path.is_file():
                        value = path.read_bytes()
                    else:
                        continue
                    files[relative] = hashlib.sha256(value).hexdigest()
                except OSError:
                    files[relative] = "<unreadable>"
        return {"head": None, "files": files}
    head = _git(root, "rev-parse", "--verify", "-q", "HEAD").stdout.decode().strip()
    entries = _git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all").stdout.split(b"\0")
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if len(entry) < 4:
            continue
        name = os.fsdecode(entry[3:])
        if entry[:1] in (b"R", b"C"):
            original = os.fsdecode(entries[index]) if index < len(entries) else ""
            index += 1  # the original path of a rename or copy
            if original and entry[:1] == b"R":
                files[original] = "<absent>"  # a rename deletes the old path
        path = root / name
        try:
            if path.is_symlink():
                content = b"symlink\0" + os.fsencode(os.readlink(path))
            else:
                content = path.read_bytes() if path.is_file() else b"<absent>"
            files[name] = hashlib.sha256(content).hexdigest()
        except OSError:
            files[name] = "<unreadable>"
    return {"head": head, "files": files}


def turn_changes(root: Path, before: State | None) -> list[str]:
    """Paths whose content changed since the turn's baseline snapshot."""
    after = snapshot(root)
    if after is None:
        return []
    before = before or {"head": None, "files": {}}
    changed = {name for name in set(before["files"]) | set(after["files"])
               if before["files"].get(name) != after["files"].get(name)}
    if before.get("head") and before["head"] != after["head"]:
        committed = _git(root, "diff", "--name-only", "--no-renames", "-z",
                         before["head"], after["head"] or "HEAD").stdout
        changed |= {os.fsdecode(name) for name in committed.split(b"\0") if name}
    return sorted(changed)


def in_scope(relative: str, allow: list[str]) -> bool:
    if relative == "PLAN.md":
        return True  # the task list and daily log belong to every change
    for pattern in allow:
        if pattern.endswith("/"):
            if relative == pattern[:-1] or relative.startswith(pattern):
                return True
        elif fnmatch.fnmatchcase(relative, pattern):
            return True
    return False
