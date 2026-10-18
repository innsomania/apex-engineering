#!/usr/bin/env python3
"""Install the Apex skill for Codex and Claude Code without replacing existing instructions."""

import argparse
import json
import os
import shlex
import stat
import sys
import tempfile
from pathlib import Path
from typing import Any

SOURCE = Path(__file__).resolve().parent
START = b"\n<!-- apex-engineering:begin -->\n"
END = b"<!-- apex-engineering:end -->\n"


CODEX_TEXT = (
    "For software engineering tasks, use the apex-engineering skill at "
    "skills/apex-engineering/SKILL.md relative to this Codex home directory. "
    "Read its entry point and only the Engineering, Coding, Test, and Security "
    "references relevant to the task. Existing user and project scope, stop, "
    "Git, and environment restrictions continue to apply.\n"
)
CLAUDE_TEXT = (
    "For software engineering tasks, use the apex-engineering skill "
    "(skills/apex-engineering/SKILL.md in this Claude Code configuration directory). "
    "Read its entry point and only the Engineering, Coding, Test, and Security "
    "references relevant to the task. Existing user and project scope, stop, "
    "Git, and environment restrictions continue to apply.\n"
)
SPEC_SKILLS = SOURCE / "Claude" / "skills"


def vendored_skill_links() -> dict[str, Path]:
    """Third-party skills kept under Claude/skills/, so a global Apex install carries them.

    Each one keeps its upstream licence beside it. See Engineering/Integrations/VENDORED_SKILLS.md
    for what is taken, from where, and under which terms.
    """
    return {f"skills/{path.name}": path
            for path in sorted(SPEC_SKILLS.iterdir())
            if path.is_dir() and (path / "SKILL.md").is_file()}


HOSTS: dict[str, dict[str, Any]] = {
    "codex": {"env": "CODEX_HOME", "default": Path.home() / ".codex",
              "instructions": "AGENTS.md", "override": "AGENTS.override.md", "text": CODEX_TEXT,
              "links": {"skills/apex-engineering": SOURCE}},
    "claude": {"env": "CLAUDE_CONFIG_DIR", "default": Path.home() / ".claude",
               "instructions": "CLAUDE.md", "override": None, "text": CLAUDE_TEXT, "hooks": True,
               "links": {"skills/apex-engineering": SOURCE,
                         "agents/apex-coding.md": SOURCE / "Claude" / "agents" / "apex-coding.md",
                         "agents/apex-reviewer.md": SOURCE / "Claude" / "agents" / "apex-reviewer.md",
                         **vendored_skill_links()}},
}


HOOK_SCRIPT = SOURCE / "Claude" / "hooks" / "apex_verify_hook.py"
HOOKS: tuple[tuple[str, str | None, str, int], ...] = (("UserPromptSubmit", None, "baseline", 60),
         ("Stop", None, "stop", 900),
         ("SubagentStop", None, "stop", 900),
         ("PreToolUse", "Write|Edit|MultiEdit|NotebookEdit", "guard", 10),
         ("PostToolUse", "ExitPlanMode", "unlock", 10))


def _owned_hook(hook: object) -> bool:
    return isinstance(hook, dict) and HOOK_SCRIPT.name in str(hook.get("command", ""))


