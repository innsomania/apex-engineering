"""Check the worker launcher without contacting a model."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "controls" / "apex_worker.py"
sys.path.insert(0, str(WORKER.parent))
import apex_worker  # noqa: E402

# The exact stream a real `codex exec --json` printed on 2026-11-01 when the account's limit was hit.
LIMIT_EVENTS = "\n".join(json.dumps(e) for e in (
    {"type": "thread.started", "thread_id": "t"}, {"type": "turn.started"},
    {"type": "error", "message": "You\u2019ve hit your usage limit. Upgrade to Pro or try again at Nov 4th."},
    {"type": "turn.failed", "error": {"message": "You\u2019ve hit your usage limit. Upgrade to Pro."}},
))


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
            command = self.dry_run("--role", role, "--engine", "codex")
            self.assertEqual(command[:2], ["codex", "exec"], role)
            self.assertEqual(command[command.index("-m") + 1], model, role)
            self.assertIn(f"model_reasoning_effort={effort}", command, role)
            self.assertEqual(command[command.index("-s") + 1], "workspace-write", role)
        self.assertEqual(apex_worker.ROLES["heavy"][0], "gpt-6.1-sol")
        self.assertEqual(apex_worker.ROLES["ui"][0], "gpt-6.1-terra")
        self.assertEqual(apex_worker.ROLES["light"], apex_worker.ROLES["focused"])

    def test_claude_workers_are_sonnet_medium_for_every_role(self):
        self.assertEqual(set(apex_worker.CLAUDE_ROLES), set(apex_worker.ROLES))
        for role in ("heavy", "focused", "ui", "light"):
            self.assertEqual(apex_worker.CLAUDE_ROLES[role], ("claude-sonnet-5-5", "medium"), role)
        for model, _ in apex_worker.CLAUDE_ROLES.values():
            self.assertNotIn("opus", model.lower(), "Opus is the planner, never a worker")

    def test_default_dry_run_is_claude_sonnet_medium_for_all_roles(self):
        for role in ("heavy", "focused", "ui", "light"):
            command = self.dry_run("--role", role)
            self.assertEqual(command[:2], ["claude", "-p"], role)
            self.assertEqual(command[command.index("--model") + 1], "claude-sonnet-5-5", role)
            self.assertIn("medium", command, role)
            self.assertNotIn("opus", " ".join(command[:-1]).lower(), role)

    def test_engine_claude_runs_the_claude_worker(self):
        command = self.dry_run("--role", "light", "--engine", "claude")
        self.assertEqual(command[:2], ["claude", "-p"])
        self.assertEqual(command[command.index("--model") + 1], "claude-sonnet-5-5")
        self.assertEqual(command[command.index("--permission-mode") + 1], "auto")
        self.assertIn("do not delegate", command[-1])

    def test_usage_limit_is_recognized_and_other_failures_are_not(self):
        self.assertTrue(apex_worker.usage_limited(LIMIT_EVENTS))
        failed = json.dumps({"type": "turn.failed", "error": {"message": "tests failed"}})
        self.assertFalse(apex_worker.usage_limited(failed))
        self.assertFalse(apex_worker.usage_limited('{"type": "item.completed", "item": {"text": "usage limit"}}'))

    def live_run(self, codex_out: str, codex_exit: int, *extra: str,
                 codex_err: str = "", claude_err: str = "", codex_action: str = "",
                 initial_dirty: bool = False) -> dict:
        """Run the launcher for real against fake `codex` and `claude` programs on PATH."""
        with tempfile.TemporaryDirectory() as temp:
            bin_dir, project = Path(temp) / "bin", Path(temp) / "project"
            bin_dir.mkdir()
            project.mkdir()
            if initial_dirty:
                subprocess.run(["git", "init", "-q"], cwd=project, check=True)
                (project / "README.md").write_text("base\n")
                subprocess.run(["git", "add", "README.md"], cwd=project, check=True)
                subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com",
                                "commit", "-qm", "base"], cwd=project, check=True)
                (project / "README.md").write_text("pre-existing user edit\n")
            (Path(temp) / "codex.out").write_text(codex_out)
            claude_out = json.dumps({"type": "result", "result": "Done by Claude", "usage": {"output_tokens": 5}})
            (Path(temp) / "claude.out").write_text(claude_out)
            for name, code, stderr, action in (("codex", codex_exit, codex_err, codex_action),
                                               ("claude", 0, claude_err, "")):
                fake = bin_dir / name
                fake.write_text(f"#!/bin/sh\necho \"$@\" > '{temp}/{name}.args'\n{action}\n"
                                f"cat '{temp}/{name}.out'\nprintf '%s' '{stderr}' >&2\nexit {code}\n")
                fake.chmod(0o755)
            task, out = Path(temp) / "task.md", Path(temp) / "r.json"
            task.write_text("Fix the typo in README.md; check: grep -c teh README.md")
            env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}
            subprocess.run([sys.executable, str(WORKER), "--project", str(project), "--task-file", str(task),
                            "--out", str(out), *extra], env=env, capture_output=True, text=True, check=False)
            result: dict = json.loads(out.read_text())
            result["ran"] = sorted(p.stem for p in Path(temp).glob("*.args"))
            claude_args = Path(temp) / "claude.args"
            result["claude_args"] = claude_args.read_text() if claude_args.exists() else ""
            return result

    def test_codex_usage_limit_hands_the_task_to_claude(self):
        result = self.live_run(LIMIT_EVENTS, 1, "--role", "heavy", "--engine", "auto")
        self.assertEqual(result["ran"], ["claude", "codex"])
        self.assertEqual((result["engine"], result["model"], result["effort"]),
                         ("claude", "claude-sonnet-5-5", "medium"))
        self.assertEqual(result["fallback"], "codex usage limit")
        self.assertEqual((result["exit"], result["report"]), (0, "Done by Claude"))
        self.assertIn("Fix the typo in README.md", result["claude_args"])

    def test_light_task_falls_back_to_sonnet(self):
        result = self.live_run(LIMIT_EVENTS, 1, "--role", "light", "--engine", "auto")
        self.assertEqual((result["model"], result["effort"]), ("claude-sonnet-5-5", "medium"))

    def test_default_engine_never_starts_codex(self):
        result = self.live_run(LIMIT_EVENTS, 1, "--role", "heavy")
        self.assertEqual((result["ran"], result["engine"]), (["claude"], "claude"))

    def test_other_codex_failures_do_not_switch_engines(self):
        failed = json.dumps({"type": "turn.failed", "error": {"message": "tests failed"}})
        result = self.live_run(failed, 1, "--role", "heavy", "--engine", "auto")
        self.assertEqual(result["ran"], ["codex"])
        self.assertEqual((result["engine"], result["fallback"], result["exit"]), ("codex", None, 1))

    def test_existing_dirty_file_is_reported_only_when_worker_changes_it(self):
        result = self.live_run(json.dumps({"type": "turn.completed", "usage": {}}), 0,
                               "--role", "heavy", "--engine", "auto",
                               initial_dirty=True, codex_action="printf 'worker edit\\n' > README.md")
        self.assertEqual(result["changed"], ["README.md"])
        unchanged = self.live_run(json.dumps({"type": "turn.completed", "usage": {}}), 0, "--role", "heavy",
                                  "--engine", "auto", initial_dirty=True)
        self.assertEqual(unchanged["changed"], [])

    def test_stderr_only_failure_is_retained_in_result(self):
        failed = json.dumps({"type": "turn.failed", "error": {"message": "tests failed"}})
        result = self.live_run(failed, 2, "--role", "heavy", "--engine", "auto", codex_err="startup failed")
        self.assertIn("startup failed", result["stderr"])
        self.assertIn("startup failed", result["report"])

    def test_claude_json_stdout_parses_when_stderr_has_warning(self):
        result = self.live_run("", 1, "--role", "heavy", "--engine", "claude", claude_err="warning")
        self.assertEqual(result["report"], "Done by Claude")
        self.assertEqual(result["usage"], {"output_tokens": 5})
        self.assertEqual(result["stderr"], "warning")

    def test_timeout_retains_stderr_diagnostic(self):
        # The timeout must outlast interpreter start-up on a loaded machine (the full suite runs many
        # processes), or the child has printed nothing yet when the timer fires; the sleep outlasts it.
        stdout, stderr, code = apex_worker.run(
            [sys.executable, "-c", "import sys,time; print('out', flush=True); print('err', file=sys.stderr, flush=True); time.sleep(30)"],
            Path.cwd(), 3)
        self.assertEqual((stdout, code), ("out\n", -1))
        self.assertIn("err", stderr)

    def test_engine_codex_never_falls_back(self):
        result = self.live_run(LIMIT_EVENTS, 1, "--role", "heavy", "--engine", "codex")
        self.assertEqual(result["ran"], ["codex"])
        self.assertIsNone(result["fallback"])

    def test_model_and_effort_can_be_overridden(self):
        command = self.dry_run("--role", "focused", "--engine", "codex", "--model", "gpt-6-astra", "--effort", "low")
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
