"""Focused process-control tests using a local fake Codex executable."""

import importlib.util
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
TASKS_SPEC = importlib.util.spec_from_file_location("apex_tasks_for_bridge", ROOT / "Engineering/tasks.py")
tasks = importlib.util.module_from_spec(TASKS_SPEC)
TASKS_SPEC.loader.exec_module(tasks)
BRIDGE_SPEC = importlib.util.spec_from_file_location("apex_coding_bridge", ROOT / "Engineering/coding_bridge.py")
bridge = importlib.util.module_from_spec(BRIDGE_SPEC)
BRIDGE_SPEC.loader.exec_module(bridge)
BRIDGE = ROOT / "Engineering/coding_bridge.py"
MODEL_ARGS = ["-m", "gpt-6-luna", "-c", 'model_reasoning_effort="xhigh"',
              "-c", 'sandbox_mode="danger-full-access"', "-c", 'approval_policy="never"']


FAKE_CODEX = """import json
import os
import sys
import time

args = sys.argv[1:]
prompt = sys.stdin.buffer.read().decode("utf-8")
is_resume = len(args) > 1 and args[1] == "resume"
record = {"argv": args, "cwd": os.getcwd(), "prompt": prompt, "pid": os.getpid()}
with open(os.environ["FAKE_CODEX_LOG"], "a", encoding="utf-8") as stream:
    stream.write(json.dumps(record) + "\\n")
    stream.flush()
mode = os.environ.get("FAKE_CODEX_MODE", "normal")
if mode == "malformed":
    print("not-json")
print(json.dumps({"type": "thread.started", "thread_id": "thread-fixed"}), flush=True)
print(json.dumps({"type": "turn.started"}), flush=True)
print(json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "fake response"}}), flush=True)
if os.environ.get("FAKE_BLOCK_FIRST") == "1" and not is_resume:
    while not os.path.exists(os.environ["FAKE_CODEX_GATE"]):
        time.sleep(0.01)
if mode == "exit":
    sys.exit(23)
if mode != "missing_completion":
    print(json.dumps({"type": "turn.completed"}), flush=True)
"""


def _unix_sockets_allowed():
    """A sandboxed Claude Code shell refuses Unix-socket binds; the bridge needs one."""
    import socket
    directory = tempfile.mkdtemp(prefix="apcb-", dir=os.environ.get("TMPDIR") or None)
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        server.bind(os.path.join(directory, "s"))
        return True
    except PermissionError:
        return False
    finally:
        server.close()
        for name in os.listdir(directory):
            os.unlink(os.path.join(directory, name))
        os.rmdir(directory)


@unittest.skipUnless(_unix_sockets_allowed(),
                     "Unix sockets are blocked here (Claude Code sandbox); run outside the sandbox")