def merge_hooks(settings: dict[str, Any], install: bool) -> dict[str, Any]:
    """Return settings with Apex hooks removed, then added back when installing."""
    result: dict[str, Any] = json.loads(json.dumps(settings))
    hooks: dict[str, Any] = result.get("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError("settings.json 'hooks' is not an object; reconcile it manually.")
    for event in list(hooks):
        groups = []
        for group in hooks[event] if isinstance(hooks[event], list) else []:
            if isinstance(group, dict) and isinstance(group.get("hooks"), list):
                kept = [hook for hook in group["hooks"] if not _owned_hook(hook)]
                if not kept and group["hooks"]:
                    continue
                group = {**group, "hooks": kept}
            groups.append(group)
        if groups:
            hooks[event] = groups
        else:
            del hooks[event]
    if install:
        python = shlex.quote(sys.executable)
        for event, matcher, mode, timeout in HOOKS:
            group = {"hooks": [{"type": "command", "timeout": timeout,
                                "command": f"{python} {shlex.quote(str(HOOK_SCRIPT))} {mode}"}]}
            if matcher:
                group = {"matcher": matcher, **group}
            hooks.setdefault(event, []).append(group)
    if hooks:
        result["hooks"] = hooks
    else:
        result.pop("hooks", None)
    return result


def read_settings(path: Path) -> dict[str, Any]:
    if path.is_symlink():
        raise ValueError(f"{path.name} is a symlink; resolve its ownership before installation.")
    if not path.exists():
        return {}
    try:
        settings = json.loads(path.read_text(encoding="utf-8") or "{}")
    except ValueError as error:
        raise ValueError(f"{path} is not valid JSON; fix it before installation: {error}") from error
    if not isinstance(settings, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return settings


def block(host: str = "codex") -> bytes:
    text: str = HOSTS[host]["text"]
    return START + text.encode() + END


def split_owned(data: bytes, host: str = "codex") -> tuple[bytes, bool]:
    """Return bytes outside our block; reject ambiguous or modified ownership."""
    begin = b"<!-- apex-engineering:begin -->"
    end = b"<!-- apex-engineering:end -->"
    if begin not in data and end not in data:
        return data, False
    if data.count(begin) != 1 or data.count(end) != 1 or block(host) not in data:
        raise ValueError("Apex instruction block was modified; reconcile it manually.")
    return data.replace(block(host), b"", 1), True


def atomic_write(path: Path, data: bytes) -> None:
    """Publish complete contents only; preserve permissions and clean failed writes."""
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
    descriptor, name = tempfile.mkstemp(prefix=".apex-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def configure(home: str | Path, action: str, host: str = "codex") -> str:
    spec = HOSTS[host]
    home = Path(home).expanduser().absolute()
    instructions = home / spec["instructions"]
    if instructions.is_symlink():
        raise ValueError(f"{instructions.name} is a symlink; resolve its ownership before installation.")
    data = instructions.read_bytes() if instructions.exists() else b""
    outside, installed_block = split_owned(data, host)
    links: dict[Path, Path] = {home / name: target for name, target in spec["links"].items()}
    owned: dict[Path, bool] = {}
    for link, target in links.items():
        ours = link.is_symlink() and link.resolve() == target
        if os.path.lexists(link) and not ours:
            raise ValueError(f"Existing file is not owned by this checkout: {link}")
        owned[link] = ours
    settings_path = home / "settings.json"
    settings = read_settings(settings_path) if spec.get("hooks") else None
    hooks_present = settings is not None and merge_hooks(settings, False) != settings
    override = home / spec["override"] if spec["override"] else None
    override_active = override is not None and override.exists() and override.stat().st_size > 0
    if action == "status":
        state = "linked" if all(owned.values()) else "partial" if any(owned.values()) else "missing"
        return (f"host={host}, skill={state}, instructions={'present' if installed_block else 'missing'}"
                + (f", hooks={'present' if hooks_present else 'missing'}" if settings is not None else "")
                + (f", override={'present' if override_active else 'absent'}" if override else ""))
    if action == "install":
        if override is not None and override_active:
            raise ValueError(f"{override.name} may mask global instructions; reconcile it before installation.")
        missing = [target for target in links.values() if not target.exists()]
        if missing:
            raise ValueError(f"Source file is missing: {missing[0]}")
        created = []
        try:
            for link, target in links.items():
                if not owned[link]:
                    link.parent.mkdir(parents=True, exist_ok=True)
                    link.symlink_to(target, target_is_directory=target.is_dir())
                    created.append(link)
            if settings is not None and merge_hooks(settings, True) != settings:
                atomic_write(settings_path, (json.dumps(merge_hooks(settings, True), indent=2,
                                                        ensure_ascii=False) + "\n").encode())
            if not installed_block:
                atomic_write(instructions, data + block(host))
        except OSError:
            for link in created:
                link.unlink()
            raise
        return f"Installed Apex Engineering for {host}: {home}"
    if action == "uninstall":
        if hooks_present and settings is not None:
            atomic_write(settings_path, (json.dumps(merge_hooks(settings, False), indent=2,
                                                    ensure_ascii=False) + "\n").encode())
        if installed_block:
            atomic_write(instructions, outside)
        for link, ours in owned.items():
            if ours:
                link.unlink()
        return f"Removed Apex links and managed instructions for {host}; other content preserved."
    raise ValueError(f"Unknown action: {action}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("install", "status", "uninstall"))
    parser.add_argument("--host", choices=("codex", "claude", "all"), default="codex",
                        help="target host; 'all' configures Codex and Claude Code")
    parser.add_argument("--codex-home", type=Path, help="Codex user directory (default: CODEX_HOME or ~/.codex)")
    parser.add_argument("--claude-home", type=Path,
                        help="Claude Code user directory (default: CLAUDE_CONFIG_DIR or ~/.claude)")
    args = parser.parse_args()
    hosts: tuple[str, ...] = ("codex", "claude") if args.host == "all" else (args.host,)
    explicit = {"codex": args.codex_home, "claude": args.claude_home}
    status = 0
    for host in hosts:
        spec = HOSTS[host]
        home = explicit[host] or Path(os.environ.get(spec["env"]) or spec["default"])
        try:
            print(configure(home, args.action, host))
        except (OSError, ValueError) as error:
            print(f"Apex ({host}): {error}", file=sys.stderr)
            status = 1
    return status


if __name__ == "__main__":
    raise SystemExit(main())
