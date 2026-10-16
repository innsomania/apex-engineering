"""Verification hook checks run against disposable git projects only."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HOOK = Path(__file__).resolve().parents[1] / "Claude" / "hooks" / "apex_verify_hook.py"


class VerifyHookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.project = base / "project"
        self.project.mkdir()
        self.state = base / "state"
        self.runs = base / "runs.log"
        # The check passes only when value.txt says "ok" and logs each run outside the repo.
        (self.project / "check.py").write_text(
            "import sys, pathlib\n"
            f"open({str(self.runs)!r}, 'a').write('run\\n')\n"
            "ok = pathlib.Path('value.txt').read_text().strip() == 'ok'\n"
            "print('value is', 'ok' if ok else 'wrong')\n"
            "sys.exit(0 if ok else 3)\n")
        (self.project / "value.txt").write_text("ok\n")
        self.configure()

    def configure(self):
        (self.project / ".apex").mkdir(exist_ok=True)
        (self.project / ".apex" / "verify.json").write_text(
            json.dumps({"command": f"{sys.executable} check.py", "timeout": 60}))

    def git_init(self):
        for args in (["init", "-q"], ["add", "-A"],
                     ["-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qm", "base"]):
            subprocess.run(["git", *args], cwd=self.project, check=True)

    def hook(self, mode, **event):
        event.setdefault("session_id", "s1")
        event.setdefault("cwd", str(self.project))
        result = subprocess.run([sys.executable, str(HOOK), mode], input=json.dumps(event),
                                capture_output=True, text=True, timeout=60,
                                env={**os.environ, "APEX_HOOK_STATE_DIR": str(self.state)})
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout) if result.stdout.strip() else None

    def run_count(self):
        return len(self.runs.read_text().splitlines()) if self.runs.exists() else 0

    def test_project_without_config_is_untouched(self):
        (self.project / ".apex" / "verify.json").unlink()
        self.assertIsNone(self.hook("stop", hook_event_name="Stop"))
        self.assertEqual(self.run_count(), 0)

    def test_unchanged_turn_skips_checks(self):
        self.git_init()
        self.hook("baseline", hook_event_name="UserPromptSubmit")
        self.assertIsNone(self.hook("stop", hook_event_name="Stop"))
        self.assertEqual(self.run_count(), 0)

    def test_failing_change_blocks_then_releases_after_limit(self):
        self.git_init()
        self.hook("baseline", hook_event_name="UserPromptSubmit")
        (self.project / "value.txt").write_text("broken\n")
        for attempt in (1, 2):
            result = self.hook("stop", hook_event_name="Stop", stop_hook_active=attempt > 1)
            self.assertEqual(result["decision"], "block")
            self.assertIn(f"attempt {attempt}/3", result["reason"])
            self.assertIn("value is wrong", result["reason"])
        result = self.hook("stop", hook_event_name="Stop", stop_hook_active=True)
        self.assertNotIn("decision", result)
        self.assertIn("NOT done", result["systemMessage"])

    def test_fixed_change_passes_and_is_not_rerun(self):
        self.git_init()
        self.hook("baseline", hook_event_name="UserPromptSubmit")
        (self.project / "value.txt").write_text("broken\n")
        self.assertEqual(self.hook("stop", hook_event_name="Stop")["decision"], "block")
        (self.project / "value.txt").write_text("ok\n")
        (self.project / "new_file.txt").write_text("untracked change\n")
        self.assertIsNone(self.hook("stop", hook_event_name="Stop", stop_hook_active=True))
        runs = self.run_count()
        self.assertIsNone(self.hook("stop", hook_event_name="Stop"))
        self.assertEqual(self.run_count(), runs)

    def test_only_the_coding_subagent_is_gated(self):
        self.git_init()
        self.hook("baseline", hook_event_name="UserPromptSubmit")
        (self.project / "value.txt").write_text("broken\n")
        self.assertIsNone(self.hook("stop", hook_event_name="SubagentStop", agent_type="Explore"))
        self.assertEqual(self.run_count(), 0)
        result = self.hook("stop", hook_event_name="SubagentStop", agent_type="apex-coding")
        self.assertEqual(result["decision"], "block")

    def test_non_git_project_always_verifies(self):
        (self.project / "value.txt").write_text("broken\n")
        self.hook("baseline", hook_event_name="UserPromptSubmit")
        self.assertEqual(self.hook("stop", hook_event_name="Stop")["decision"], "block")

    def test_invalid_config_is_reported_not_blocking(self):
        self.git_init()
        self.hook("baseline", hook_event_name="UserPromptSubmit")
        (self.project / ".apex" / "verify.json").write_text("{}")
        result = self.hook("stop", hook_event_name="Stop")
        self.assertNotIn("decision", result)
        self.assertIn('"command"', result["systemMessage"])

    def test_guard_denies_only_the_verify_config(self):
        denied = self.hook("guard", hook_event_name="PreToolUse", tool_name="Edit",
                           tool_input={"file_path": ".apex/verify.json"})
        self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIsNone(self.hook("guard", hook_event_name="PreToolUse", tool_name="Write",
                                    tool_input={"file_path": str(self.project / "value.txt")}))


if __name__ == "__main__":
    unittest.main()
