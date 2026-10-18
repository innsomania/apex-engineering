"""Task lifecycle and persistence tests; all writes stay in temporary directories."""

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("apex_tasks", ROOT / "Engineering/tasks.py")
tasks = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tasks)


class TaskTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="apex task tests ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.ledger = tasks.Ledger(self.root / "state.sqlite3")
        self.ledger.initialize()
        self.proof = self.root / "test.log"
        self.proof.write_text("Observed result: passed\n")

    def create(self, **kwargs):
        args = dict(project="sample", title="Fix scoped behavior", scope="One module only",
                    criteria=["Authorized behavior passes", "Forbidden behavior denied"])
        args.update(kwargs)
        return self.ledger.create(**args)["id"]

    def review(self, task_id):
        self.ledger.transition(task_id, "start")
        self.ledger.transition(task_id, "review")

    def prove(self, task_id):
        for criterion in ("1", "2"):
            self.ledger.evidence(task_id, criterion, "pass", self.proof,
                                 "Observed fixture result", "Test")

    def test_lifecycle_survives_reopening_and_records_history(self):
        task_id = self.create(role="Coding")
        self.review(task_id)
        self.prove(task_id)
        self.ledger.transition(task_id, "complete")
        reopened = tasks.Ledger(self.ledger.path).show(task_id)
        self.assertEqual(reopened["state"], "completed")
        self.assertEqual(reopened["role"], "Coding")
        self.assertEqual([e["event"] for e in reopened["history"]],
                         ["created", "start", "review", "evidence", "evidence", "complete"])

    def test_dependency_blocks_start_and_ready_queue(self):
        parent = self.create()
        child = self.create(dependencies=[parent])
        self.assertEqual([t["id"] for t in self.ledger.list(ready=True)], [parent])
        with self.assertRaises(ValueError):
            self.ledger.transition(child, "start")
        self.review(parent)
        self.prove(parent)
        self.ledger.transition(parent, "complete")
        self.assertEqual([t["id"] for t in self.ledger.list(ready=True)], [child])
        self.ledger.transition(child, "start")

    def test_invalid_dependencies_and_project_isolation(self):
        task_id = self.create()
        for kwargs in ({"dependencies": ["missing"]},
                       {"dependencies": [task_id], "project": "other"}):
            with self.assertRaises(ValueError):
                self.create(**kwargs)
        self.ledger.transition(task_id, "cancel", "User withdrew task")
        with self.assertRaises(ValueError):
            self.create(dependencies=[task_id])
        self.assertEqual(self.ledger.list(project="other"), [])

    def test_completion_requires_all_current_passing_evidence(self):
        task_id = self.create()
        self.review(task_id)
        with self.assertRaises(ValueError):
            self.ledger.transition(task_id, "complete")
        self.ledger.evidence(task_id, "1", "pass", self.proof, "Observed pass", "Test")
        self.ledger.evidence(task_id, "2", "fail", self.proof, "Observed failure", "Security")
        with self.assertRaises(ValueError):
            self.ledger.transition(task_id, "complete")
        self.prove(task_id)
        self.proof.write_text("Changed after verification")
        with self.assertRaises(ValueError):
            self.ledger.transition(task_id, "complete")
        self.assertEqual(self.ledger.show(task_id)["state"], "review")

    def test_deleted_evidence_blocks_completion(self):
        task_id = self.create()
        self.review(task_id)
        self.prove(task_id)
        self.proof.unlink()
        with self.assertRaises(ValueError):
            self.ledger.transition(task_id, "complete")

    def test_block_pause_resume_and_rework_clear_stale_evidence(self):
        task_id = self.create()
        self.review(task_id)
        self.prove(task_id)
        self.ledger.transition(task_id, "rework", "Implementation changed")
        self.assertEqual(self.ledger.show(task_id)["evidence"], {})
        self.ledger.transition(task_id, "block", "Required decision missing")
        self.ledger.assign(task_id, "Security", "Authorization review needed")
        self.ledger.transition(task_id, "pause", "User paused work")
        with self.assertRaises(ValueError):
            self.ledger.transition(task_id, "start")
        with self.assertRaises(ValueError):
            self.ledger.transition(task_id, "resume")
        self.ledger.transition(task_id, "resume", "User explicitly requested continuation")
        self.assertEqual(self.ledger.show(task_id)["state"], "queued")

    def test_terminal_records_reject_further_changes(self):
        for terminal in ("complete", "cancel"):
            task_id = self.create()
            if terminal == "complete":
                self.review(task_id)
                self.prove(task_id)
            self.ledger.transition(task_id, terminal, "Done")
            before = self.ledger.show(task_id)
            with self.assertRaises(ValueError):
                self.ledger.assign(task_id, "Test", "Attempt reassignment")
            for action in tasks.TRANSITIONS:
                with self.assertRaises(ValueError):
                    self.ledger.transition(task_id, action, "Attempt mutation")
            with self.assertRaises(ValueError):
                self.ledger.evidence(task_id, "1", "pass", self.proof, "Late result", "Test")
            self.assertEqual(before, self.ledger.show(task_id))

    def test_invalid_input_rolls_back_without_task(self):
        for kwargs in ({"title": " "}, {"criteria": []}, {"criteria": ["same", "same"]},
                       {"role": "Unknown"}, {"scope": ""}):
            with self.assertRaises(ValueError):
                self.create(**kwargs)
        self.assertEqual(self.ledger.list(), [])

    def test_evidence_rejects_wrong_stage_criterion_and_role(self):
        task_id = self.create()
        with self.assertRaises(ValueError):
            self.ledger.evidence(task_id, "1", "pass", self.proof, "Result", "Test")
        self.review(task_id)
        for criterion, role in (("9", "Test"), ("1", "Coding")):
            with self.assertRaises(ValueError):
                self.ledger.evidence(task_id, criterion, "pass", self.proof, "Result", role)

    def test_concurrent_claim_only_one_start_succeeds(self):
        task_id = self.create()
        def start(_):
            try:
                tasks.Ledger(self.ledger.path).transition(task_id, "start")
                return True
            except ValueError:
                return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(start, range(2))), [False, True])
        self.assertEqual(len(self.ledger.show(task_id)["history"]), 2)

    def test_export_preserves_unowned_note_and_atomic_previous_snapshot(self):
        self.create(title="Task [unsafe](https://example.com) <script>")
        note = self.root / "board.md"
        note.write_text("User notes")
        with self.assertRaises(ValueError):
            self.ledger.export(note)
        self.assertEqual(note.read_text(), "User notes")
        board = self.root / "apex-board.md"
        self.ledger.export(board)
        previous = board.read_bytes()
        self.assertNotIn("<script>", board.read_text())
        with patch.object(tasks.os, "replace", side_effect=OSError("Publish failed")):
            with self.assertRaises(OSError):
                self.ledger.export(board)
        self.assertEqual(board.read_bytes(), previous)
        self.assertEqual(list(self.root.glob(".apex-board-*")), [])

    def test_configured_board_refreshes_after_every_change(self):
        board = self.root / "vault dir" / "Apex Tasks.md"
        (self.root / "state.board.json").write_text(json.dumps({"output": str(board)}))
        task_id = self.create(title="First board task")
        self.assertIn("First board task", board.read_text())
        self.assertIn("State: queued", board.read_text())
        self.ledger.transition(task_id, "start")
        self.assertIn("State: active", board.read_text())
        self.ledger.assign(self.create(title="Second"), "Coding", "Implementation owner")
        self.assertIn("Second", board.read_text())
        self.assertIsNone(self.ledger.board_warning)

    def test_board_failure_keeps_the_task_change(self):
        unowned = self.root / "Personal note.md"
        unowned.write_text("my own note\n")
        (self.root / "state.board.json").write_text(json.dumps({"output": str(unowned)}))
        task_id = self.create()
        self.assertEqual(self.ledger.show(task_id)["state"], "queued")
        self.assertIn("board was not refreshed", self.ledger.board_warning)
        self.assertEqual(unowned.read_text(), "my own note\n")

    def test_without_board_config_nothing_is_exported(self):
        self.create()
        self.assertEqual(sorted(p.name for p in self.root.iterdir()),
                         ["state.sqlite3", "test.log"])

    def test_read_does_not_create_store_and_init_preserves_existing(self):
        missing = self.root / "missing" / "ledger.sqlite3"
        with self.assertRaises(ValueError):
            tasks.Ledger(missing).list()
        self.assertFalse(missing.parent.exists())
        self.create()
        before = self.ledger.path.read_bytes()
        with self.assertRaises(ValueError):
            self.ledger.initialize()
        self.assertEqual(self.ledger.path.read_bytes(), before)

    def test_cli_persists_between_processes_with_spaces(self):
        command = [sys.executable, str(ROOT / "Engineering/tasks.py"), "--store", str(self.ledger.path)]
        result = subprocess.run([*command, "create", "--project", "demo", "--title", "Small task", "--scope", "One file", "--criterion", "Observed behavior"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        task_id = json.loads(result.stdout)["id"]
        result = subprocess.run([*command, "show", task_id], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["title"], "Small task")


if __name__ == "__main__":
    unittest.main()
