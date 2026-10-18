#!/usr/bin/env python3
"""Bounded MCP capability discovery and redacted Codex JSONL audit."""

import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import logging
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 and older; load_config fails closed below.
    tomllib = None
from urllib.parse import urlsplit

MCP_SDK_VERSION = "2.3.0"
MAX_TOOLS = 1_024
MAX_TOOL_PAGES = 16
MAX_AUDIT_LINES = 100_000
MAX_AUDIT_LINE_BYTES = 1_000_000
TASK_ID_RE = re.compile(r"^APX-[0-9a-f]{32}$")
TOOL_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")


@dataclass(frozen=True)
class ServerSpec:
    capability: str
    expected_tools: tuple[str, ...]


# Explicit allowlist of the six Engineering MCP servers.
REGISTRY = {
    "playwright": ServerSpec("browser_testing", ("browser_navigate", "browser_snapshot")),
    "microsoft-learn": ServerSpec("microsoft_documentation", ("microsoft_docs_search",)),
    "openai-developer-docs": ServerSpec(
        "openai_documentation", ("search_openai_docs", "fetch_openai_doc")),
    "context7": ServerSpec("library_documentation", ("resolve-library-id", "query-docs")),
    "github-readonly": ServerSpec("repository_context", ("get_file_contents",)),
    "markitdown": ServerSpec("document_conversion", ("convert_to_markdown",)),
}
ROUTES = {spec.capability: server for server, spec in REGISTRY.items()}


def route_capability(capability):
    """Return the allowlisted server for an Engineering capability."""
    try:
        return ROUTES[capability]
    except (KeyError, TypeError) as error:
        raise ValueError("Unknown MCP capability") from error


def _config_path():
    codex_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser()
    return codex_home / "config.toml"


def load_config(path=None):
    """Load server entries for internal use without exposing configuration values."""
    config_path = Path(path).expanduser() if path else _config_path()
    try:
        if not config_path.exists():
            return {}
        if config_path.is_symlink() or not config_path.is_file():
            raise ValueError("Configuration must be a regular file")
        if tomllib is None:
            raise ValueError("Reading it needs tomllib (Python 3.11 or newer)")
        with config_path.open("rb") as stream:
            config = tomllib.load(stream)
    except (OSError, ValueError) as error:
        raise ValueError("Codex MCP configuration is unavailable or invalid") from error
    servers = config.get("mcp_servers", {})
    if not isinstance(servers, dict):
        raise ValueError("Codex MCP configuration is unavailable or invalid")
    return servers


def _stdio_params(entry, params_type):
    command = entry.get("command")
    args = entry.get("args", [])
    env = entry.get("env", {}) or {}
    cwd = entry.get("cwd")
    if (not isinstance(command, str) or not command
            or not isinstance(args, list) or any(not isinstance(value, str) for value in args)
            or not isinstance(env, dict)
            or any(not isinstance(key, str) or not isinstance(value, str) for key, value in env.items())
            or (cwd is not None and not isinstance(cwd, str))):
        raise ValueError("Invalid STDIO configuration")

    child_env = dict(env)
    env_vars = entry.get("env_vars", [])
    if not isinstance(env_vars, list):
        raise ValueError("Invalid STDIO environment allowlist")
    for item in env_vars:
        if isinstance(item, str):
            name, source = item, "local"
        elif isinstance(item, dict):
            name, source = item.get("name"), item.get("source", "local")
        else:
            raise ValueError("Invalid STDIO environment allowlist")
        if not isinstance(name, str) or source != "local":
            raise ValueError("Unsupported STDIO environment source")
        if name in os.environ:
            child_env[name] = os.environ[name]
    return params_type(command=command, args=args, env=child_env or None, cwd=cwd)


def _remote_target(entry):
    url = entry.get("url")
    if not isinstance(url, str):
        raise ValueError("Invalid HTTP configuration")
    try:
        parts = urlsplit(url)
    except ValueError as error:
        raise ValueError("Invalid HTTP configuration") from error
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        raise ValueError("Invalid HTTP configuration")
    # These six configured HTTP services are public. Do not read or forward
    # credential material through a diagnostic probe.
    if any(entry.get(key) for key in (
            "bearer_token_env_var", "http_headers", "env_http_headers", "http_headers_helper")):
        raise ValueError("Authenticated HTTP probing is unsupported")
    return url


