"""Focused fixture tests for MCP routing, safe discovery, and audit metadata."""

import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("apex_mcp_doctor", ROOT / "Engineering/mcp_doctor.py")
doctor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(doctor)


class FakeStdioParameters:
    def __init__(self, **kwargs):
        self.values = kwargs


class FakeClient:
    instances = []

    def __init__(self, target, *, read_timeout_seconds):
        self.target = target
        self.timeout = read_timeout_seconds
        self.calls = []
        self.instances.append(self)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    async def list_tools(self, *, cursor=None):
        self.calls.append(("list_tools", cursor))
        return SimpleNamespace(tools=[
            SimpleNamespace(name="browser_navigate"),
            SimpleNamespace(name="browser_snapshot"),
            SimpleNamespace(name="credentialValueMustNotAppear"),
        ], next_cursor=None)

    async def call_tool(self, *_args, **_kwargs):
        raise AssertionError("A probe must never call MCP tools")


SDK = (FakeClient, FakeStdioParameters)


class McpDoctorTests(unittest.TestCase):
    def setUp(self):
        FakeClient.instances.clear()

    def test_capability_routing_is_allowlisted_to_six_servers(self):
        self.assertEqual(len(doctor.REGISTRY), 6)
        expected = {
            "browser_testing": "playwright",
            "microsoft_documentation": "microsoft-learn",
            "openai_documentation": "openai-developer-docs",
            "library_documentation": "context7",
            "repository_context": "github-readonly",
            "document_conversion": "markitdown",
        }
        self.assertEqual({key: doctor.route_capability(key) for key in expected}, expected)
        with self.assertRaises(ValueError):
            doctor.route_capability("unregistered_capability")

    def test_sdk_probe_lists_tools_and_never_invokes_them(self):
        config = {
            "playwright": {
                "command": "fixture-server",
                "args": ["--read-only"],
                "env": {"TOKEN": "private-config-value"},
            },
        }
        report = doctor.probe_servers(config, ["playwright"], 3, sdk=SDK)[0]
        client = FakeClient.instances[0]
        self.assertEqual(report["status"], "available")
        self.assertEqual(report["discovered_tools"], ["browser_navigate", "browser_snapshot"])
        self.assertNotIn("credentialValueMustNotAppear", json.dumps(report))
        self.assertNotIn("private-config-value", json.dumps(report))
        self.assertEqual(client.calls, [("list_tools", None)])
        self.assertEqual(client.target.values["command"], "fixture-server")
        self.assertEqual(client.target.values["env"]["TOKEN"], "private-config-value")

    def test_probe_reports_disabled_unconfigured_unavailable_and_degraded(self):
        config = {
            "playwright": {"enabled": False, "env": {"TOKEN": "private-value"}},
            "microsoft-learn": {"url": "https://learn.microsoft.com/api/mcp"},
            "openai-developer-docs": {"command": "fixture-server"},
        }
        with patch.object(doctor, "_discover_tools", side_effect=[
                (None, "connection_failed"), ([], None)]):
            reports = doctor.probe_servers(
                config,
                ["playwright", "microsoft-learn", "openai-developer-docs", "context7"],
                sdk=SDK,
            )
        by_name = {item["server"]: item for item in reports}
        self.assertEqual(by_name["playwright"]["status"], "disabled")
        self.assertEqual(by_name["microsoft-learn"]["status"], "unavailable")
        self.assertEqual(by_name["openai-developer-docs"]["status"], "degraded")
        self.assertEqual(by_name["context7"]["status"], "unconfigured")
        serialized = json.dumps(reports)
        self.assertNotIn("private-value", serialized)

    def test_audit_links_task_hashes_results_and_redacts_failures(self):
        task_id = "APX-9cd506fec1d74b89b9b3cb4be89083da"
        secret = "result-secret-not-for-output"
        result = {"content": [{"type": "text", "text": secret}],
                  "structured_content": {"token": secret}}
        expected_digest = hashlib.sha256(json.dumps(
            result, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            allow_nan=False).encode("utf-8")).hexdigest()
        lines = [
            json.dumps({"type": "item.completed", "item": {
                "type": "mcp_tool_call", "server": "microsoft-learn",
                "tool": "microsoft_docs_search", "status": "completed",
                "arguments": {"query": secret}, "result": result,
            }}),
            json.dumps({"type": "item.completed", "item": {
                "type": "mcp_tool_call", "server": "github-readonly",
                "tool": "get_file_contents", "status": "failed",
                "error": secret, "result": None,
            }}),
            json.dumps({"type": "error", "message": secret}),
            json.dumps({"type": "item.completed", "item": {
                "type": "mcp_tool_call", "server": "unregistered", "tool": secret,
                "status": "completed", "result": secret,
            }}),
            json.dumps({"type": [], "item": {"type": "mcp_tool_call"}}),
            "not-json " + secret,
        ]
        audit = doctor.audit_jsonl(lines, task_id)
        serialized = json.dumps(audit)
        self.assertEqual(audit["task_id"], task_id)
        self.assertEqual(audit["events"][0]["result_sha256"], expected_digest)
        self.assertEqual(audit["events"][1]["status"], "failed")
        self.assertIsNone(audit["events"][1]["result_sha256"])
        self.assertEqual(audit["failed_event_count"], 2)
        self.assertEqual(audit["ignored_unregistered_count"], 1)
        self.assertEqual(audit["malformed_line_count"], 2)
        self.assertNotIn(secret, serialized)
        with self.assertRaises(ValueError):
            doctor.audit_jsonl([], "not-a-task")


if __name__ == "__main__":
    unittest.main()