class CodingBridgeTests(unittest.TestCase):
    def setUp(self):
        # A short base keeps Unix socket paths within macOS sun_path limits. Prefer a short
        # TMPDIR (sandboxed sessions only allow writes there), otherwise /tmp.
        base = os.environ.get("TMPDIR", "")
        self.temp = tempfile.TemporaryDirectory(prefix="apcb-", dir=base if base and len(base) <= 32 else "/tmp")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / "project with spaces"
        self.project.mkdir()
        self.state_dir = self.root / "sessions"
        self.ledger = tasks.Ledger(self.root / "tasks.sqlite3")
        self.ledger.initialize()
        self.fake_bin = self.root / "bin"
        self.fake_bin.mkdir()
        # A shebang cannot carry an interpreter path with spaces, and sys.executable may
        # have them, so a /bin/sh wrapper runs the body with the path quoted.
        body = self.fake_bin / "codex_body.py"
        body.write_text(FAKE_CODEX, encoding="utf-8")
        self.fake = self.fake_bin / "codex"
        self.fake.write_text(f'#!/bin/sh\nexec {shlex.quote(sys.executable)} {shlex.quote(str(body))} "$@"\n',
                             encoding="utf-8")
        self.fake.chmod(0o755)
        self.log = self.root / "codex-calls.jsonl"
        self.gate = self.root / "release-initial-turn"
        self.request_file = self.root / "original-request.txt"
        self.request_file.write_text("Apply the original user request exactly.", encoding="utf-8")
        self.env = os.environ.copy()
        self.env.update({"PATH": str(self.fake_bin), "FAKE_CODEX_LOG": str(self.log),
                         "FAKE_CODEX_GATE": str(self.gate)})
        self.sessions = []
        self.addCleanup(self._stop_sessions)

    def _create_active_task(self, *, role="Coding", title="Apply the bounded fix"):
        task = self.ledger.create(
            project="sample project", title=title,
            scope="Change only the bridge module and its focused tests",
            criteria=["The fake Codex call receives the exact task contract",
                      "Follow-up turns reuse the original thread"], role=role)
        self.ledger.transition(task["id"], "start")
        return task["id"]

    def _cli(self, *arguments, env=None, timeout=20):
        return subprocess.run([sys.executable, str(BRIDGE), *map(str, arguments)],
                              cwd=self.project, env=env or self.env,
                              capture_output=True, text=True, timeout=timeout)

    def _start(self, task_id, *, request_file=None, env=None):
        result = self._cli("start", "--project", self.project, "--task-id", task_id,
                           "--store", self.ledger.path, "--request-file",
                           request_file or self.request_file,
                           "--state-dir", self.state_dir, env=env)
        if result.returncode == 0:
            session_id = result.stdout.strip()
            self.sessions.append(session_id)
            return session_id
        return result

    def _status(self, session_id):
        result = self._cli("status", session_id, "--state-dir", self.state_dir)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def _records(self):
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]

    def _wait_until(self, predicate, message, timeout=8):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            result = predicate()
            if result:
                return result
            time.sleep(0.02)
        self.fail(message)

    def _stop_sessions(self):
        for session_id in self.sessions:
            try:
                self._cli("stop", session_id, "--state-dir", self.state_dir, timeout=8)
            except (OSError, subprocess.TimeoutExpired):
                pass

    def test_start_uses_task_contract_and_queued_resume_reuses_thread(self):
        task_id = self._create_active_task()
        original_request = (
            "Match the landing page to references/hero-mobile.png, including the exact "
            "18 px left inset and the original warm color palette.\r\nPreserve café's "
            "typography and spacing."
        )
        self.request_file.write_bytes(original_request.encode("utf-8"))
        self.env["FAKE_BLOCK_FIRST"] = "1"
        session_id = self._start(task_id)
        self.assertRegex(session_id, r"^[0-9a-f]{12}$")
        session_dir = self.state_dir / session_id
        self.assertEqual(session_dir.stat().st_mode & 0o777, 0o700)

        self._wait_until(lambda: len(self._records()) == 1, "Initial fake Codex call was not started")
        running = self._wait_until(
            lambda: (state if (state := self._status(session_id)).get("codex_thread_id") else None),
            "thread.started was not reflected in status")
        self.assertEqual(running["phase"], "running")
        self.assertEqual(running["model"], "gpt-6-luna")
        self.assertEqual(running["reasoning_effort"], "xhigh")
        self.assertEqual(running["turn_count"], 1)
        self.assertEqual(running["latest_agent_message"], "fake response")
        request_snapshot = Path(running["original_request_snapshot_path"])
        self.assertEqual(request_snapshot.read_bytes(), original_request.encode("utf-8"))
        self.assertEqual(request_snapshot.stat().st_mode & 0o777, 0o600)
        self.assertEqual(running["original_request_sha256"],
                         hashlib.sha256(original_request.encode("utf-8")).hexdigest())

        followup = "Keep the change within the recorded scope."
        queued = self._cli("instruct", session_id, "--text", followup, "--state-dir", self.state_dir)
        self.assertEqual(queued.returncode, 0, queued.stderr)
        self.assertEqual(json.loads(queued.stdout)["queue_depth"], 1)
        self.gate.touch()
        self._wait_until(lambda: len(self._records()) == 2, "Queued Codex resume did not start")
        completed = self._wait_until(
            lambda: (state if ((state := self._status(session_id)).get("phase") == "idle"
                              and state.get("turn_count") == 2) else None),
            "Queued Codex resume did not complete")
        self.assertEqual(completed["codex_thread_id"], "thread-fixed")

        initial, resume = self._records()
        resolved_project = str(self.project.resolve())
        self.assertEqual(initial["cwd"], resolved_project)
        self.assertEqual(initial["argv"], ["exec", "--json", "--skip-git-repo-check",
                                            *MODEL_ARGS, "-C", resolved_project, "-"])
        self.assertIn("Apply the bounded fix", initial["prompt"])
        self.assertIn("Change only the bridge module and its focused tests", initial["prompt"])
        self.assertIn("The fake Codex call receives the exact task contract", initial["prompt"])
        self.assertIn("Follow-up turns reuse the original thread", initial["prompt"])
        self.assertEqual(initial["prompt"].count(original_request), 1)
        self.assertIn("task contract bounds this Coding worker's implementation scope",
                      initial["prompt"])
        self.assertIn("report the unresolved conflict", initial["prompt"])
        self.assertEqual(resume["cwd"], resolved_project)
        self.assertEqual(resume["argv"], ["exec", "resume", "thread-fixed", "--json",
                                          "--skip-git-repo-check", *MODEL_ARGS, "-"])
        self.assertEqual(resume["prompt"], followup)
        self.assertEqual(self.ledger.show(task_id)["state"], "active")

        state_file = session_dir / "state.json"
        events_file = session_dir / "events.jsonl"
        stderr_file = session_dir / "codex.stderr.log"
        for path in (state_file, events_file, stderr_file):
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        events = self._cli("events", session_id, "--state-dir", self.state_dir)
        self.assertEqual(events.returncode, 0, events.stderr)
        event_result = json.loads(events.stdout)
        self.assertTrue(any(item.get("event", {}).get("type") == "thread.started"
                            for item in event_result["events"]))

        stopped = self._cli("stop", session_id, "--state-dir", self.state_dir)
        self.assertEqual(stopped.returncode, 0, stopped.stderr)
        self.assertEqual(json.loads(stopped.stdout)["phase"], "stopped")

    def test_stop_kills_running_process_and_discards_queued_turn(self):
        task_id = self._create_active_task()
        self.env["FAKE_BLOCK_FIRST"] = "1"
        session_id = self._start(task_id)
        self._wait_until(lambda: len(self._records()) == 1, "Initial fake Codex call was not started")
        record = self._records()[0]
        self._cli("instruct", session_id, "--text", "This queued turn must not run.",
                  "--state-dir", self.state_dir)
        stopped = self._cli("stop", session_id, "--state-dir", self.state_dir, timeout=15)
        self.assertEqual(stopped.returncode, 0, stopped.stderr)
        state = json.loads(stopped.stdout)
        self.assertEqual(state["phase"], "stopped")
        self.assertEqual(state["queue_depth"], 0)
        self.assertEqual(state["discarded_followups"], 1)
        self.assertEqual(len(self._records()), 1)
        with self.assertRaises(ProcessLookupError):
            os.kill(record["pid"], 0)

    def test_rejects_inactive_and_wrong_role_task_records(self):
        queued_task = self.ledger.create(project="sample project", title="Queued", scope="No change",
                                         criteria=["Must stay queued"], role="Coding")["id"]
        queued = self._start(queued_task)
        self.assertNotIsInstance(queued, str)
        self.assertNotEqual(queued.returncode, 0)
        self.assertIn("active Apex task", queued.stderr)

        wrong_role = self._create_active_task(role="Engineering", title="Engineering owned")
        result = self._start(wrong_role)
        self.assertNotIsInstance(result, str)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("assigned to Coding", result.stderr)
        self.assertFalse(self.state_dir.exists())

    def test_malformed_jsonl_and_nonzero_exit_are_persisted_as_failures(self):
        task_id = self._create_active_task()
        self.env["FAKE_CODEX_MODE"] = "malformed"
        session_id = self._start(task_id)
        self.assertIsInstance(session_id, str)
        failed = self._wait_until(lambda: (state if (state := self._status(session_id)).get("phase") == "failed"
                                           else None), "Malformed output was silently accepted")
        self.assertEqual(failed["malformed_event_count"], 1)
        events = self._cli("events", session_id, "--state-dir", self.state_dir)
        self.assertEqual(events.returncode, 0, events.stderr)
        self.assertTrue(any(item.get("malformed") and item.get("raw") == "not-json"
                            for item in json.loads(events.stdout)["events"]))

        self.env["FAKE_CODEX_MODE"] = "exit"
        second_id = self._start(task_id)
        self.assertIsInstance(second_id, str)
        failed_exit = self._wait_until(
            lambda: (state if (state := self._status(second_id)).get("phase") == "failed" else None),
            "Nonzero Codex exit was silently accepted")
        self.assertIn("status 23", failed_exit["last_error"])

    def test_zero_exit_without_turn_completed_fails_and_discards_queued_followup(self):
        task_id = self._create_active_task()
        self.env["FAKE_CODEX_MODE"] = "missing_completion"
        self.env["FAKE_BLOCK_FIRST"] = "1"
        session_id = self._start(task_id)
        self._wait_until(lambda: len(self._records()) == 1, "Initial fake Codex call was not started")
        self._wait_until(lambda: self._status(session_id).get("codex_thread_id"),
                         "thread.started was not reflected in status")
        queued = self._cli("instruct", session_id, "--text", "Do not run after an incomplete turn.",
                           "--state-dir", self.state_dir)
        self.assertEqual(queued.returncode, 0, queued.stderr)
        self.assertEqual(json.loads(queued.stdout)["queue_depth"], 1)

        self.gate.touch()
        failed = self._wait_until(
            lambda: (state if (state := self._status(session_id)).get("phase") == "failed" else None),
            "Zero exit without turn.completed was silently accepted")
        self.assertIn("exactly one turn.completed", failed["last_error"])
        self.assertEqual(failed["discarded_followups"], 1)
        self.assertEqual(len(self._records()), 1)

    def test_stop_signal_wins_over_completion_and_socket_dispatch(self):
        def make_supervisor(session_id):
            session_dir = self.root / session_id
            session_dir.mkdir(mode=0o700)
            snapshot_path = session_dir / bridge.USER_REQUEST_NAME
            bridge._write_private_file(snapshot_path, b"signal test request", exclusive=True)
            state = bridge._new_state(
                session_id, self.project.resolve(),
                {"id": "APX-signal-test", "project": "sample", "role": "Coding"},
                hashlib.sha256(b"signal test request").hexdigest(), snapshot_path)
            state["event_log_path"] = str(session_dir / bridge.EVENTS_NAME)
            state["stderr_log_path"] = str(session_dir / bridge.STDERR_NAME)
            bridge._atomic_state_write(session_dir, state)
            bridge._write_private_file(session_dir / bridge.EVENTS_NAME, b"", exclusive=True)
            return bridge.Supervisor(session_dir, self.project.resolve(), ""), session_dir

        completion_supervisor, completion_dir = make_supervisor("a" * 12)
        try:
            completion_supervisor.signal_requested = threading.Event()
            completion_supervisor.signal_requested.set()
            completion_supervisor._update(codex_thread_id="thread-fixed", phase="running", queue_depth=1)
            completion_supervisor.pending.append("queued completion-boundary instruction")
            handle = bridge.TurnHandle(None, resumed=False)
            handle.turn_completed_count = 1
            completion_supervisor.child = handle
            with patch.object(completion_supervisor, "_start_next") as start_next:
                completion_supervisor._finish_turn(handle, 0)
                start_next.assert_not_called()
            self.assertEqual(completion_supervisor.state["phase"], "stopping")
            self.assertEqual(completion_supervisor.state["discarded_followups"], 1)
            self.assertEqual(completion_supervisor.state["queue_depth"], 0)
        finally:
            completion_supervisor.event_file.close()

        socket_supervisor, socket_dir = make_supervisor("b" * 12)
        try:
            socket_supervisor.signal_requested = threading.Event()
            socket_supervisor.signal_requested.set()
            with patch.object(socket_supervisor, "_start_next") as start_next:
                response = socket_supervisor._handle({"op": "instruct", "text": "queued from socket"})
                start_next.assert_not_called()
            self.assertFalse(response["ok"])
            self.assertFalse(socket_supervisor.pending)
            self.assertFalse(socket_supervisor.state["accepting"])
            self.assertEqual(socket_supervisor.state["phase"], "stopping")
        finally:
            socket_supervisor.event_file.close()

    def test_invalid_or_missing_request_source_never_launches_codex(self):
        task_id = self._create_active_task()
        empty = self.root / "empty-request.txt"
        empty.write_bytes(b"")
        whitespace = self.root / "whitespace-request.txt"
        whitespace.write_bytes(" \t\r\n ".encode("utf-8"))
        invalid_utf8 = self.root / "invalid-utf8-request.txt"
        invalid_utf8.write_bytes(b"\xff")
        oversized = self.root / "oversized-request.txt"
        oversized.write_bytes(b"x" * (bridge.MAX_REQUEST_BYTES + 1))
        directory = self.root / "request-directory"
        directory.mkdir()
        fifo = self.root / "request-fifo"
        os.mkfifo(fifo)
        missing = self.root / "missing-request.txt"

        no_argument = self._cli("start", "--project", self.project, "--task-id", task_id,
                                 "--store", self.ledger.path, "--state-dir", self.state_dir)
        self.assertEqual(no_argument.returncode, 2)
        for source in (missing, empty, whitespace, invalid_utf8, oversized, directory, fifo):
            with self.subTest(source=source.name):
                result = self._cli("start", "--project", self.project, "--task-id", task_id,
                                   "--store", self.ledger.path, "--request-file", source,
                                   "--state-dir", self.state_dir, timeout=3)
                self.assertNotEqual(result.returncode, 0)
                if source == whitespace:
                    self.assertIn("empty", result.stderr)
        self.assertFalse(self.state_dir.exists())
        self.assertFalse(self.log.exists())

    def test_missing_codex_fails_startup_without_claiming_a_session(self):
        task_id = self._create_active_task()
        empty_path = self.root / "empty-path"
        empty_path.mkdir()
        env = self.env.copy()
        env["PATH"] = str(empty_path)
        result = self._start(task_id, env=env)
        self.assertNotIsInstance(result, str)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Codex CLI executable was not found", result.stderr)
        state_files = list(self.state_dir.glob("*/state.json"))
        self.assertEqual(len(state_files), 1)
        saved = json.loads(state_files[0].read_text(encoding="utf-8"))
        self.assertEqual(saved["phase"], "failed")
        self.assertFalse(saved["child_pid"])
        self.assertFalse((state_files[0].parent / "c.sock").exists())


if __name__ == "__main__":
    unittest.main()