def _discover_tools(entry, transport, timeout=8.0, *, sdk=None):
    """Use the pinned MCP SDK to initialize a server and request tools/list only."""
    if sdk is None:
        try:
            logging.disable(logging.CRITICAL)
            if importlib.metadata.version("mcp") != MCP_SDK_VERSION:
                return None, "sdk_version_mismatch"
            from mcp import Client, StdioServerParameters  # noqa: PLC0415 - the SDK is optional
        except (ImportError, importlib.metadata.PackageNotFoundError):
            return None, "sdk_unavailable"
        sdk = (Client, StdioServerParameters)
    client_type, params_type = sdk

    try:
        if transport == "stdio":
            target = _stdio_params(entry, params_type)
        elif transport == "streamable_http":
            target = _remote_target(entry)
        else:
            return None, "invalid_configuration"
    except ValueError:
        return None, "invalid_configuration"

    async def list_names():
        async with client_type(target, read_timeout_seconds=timeout) as client:
            discovered = []
            cursor = None
            for _ in range(MAX_TOOL_PAGES):
                page = await client.list_tools(cursor=cursor)
                tools = getattr(page, "tools", None)
                if not isinstance(tools, list):
                    return None
                for tool in tools:
                    name = getattr(tool, "name", None)
                    if isinstance(name, str) and TOOL_NAME_RE.fullmatch(name):
                        discovered.append(name)
                        if len(discovered) >= MAX_TOOLS:
                            break
                cursor = getattr(page, "next_cursor", None)
                if not isinstance(cursor, str) or not cursor or len(discovered) >= MAX_TOOLS:
                    return sorted(set(discovered))
            return None

    try:
        names = asyncio.run(asyncio.wait_for(list_names(), timeout=timeout))
    except TimeoutError:
        return None, "timeout"
    except Exception:  # noqa: BLE001 - any probe failure is reported as one status
        # SDK and transport exceptions can contain URLs, paths, headers, or server data.
        return None, "connection_failed"
    return (names, None) if names is not None else (None, "protocol_error")


def probe_servers(config, names=None, timeout=8.0, *, sdk=None):
    """Probe registered servers. No MCP tool invocation is made."""
    selected = list(names) if names is not None else list(REGISTRY)
    reports = []
    for name in selected:
        if name not in REGISTRY:
            raise ValueError("Server is outside the MCP allowlist")
        spec = REGISTRY[name]
        entry = config.get(name)
        report = {
            "server": name,
            "capability": spec.capability,
            "expected_tools": list(spec.expected_tools),
            "status": "unconfigured",
            "transport": None,
            "discovered_tools": [],
            "missing_tools": [],
        }
        if entry is None:
            reports.append(report)
            continue
        if not isinstance(entry, dict):
            report.update(status="unavailable", reason="invalid_configuration")
            reports.append(report)
            continue
        if "enabled" in entry and not isinstance(entry["enabled"], bool):
            report.update(status="unavailable", reason="invalid_configuration")
            reports.append(report)
            continue
        if entry.get("enabled") is False:
            report.update(status="disabled", reason="disabled_by_config")
            reports.append(report)
            continue
        if ("url" in entry) == ("command" in entry):
            report.update(status="unavailable", reason="invalid_configuration")
            reports.append(report)
            continue
        transport = "streamable_http" if "url" in entry else "stdio"
        report["transport"] = transport
        discovered, reason = _discover_tools(entry, transport, timeout, sdk=sdk)
        if discovered is None:
            report.update(status="unavailable", reason=reason or "connection_failed")
        else:
            # Only names in the static registry may appear in doctor output.
            found = sorted(set(spec.expected_tools).intersection(discovered))
            missing = sorted(set(spec.expected_tools) - set(found))
            report.update(
                discovered_tools=found,
                missing_tools=missing,
                status="degraded" if missing else "available",
            )
            if missing:
                report["reason"] = "expected_tools_missing"
        reports.append(report)
    return reports


