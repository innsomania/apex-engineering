"""Acceptance tests for the external execution guard (Engineering/Integrations/EXECUTION_GUARD.md).

The guard is third-party software that Apex does not install. These tests skip when it is absent
and verify its actual decisions when it is present. Every command below is an analyzer input
string; none of them is executed by a shell.
"""

import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path

SAFE = "git status"
MUST_BLOCK = {
    "rm -rf /": "a destructive delete at the filesystem root",
    "git reset --hard HEAD~3": "discarding uncommitted work",
    "cat ~/.ssh/id_rsa": "reading a private key",
    "echo $(rm -rf ~/Desktop)": "a destructive delete hidden in a command substitution",
}


def locate_guard():
    """The installed guard's invocation, or None. CC_SAFETY_NET_BIN overrides discovery."""
    override = os.environ.get("CC_SAFETY_NET_BIN")
    if override:
        return ["node", override] if override.endswith((".js", ".mjs")) else [override]
    on_path = shutil.which("cc-safety-net")
    if on_path:
        return [on_path]
    node = shutil.which("node")
    if not node:
        return None
    for root in (Path.home() / ".claude" / "plugins", Path.home() / ".claude"):
        for script in sorted(root.glob("**/dist/bin/cc-safety-net.js")):
            return [node, str(script)]
    return None


GUARD = locate_guard()


@unittest.skipIf(GUARD is None, "cc-safety-net is not installed; see Integrations/EXECUTION_GUARD.md")
class ExecutionGuardTests(unittest.TestCase):
    def decide(self, command):
        """The guard's permissionDecision for a Bash command, or None when it emits no decision."""
        payload = {"hook_event_name": "PreToolUse", "tool_name": "Bash",
                   "tool_input": {"command": command}, "cwd": "/tmp"}
        result = subprocess.run([*GUARD, "hook", "--coding-cli"], input=json.dumps(payload),
                                capture_output=True, text=True, timeout=60)
        if not result.stdout.strip():
            return None
        try:
            return json.loads(result.stdout).get("hookSpecificOutput", {}).get("permissionDecision")
        except ValueError:
            return None

    def test_destructive_commands_are_denied(self):
        for command, why in MUST_BLOCK.items():
            self.assertEqual(self.decide(command), "deny", f"{command!r} is {why}")

    def test_a_read_only_command_is_not_denied(self):
        self.assertNotEqual(self.decide(SAFE), "deny")


if __name__ == "__main__":
    unittest.main()
