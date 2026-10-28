"""Check the Codex worker launcher without contacting a model."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "controls" / "apex_worker.py"
sys.path.insert(0, str(WORKER.parent))
import apex_worker  # noqa: E402


class WorkerTests(unittest.TestCase):
    def dry_run(self, *extra: str) -> list[str]:
        with tempfile.TemporaryDirectory() as temp:
            task = Path(temp) / "task.md"
            task.write_text("Add `--json` to inventory.py; check: python3 -m unittest")
            result = subprocess.run([sys.executable, str(WORKER), "--project", temp, "--task-file", str(task),
                                     "--out", str(Path(temp) / "r.json"), "--dry-run", *extra],
                                    check=True, capture_output=True, text=True)
            command: list[str] = json.loads(result.stdout)
            return command

    def test_each_role_runs_its_model_in_the_sandbox(self):
        for role, (model, effort) in apex_worker.ROLES.items():
            command = self.dry_run("--role", role)
            self.assertEqual(command[:2], ["codex", "exec"], role)
            self.assertEqual(command[command.index("-m") + 1], model, role)
            self.assertIn(f"model_reasoning_effort={effort}", command, role)
            self.assertEqual(command[command.index("-s") + 1], "workspace-write", role)
        self.assertEqual(apex_worker.ROLES["heavy"][0], "gpt-6.1-sol")
        self.assertEqual(apex_worker.ROLES["ui"][0], "gpt-6.1-terra")

    def test_model_and_effort_can_be_overridden(self):
        command = self.dry_run("--role", "focused", "--model", "gpt-6-astra", "--effort", "low")
        self.assertEqual(command[command.index("-m") + 1], "gpt-6-astra")
        self.assertIn("model_reasoning_effort=low", command)

    def test_the_worker_is_told_not_to_plan_or_delegate(self):
        prompt = self.dry_run("--role", "heavy")[-1]
        self.assertIn("do not ask for plan approval", prompt)
        self.assertIn("do not delegate", prompt)
        self.assertTrue(prompt.endswith("Add `--json` to inventory.py; check: python3 -m unittest"))

    def test_summary_keeps_the_last_report_and_the_usage(self):
        events = "\n".join(json.dumps(e) for e in (
            {"type": "item.completed", "item": {"type": "agent_message", "text": "working"}},
            {"type": "item.completed", "item": {"type": "agent_message", "text": "Done: 3 tests pass"}},
            {"type": "turn.completed", "usage": {"input_tokens": 1200, "output_tokens": 80}},
        )) + "\nnot json\n"
        self.assertEqual(apex_worker.summarize(events),
                         {"report": "Done: 3 tests pass", "usage": {"input_tokens": 1200, "output_tokens": 80}})


if __name__ == "__main__":
    unittest.main()