def _result_sha256(result):
    if result is None:
        return None
    serialized = json.dumps(result, ensure_ascii=False, sort_keys=True,
                            separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def audit_jsonl(lines, task_id):
    """Summarize registered MCP events; retain no arguments, results, or errors."""
    if not isinstance(task_id, str) or not TASK_ID_RE.fullmatch(task_id):
        raise ValueError("Task ID must be an Apex task identifier")
    events = []
    malformed = 0
    ignored_unregistered = 0
    failed = 0
    total_lines = 0
    truncated = False
    for raw in lines:
        total_lines += 1
        if total_lines > MAX_AUDIT_LINES:
            truncated = True
            break
        if isinstance(raw, bytes):
            if len(raw) > MAX_AUDIT_LINE_BYTES:
                malformed += 1
                continue
            try:
                raw = raw.decode("utf-8")
            except UnicodeDecodeError:
                malformed += 1
                continue
        if not isinstance(raw, str) or len(raw.encode("utf-8", errors="replace")) > MAX_AUDIT_LINE_BYTES:
            malformed += 1
            continue
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            malformed += 1
            continue
        if not isinstance(event, dict):
            malformed += 1
            continue
        event_type = event.get("type")
        if not isinstance(event_type, str):
            malformed += 1
            continue
        if event_type in {"error", "turn.failed"}:
            failed += 1
            continue
        if event_type not in {"item.started", "item.completed", "item.updated"}:
            continue
        item = event.get("item")
        if not isinstance(item, dict) or item.get("type") != "mcp_tool_call":
            continue
        server = item.get("server")
        if not isinstance(server, str) or server not in REGISTRY:
            ignored_unregistered += 1
            continue
        tool = item.get("tool")
        if not isinstance(tool, str) or not TOOL_NAME_RE.fullmatch(tool):
            malformed += 1
            continue
        status = item.get("status")
        if not isinstance(status, str) or status not in {
                "in_progress", "completed", "failed", "cancelled"}:
            status = "failed" if item.get("error") else {
                "item.started": "in_progress",
                "item.completed": "completed",
                "item.updated": "unknown",
            }[event_type]
        if status == "failed":
            failed += 1
        try:
            digest = _result_sha256(item.get("result"))
        except (TypeError, ValueError):
            malformed += 1
            continue
        events.append({
            "event": event_type,
            "server": server,
            "tool": tool,
            "status": status,
            "result_sha256": digest,
        })
    return {
        "schema_version": 1,
        "task_id": task_id,
        "events": events,
        "failed_event_count": failed,
        "malformed_line_count": malformed,
        "ignored_unregistered_count": ignored_unregistered,
        "truncated": truncated,
    }


def _write_json(value):
    json.dump(value, sys.stdout, ensure_ascii=False, sort_keys=True)
    sys.stdout.write("\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Probe allowlisted MCP capabilities and audit Codex JSONL")
    subparsers = parser.add_subparsers(dest="command", required=True)
    routes_parser = subparsers.add_parser("routes", help="List bounded capability routing")
    routes_parser.set_defaults(action="routes")
    probe_parser = subparsers.add_parser("probe", help="List tools without invoking MCP tools")
    probe_parser.add_argument("--server", action="append", choices=tuple(REGISTRY), dest="servers")
    probe_parser.add_argument("--timeout", type=float, default=8.0)
    probe_parser.add_argument("--config", help=argparse.SUPPRESS)
    probe_parser.set_defaults(action="probe")
    audit_parser = subparsers.add_parser("audit", help="Create redacted, task-linked JSONL audit metadata")
    audit_parser.add_argument("--task-id", required=True)
    audit_parser.add_argument("--input", default="-", help="JSONL file path, or - for stdin")
    audit_parser.set_defaults(action="audit")
    args = parser.parse_args(argv)

    try:
        if args.action == "routes":
            _write_json({"routes": ROUTES})
            return 0
        if args.action == "audit":
            if args.input == "-":
                result = audit_jsonl(sys.stdin, args.task_id)
            else:
                path = Path(args.input).expanduser()
                if path.is_symlink() or not path.is_file():
                    raise ValueError("Input must be a regular JSONL file")
                with path.open("r", encoding="utf-8", errors="replace") as stream:
                    result = audit_jsonl(stream, args.task_id)
            _write_json(result)
            return 0
        if not 0.1 <= args.timeout <= 60:
            raise ValueError("Timeout must be between 0.1 and 60 seconds")
        reports = probe_servers(load_config(args.config), args.servers, args.timeout)
        _write_json({"servers": reports})
        return 0 if all(item["status"] == "available" for item in reports) else 1
    except (OSError, ValueError):
        message = "Invalid task ID" if args.action == "audit" else "MCP diagnostic failed; details were redacted"
        print(message, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
