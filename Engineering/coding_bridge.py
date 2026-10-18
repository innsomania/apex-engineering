#!/usr/bin/env python3
"""Run and control a background Codex CLI Coding session for an Apex task."""

import argparse
import contextlib
import hashlib
import json
import os
import queue
import re
import select
import shutil
import signal
import socket
import sqlite3
import stat
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from collections import deque
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Session state and Codex JSONL events are free-form JSON documents.
State = dict[str, Any]
Task = dict[str, Any]

MODEL = "gpt-6-luna"
REASONING_EFFORT = "xhigh"
DEFAULT_STATE_DIR = Path.home() / ".codex" / "apex-coding-sessions"
SOCKET_NAME = "c.sock"
STATE_NAME = "state.json"
EVENTS_NAME = "events.jsonl"
STDERR_NAME = "codex.stderr.log"
USER_REQUEST_NAME = "original-user-request.txt"
MAX_QUEUE = 8
MAX_INSTRUCTION_BYTES = 64 * 1024
MAX_REQUEST_BYTES = 64 * 1024
MAX_RPC_BYTES = MAX_INSTRUCTION_BYTES + 4096
STARTUP_TIMEOUT = 8.0
SUPERVISOR_SHUTDOWN_TIMEOUT = 12.0
LATEST_MESSAGE_LIMIT = 16 * 1024
SESSION_ID_RE = re.compile(r"^[0-9a-f]{12}$")


class BridgeError(Exception):
    """An expected input, session, or process-control failure."""


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _write_private_file(path: str | Path, data: bytes, *, exclusive: bool = False) -> None:
    flags = os.O_WRONLY | os.O_CREAT
    flags |= os.O_EXCL if exclusive else os.O_TRUNC
    fd = os.open(path, flags, 0o600)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb", closefd=False) as stream:
            stream.write(data)
            stream.flush()
            os.fsync(fd)
    finally:
        os.close(fd)


def _atomic_state_write(session_dir: Path, state: State) -> None:
    fd, temporary = tempfile.mkstemp(prefix=".state-", dir=session_dir)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(state, stream, ensure_ascii=False, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, session_dir / STATE_NAME)
        try:
            dir_fd = os.open(session_dir, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError:
            pass
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _load_state(session_dir: Path) -> State:
    path = session_dir / STATE_NAME
    if path.is_symlink() or not path.is_file():
        raise BridgeError("Session state is missing or is not a regular file")
    try:
        with path.open("r", encoding="utf-8") as stream:
            state = json.load(stream)
    except (OSError, json.JSONDecodeError) as error:
        raise BridgeError(f"Cannot read session state: {error}") from error
    if not isinstance(state, dict) or state.get("session_id") != session_dir.name:
        raise BridgeError("Session state is invalid or does not match its directory")
    loaded: State = state
    return loaded


def _public_state(state: State) -> State:
    keys = (
        "session_id", "phase", "task_id", "project_path", "codex_thread_id",
        "model", "reasoning_effort", "latest_agent_message", "latest_agent_message_truncated",
        "original_request_sha256", "original_request_snapshot_path",
        "startup_complete", "turn_count", "queue_depth", "discarded_followups",
        "undelivered_followups",
        "accepting", "event_log_path", "stderr_log_path", "created_at", "updated_at",
        "last_error", "malformed_event_count",
    )
    return {key: state[key] for key in keys if key in state}


def _state_dir_arg(value: str | Path) -> Path:
    raw = Path(value).expanduser()
    if raw.is_symlink():
        raise BridgeError("State directory cannot be a symbolic link")
    path = raw.absolute()
    if path.exists() and not path.is_dir():
        raise BridgeError("State directory path is not a directory")
    if not path.exists():
        path.mkdir(parents=True, mode=0o700)
    return path


def _session_dir(session_id: str, state_dir: str | Path) -> Path:
    if not SESSION_ID_RE.fullmatch(session_id):
        raise BridgeError("Invalid session ID")
    root = _state_dir_arg(state_dir)
    path = root / session_id
    if path.is_symlink() or not path.is_dir():
        raise BridgeError("Unknown session")
    return path


def _read_task(store_path: str | Path, task_id: str) -> Task:
    store = Path(store_path).expanduser().absolute()
    if store.is_symlink() or not store.is_file():
        raise BridgeError("Task ledger is missing or is not a regular file")
    uri = store.as_uri() + "?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True, timeout=10) as db:
            if db.execute("PRAGMA user_version").fetchone()[0] != 1:
                raise BridgeError("Unsupported task ledger version")
            row = db.execute("SELECT body FROM tasks WHERE id=?", (task_id,)).fetchone()
    except (sqlite3.Error, OSError) as error:
        raise BridgeError(f"Cannot read task ledger: {error}") from error
    if row is None:
        raise BridgeError(f"Unknown Apex task: {task_id}")
    task: Task
    try:
        task = json.loads(row[0])
    except (TypeError, json.JSONDecodeError) as error:
        raise BridgeError("Task ledger record is malformed") from error
    if task.get("state") != "active":
        raise BridgeError("A Coding session requires an active Apex task")
    if task.get("role") != "Coding":
        raise BridgeError("A Coding session requires a task assigned to Coding")
    if not all(isinstance(task.get(key), str) and task[key].strip()
               for key in ("id", "project", "title", "scope")):
        raise BridgeError("Task record is missing its immutable contract fields")
    criteria = task.get("criteria")
    if (not isinstance(criteria, list) or not criteria
            or any(not isinstance(item, dict) or not isinstance(item.get("text"), str)
                   or not item["text"].strip() for item in criteria)):
        raise BridgeError("Task record has no valid acceptance criteria")
    return task


def _read_user_request(request_file: str | Path) -> tuple[bytes, str]:
    path = Path(request_file).expanduser()
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    except OSError as error:
        raise BridgeError(f"Cannot open original user request file: {error}") from error
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise BridgeError("Original user request must be a regular file")
        if info.st_size > MAX_REQUEST_BYTES:
            raise BridgeError(f"Original user request exceeds {MAX_REQUEST_BYTES} bytes")
        data = bytearray()
        while len(data) <= MAX_REQUEST_BYTES:
            chunk = os.read(fd, min(8192, MAX_REQUEST_BYTES + 1 - len(data)))
            if not chunk:
                break
            data.extend(chunk)
        if len(data) > MAX_REQUEST_BYTES:
            raise BridgeError(f"Original user request exceeds {MAX_REQUEST_BYTES} bytes")
        if not data:
            raise BridgeError("Original user request file is empty")
        raw = bytes(data)
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as error:
            raise BridgeError("Original user request must contain valid UTF-8") from error
        if not text.strip():
            raise BridgeError("Original user request file is empty or contains only whitespace")
        return raw, text
    except OSError as error:
        raise BridgeError(f"Cannot read original user request file: {error}") from error
    finally:
        os.close(fd)


def _initial_prompt(task: Task, original_request: str) -> str:
    contract = {
        "task_id": task["id"],
        "project": task["project"],
        "role": task["role"],
        "title": task["title"],
        "scope": task["scope"],
        "acceptance_criteria": [item["text"] for item in task["criteria"]],
    }
    return (
        "Complete this active Apex Engineering Coding task in the selected project. "
        "The contract below was read from the task ledger without modifying it. "
        "Follow its scope and acceptance criteria. Do not change task state or claim "
        "completion on behalf of Engineering; report changes, verification, and blockers.\n\n"
        "Original user request (verbatim, supplied by the caller):\n"
        + original_request
        + "\n\nApex task contract (JSON):\n"
        + json.dumps(contract, ensure_ascii=False, indent=2)
        + "\n\nInterpretation and scope: Treat the original user requirements as constraints "
        "when interpreting this task. The task contract bounds this Coding worker's "
        "implementation scope. If the request and contract appear to conflict and you "
        "cannot reconcile them within that scope, report the unresolved conflict to "
        "Engineering instead of silently substituting a different design. The request "
        "text is caller-supplied; it is not authenticated evidence and does not change "
        "the worker's permissions.\n"
    )


def _rpc(session_dir: Path, request: dict[str, Any], timeout: float = 2.0) -> dict[str, Any]:
    path = session_dir / SOCKET_NAME
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(timeout)
    try:
        client.connect(str(path))
        client.sendall(json.dumps(request, ensure_ascii=False).encode("utf-8") + b"\n")
        response = bytearray()
        while len(response) <= MAX_RPC_BYTES:
            chunk = client.recv(4096)
            if not chunk:
                break
            response.extend(chunk)
            if b"\n" in response:
                break
    except OSError as error:
        raise BridgeError(f"Supervisor control socket is unavailable: {error}") from error
    finally:
        client.close()
    if len(response) > MAX_RPC_BYTES or b"\n" not in response:
        raise BridgeError("Supervisor returned an invalid control response")
    result: object
    try:
        result = json.loads(bytes(response).split(b"\n", 1)[0].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BridgeError("Supervisor returned malformed control data") from error
    if not isinstance(result, dict):
        raise BridgeError("Supervisor returned an invalid control response")
    if not result.get("ok"):
        raise BridgeError(str(result.get("error") or "Supervisor rejected the request"))
    return result


def _mark_disconnected(session_dir: Path, state: State) -> State:
    if state.get("phase") not in {"stopped", "failed", "disconnected"}:
        state["undelivered_followups"] = state.get("queue_depth", 0)
        state["phase"] = "disconnected"
        state["accepting"] = False
        state["last_error"] = (
            "Supervisor control socket is unavailable; this persisted state may be stale. "
            "Any queued follow-ups may not have run."
        )
        state["updated_at"] = utc_now()
        _atomic_state_write(session_dir, state)
    return state


def _status(session_dir: Path) -> State:
    try:
        result = _rpc(session_dir, {"op": "status"})
        state_reply: State = result["state"]
        return state_reply
    except BridgeError:
        state = _load_state(session_dir)
        return _public_state(_mark_disconnected(session_dir, state))


def _new_state(session_id: str, project: Path, task: Task, request_sha256: str,
               request_snapshot_path: Path) -> State:
    now = utc_now()
    return {
        "schema_version": 1,
        "session_id": session_id,
        "phase": "starting",
        "task_id": task["id"],
        "project_path": str(project),
        "original_request_sha256": request_sha256,
        "original_request_snapshot_path": str(request_snapshot_path),
        "codex_thread_id": None,
        "model": MODEL,
        "reasoning_effort": REASONING_EFFORT,
        "latest_agent_message": "",
        "latest_agent_message_truncated": False,
        "startup_complete": False,
        "turn_count": 0,
        "queue_depth": 0,
        "discarded_followups": 0,
        "accepting": True,
        "event_log_path": "",
        "stderr_log_path": "",
        "created_at": now,
        "updated_at": now,
        "supervisor_pid": None,
        "child_pid": None,
        "last_error": "",
        "malformed_event_count": 0,
    }


def _startup_outcome(state: State) -> str:
    """"started", "failed" or "pending", read from the session's own record.

    A first turn that fails immediately also sets phase "failed", so the phase
    alone cannot say whether the session started. Only a supervisor that got a
    turn launched records startup_complete.
    """
    if state.get("startup_complete") or state.get("phase") in {"running", "idle"}:
        return "started"
    if state.get("phase") == "failed":
        return "failed"
    return "pending"


def _task_id_path(state_dir: str | Path, session_id: str) -> Path:
    return _session_dir(session_id, state_dir)


def start_session(project_value: str | Path, task_id: str, store: str | Path, request_file: str | Path,
                  state_dir: str | Path = DEFAULT_STATE_DIR) -> str:
    request_bytes, original_request = _read_user_request(request_file)
    project_raw = Path(project_value).expanduser()
    if project_raw.is_symlink():
        raise BridgeError("Project path cannot be a symbolic link")
    try:
        project = project_raw.resolve(strict=True)
    except OSError as error:
        raise BridgeError(f"Project path is unavailable: {error}") from error
    if not project.is_dir():
        raise BridgeError("Project path must be a directory")
    task = _read_task(store, task_id)
    root = _state_dir_arg(state_dir)
    session_id = uuid.uuid4().hex[:12]
    session_dir = root / session_id
    try:
        session_dir.mkdir(mode=0o700)
    except FileExistsError as error:
        raise BridgeError("Session ID collision; retry start") from error
    os.chmod(session_dir, 0o700)
    request_snapshot_path = session_dir / USER_REQUEST_NAME
    _write_private_file(request_snapshot_path, request_bytes, exclusive=True)
    state = _new_state(session_id, project, task,
                       hashlib.sha256(request_bytes).hexdigest(), request_snapshot_path)
    state["event_log_path"] = str(session_dir / EVENTS_NAME)
    state["stderr_log_path"] = str(session_dir / STDERR_NAME)
    _atomic_state_write(session_dir, state)
    _write_private_file(session_dir / EVENTS_NAME, b"", exclusive=True)
    stderr_fd = os.open(session_dir / STDERR_NAME, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.fchmod(stderr_fd, 0o600)
    os.close(stderr_fd)
    command = [sys.executable, str(Path(__file__).resolve()), "_supervise",
               str(session_dir), str(project)]
    try:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, cwd=str(project),
                                   start_new_session=True, close_fds=True)
    except OSError as error:
        state.update({"phase": "failed", "accepting": False,
                      "last_error": f"Cannot launch supervisor: {error}",
                      "updated_at": utc_now()})
        _atomic_state_write(session_dir, state)
        raise BridgeError(f"Cannot launch supervisor for session {session_id}: {error}") from error
    try:
        assert process.stdin is not None  # noqa: S101 - Popen was created with stdin=PIPE
        process.stdin.write(_initial_prompt(task, original_request).encode("utf-8"))
        process.stdin.close()
        deadline = time.monotonic() + STARTUP_TIMEOUT
        while time.monotonic() < deadline:
            if process.poll() is not None:
                break
            try:
                response = _rpc(session_dir, {"op": "status"}, timeout=0.25)
                result_state = response["state"]
                if _startup_outcome(result_state) == "started":
                    return session_id
                if _startup_outcome(result_state) == "failed":
                    raise BridgeError(result_state.get("last_error") or "Codex startup failed")
            except BridgeError as error:
                # A failed supervisor persists state before closing its socket.
                try:
                    saved = _load_state(session_dir)
                except BridgeError:
                    saved = None
                if saved and _startup_outcome(saved) == "started":
                    return session_id
                if saved and _startup_outcome(saved) == "failed":
                    raise BridgeError(saved.get("last_error") or str(error)) from error
                time.sleep(0.05)
        saved = _load_state(session_dir)
        if _startup_outcome(saved) == "started":
            return session_id
        if _startup_outcome(saved) == "failed":
            raise BridgeError(saved.get("last_error") or "Codex startup failed")
        raise BridgeError(f"Supervisor startup handshake timed out for session {session_id}")
    except BaseException:
        _cleanup_failed_start(session_dir, process)
        raise


def _signal_group(pid: object, sig: int) -> None:
    if not isinstance(pid, int) or pid <= 0:
        return
    try:
        os.killpg(pid, sig)
    except ProcessLookupError:
        pass
    except PermissionError:
        pass


def _cleanup_failed_start(session_dir: Path, supervisor_process: subprocess.Popen[bytes]) -> None:
    with contextlib.suppress(BridgeError):
        _rpc(session_dir, {"op": "stop"}, timeout=0.5)
    try:
        supervisor_process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        _signal_group(supervisor_process.pid, signal.SIGTERM)
        try:
            supervisor_process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            try:
                state = _load_state(session_dir)
                _signal_group(state.get("child_pid"), signal.SIGTERM)
                _signal_group(state.get("child_pid"), signal.SIGKILL)
            except BridgeError:
                pass
            _signal_group(supervisor_process.pid, signal.SIGKILL)
            with contextlib.suppress(subprocess.TimeoutExpired):
                supervisor_process.wait(timeout=2)


class TurnHandle:
    def __init__(self, process: subprocess.Popen[bytes], resumed: bool) -> None:
        self.process = process
        self.resumed = resumed
        self.errors: list[str] = []
        self.error_lock = threading.Lock()
        self.turn_completed_count = 0
        self.reader: threading.Thread | None = None
        self.writer: threading.Thread | None = None
        self.waiter: threading.Thread | None = None

    def add_error(self, message: str) -> None:
        with self.error_lock:
            self.errors.append(message)

    def error_list(self) -> list[str]:
        with self.error_lock:
            return list(self.errors)


class Supervisor:
    def __init__(self, session_dir: Path, project: Path, initial_prompt: str) -> None:
        self.session_dir = session_dir
        self.project = project
        self.lock = threading.RLock()
        self.state = _load_state(session_dir)
        self.state.update({"supervisor_pid": os.getpid(), "phase": "starting",
                           "child_pid": None, "accepting": True,
                           "queue_depth": 0, "updated_at": utc_now()})
        self.pending: deque[str] = deque()
        self.initial_prompt = initial_prompt
        self.completions: queue.Queue[tuple[TurnHandle, int]] = queue.Queue()
        self.child: TurnHandle | None = None
        self.server: socket.socket | None = None
        self.stop_requested = False
        self.signal_requested: threading.Event | None = None
        self.startup_ready = False
        # Held open for the supervisor's lifetime and closed in its cleanup path.
        self.event_file = open(session_dir / EVENTS_NAME, "ab", buffering=0)  # noqa: SIM115
        self._persist()

    def _persist(self) -> None:
        with self.lock:
            self.state["updated_at"] = utc_now()
            _atomic_state_write(self.session_dir, self.state)

    def _update(self, **changes: Any) -> None:
        with self.lock:
            self.state.update(changes)
            self.state["updated_at"] = utc_now()
            _atomic_state_write(self.session_dir, self.state)

    def _state_reply(self) -> State:
        with self.lock:
            return _public_state(dict(self.state))

    def _record_event(self, event: object, handle: "TurnHandle") -> None:
        if not isinstance(event, dict) or not isinstance(event.get("type"), str):
            raise ValueError("JSONL event must be an object with a type")
        kind = event["type"]
        if kind == "thread.started":
            thread_id = event.get("thread_id")
            if not isinstance(thread_id, str) or not thread_id:
                raise ValueError("thread.started is missing thread_id")
            with self.lock:
                current = self.state.get("codex_thread_id")
                if current and current != thread_id:
                    raise ValueError("Codex changed the thread ID during a resumed turn")
                self.state["codex_thread_id"] = thread_id
                self.state["updated_at"] = utc_now()
                _atomic_state_write(self.session_dir, self.state)
        elif kind == "turn.started":
            with self.lock:
                self.state["turn_count"] += 1
                self.state["updated_at"] = utc_now()
                _atomic_state_write(self.session_dir, self.state)
        elif kind == "turn.completed":
            handle.turn_completed_count += 1
        elif kind in {"turn.failed", "error"}:
            message = event.get("message") or event.get("error") or kind
            handle.add_error(f"Codex event reported failure: {message}")
        text = None
        item = event.get("item")
        if (kind in {"item.completed", "item.updated"} and isinstance(item, dict)
                and item.get("type") in {"agent_message", "assistant_message"}):
            text = item.get("text") or item.get("message")
        elif kind in {"agent_message", "assistant_message"}:
            text = event.get("text") or event.get("message")
        if isinstance(text, str):
            trimmed = len(text) > LATEST_MESSAGE_LIMIT
            with self.lock:
                self.state["latest_agent_message"] = text[-LATEST_MESSAGE_LIMIT:]
                self.state["latest_agent_message_truncated"] = trimmed
                self.state["updated_at"] = utc_now()
                _atomic_state_write(self.session_dir, self.state)

    def _read_stdout(self, handle: "TurnHandle") -> None:
        stream = handle.process.stdout
        if stream is None:  # Popen was created with stdout=PIPE
            handle.add_error("Codex process provided no event stream")
            return
        try:
            for raw in iter(stream.readline, b""):
                self.event_file.write(raw)
                line = raw.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line.decode("utf-8"))
                    self._record_event(event, handle)
                except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
                    handle.add_error(f"Malformed Codex JSONL event: {error}")
                    with self.lock:
                        self.state["malformed_event_count"] += 1
                        self.state["last_error"] = f"Malformed Codex JSONL event: {error}"
                        self.state["updated_at"] = utc_now()
                        _atomic_state_write(self.session_dir, self.state)
        except OSError as error:
            handle.add_error(f"Cannot read Codex event stream: {error}")
        finally:
            stream.close()
            self.event_file.flush()

    def _write_stdin(self, handle: "TurnHandle", text: str) -> None:
        stream = handle.process.stdin
        if stream is None:  # Popen was created with stdin=PIPE
            handle.add_error("Codex process accepted no prompt stream")
            return
        try:
            stream.write(text.encode("utf-8"))
            stream.flush()
        except (BrokenPipeError, OSError) as error:
            handle.add_error(f"Cannot send prompt to Codex: {error}")
        finally:
            with contextlib.suppress(OSError):
                stream.close()

    def _start_turn(self, text: str, resumed: bool) -> None:
        executable = shutil.which("codex")
        if not executable:
            raise BridgeError("Codex CLI executable was not found on PATH")
        base = [executable, "exec"]
        if resumed:
            thread_id = self.state.get("codex_thread_id")
            if not isinstance(thread_id, str) or not thread_id:
                raise BridgeError("Cannot resume because thread.started did not provide a thread ID")
            base += ["resume", thread_id]
        base += ["--json", "--skip-git-repo-check", "-m", MODEL,
                 "-c", 'model_reasoning_effort="xhigh"',
                 "-c", 'sandbox_mode="danger-full-access"',
                 "-c", 'approval_policy="never"']
        if not resumed:
            base += ["-C", str(self.project)]
        base += ["-"]
        stderr_fd = os.open(self.session_dir / STDERR_NAME, os.O_WRONLY | os.O_APPEND)
        try:
            process = subprocess.Popen(base, cwd=str(self.project), stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE, stderr=stderr_fd,
                                       start_new_session=True, close_fds=True)
        finally:
            os.close(stderr_fd)
        handle = TurnHandle(process, resumed)
        handle.reader = threading.Thread(target=self._read_stdout, args=(handle,), daemon=True)
        handle.writer = threading.Thread(target=self._write_stdin, args=(handle, text), daemon=True)
        handle.reader.start()
        handle.writer.start()

        def wait_for_turn() -> None:
            code = process.wait()
            if handle.reader is not None:
                handle.reader.join()
            if handle.writer is not None:
                handle.writer.join()
            self.completions.put((handle, code))

        handle.waiter = threading.Thread(target=wait_for_turn, daemon=True)
        handle.waiter.start()
        self.child = handle
        with self.lock:
            self.state["phase"] = "running"
            self.state["child_pid"] = process.pid
            self.state["queue_depth"] = len(self.pending)
            self.state["last_error"] = ""
            self.state["updated_at"] = utc_now()
            _atomic_state_write(self.session_dir, self.state)

    def _finish_turn(self, handle: "TurnHandle", return_code: int) -> None:
        if self.child is not handle:
            return
        if self._observe_stop_signal():
            return
        self.child = None
        with self.lock:
            thread_id = self.state.get("codex_thread_id")
        errors = handle.error_list()
        if return_code != 0:
            errors.append(f"Codex exited with status {return_code}")
        if handle.turn_completed_count != 1:
            errors.append("Codex output must contain exactly one turn.completed event; "
                          f"received {handle.turn_completed_count}")
        if not thread_id:
            errors.append("Codex output did not include thread.started with a thread_id")
        if errors:
            discarded = len(self.pending)
            self.pending.clear()
            with self.lock:
                self.state.update({"phase": "failed", "accepting": False,
                                   "child_pid": None, "queue_depth": 0,
                                   "discarded_followups": self.state.get("discarded_followups", 0) + discarded,
                                   "last_error": "; ".join(errors)})
            self._persist()
            return
        with self.lock:
            self.state.update({"phase": "idle", "child_pid": None,
                               "queue_depth": len(self.pending), "last_error": ""})
        self._persist()
        if self.pending and not self.stop_requested:
            self._start_next()

    def _begin_stop(self) -> None:
        if self.stop_requested:
            return
        self.stop_requested = True
        discarded = len(self.pending)
        self.pending.clear()
        with self.lock:
            self.state.update({"accepting": False, "phase": "stopping", "queue_depth": 0,
                               "discarded_followups": self.state.get("discarded_followups", 0) + discarded})
        self._persist()

    def _observe_stop_signal(self) -> bool:
        if (self.signal_requested is not None and self.signal_requested.is_set()
                and not self.stop_requested):
            self._begin_stop()
        return self.stop_requested

    def _start_next(self) -> None:
        if (self._observe_stop_signal() or self.child is not None or not self.pending):
            return
        text = self.pending.popleft()
        self._update(queue_depth=len(self.pending))
        try:
            self._start_turn(text, resumed=True)
        except (OSError, BridgeError) as error:
            discarded = len(self.pending) + 1
            self.pending.clear()
            self._update(phase="failed", accepting=False, child_pid=None, queue_depth=0,
                         discarded_followups=self.state.get("discarded_followups", 0) + discarded,
                         last_error=str(error))

    def _terminate_child(self) -> None:
        handle = self.child
        if handle is None:
            return
        process = handle.process
        if process.poll() is None:
            _signal_group(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                _signal_group(process.pid, signal.SIGKILL)
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    handle.add_error("Codex process group did not exit after SIGKILL")
        if handle.waiter is not None:
            handle.waiter.join(timeout=5)
        self.child = None

    def _handle(self, request: object) -> dict[str, Any]:
        if not isinstance(request, dict):
            return {"ok": False, "error": "Control request must be a JSON object"}
        op = request.get("op")
        self._observe_stop_signal()
        if op == "status":
            return {"ok": True, "state": self._state_reply()}
        if op == "instruct":
            text = request.get("text")
            if not isinstance(text, str) or not text.strip():
                return {"ok": False, "error": "Instruction text must be non-empty"}
            if len(text.encode("utf-8")) > MAX_INSTRUCTION_BYTES:
                return {"ok": False, "error": "Instruction exceeds the 64 KiB limit"}
            with self.lock:
                if not self.state.get("accepting") or self.stop_requested:
                    return {"ok": False, "error": "Session is no longer accepting instructions"}
                if len(self.pending) >= MAX_QUEUE:
                    return {"ok": False, "error": f"Follow-up queue is full (limit {MAX_QUEUE})"}
                self.pending.append(text)
                self.state["queue_depth"] = len(self.pending)
                self.state["updated_at"] = utc_now()
                _atomic_state_write(self.session_dir, self.state)
                phase = self.state.get("phase")
            if phase == "idle" and self.child is None:
                self._start_next()
                if self.stop_requested:
                    return {"ok": False, "error": "Session stopped before the follow-up could start"}
                if self.state.get("phase") == "failed":
                    return {"ok": False, "error": self.state.get("last_error") or "Could not start follow-up"}
            return {"ok": True, "queued": True, "state": self._state_reply()}
        if op == "stop":
            self._begin_stop()
            return {"ok": True, "stopping": True, "state": self._state_reply()}
        return {"ok": False, "error": "Unknown control operation"}

    def _serve_one(self, connection: socket.socket) -> None:
        connection.settimeout(2.0)
        try:
            data = bytearray()
            while len(data) <= MAX_RPC_BYTES:
                chunk = connection.recv(4096)
                if not chunk:
                    break
                data.extend(chunk)
                if b"\n" in data:
                    break
            if len(data) > MAX_RPC_BYTES or b"\n" not in data:
                response = {"ok": False, "error": "Control request is too large or incomplete"}
            else:
                try:
                    request = json.loads(bytes(data).split(b"\n", 1)[0].decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    response = {"ok": False, "error": "Control request is malformed"}
                else:
                    response = self._handle(request)
            encoded = json.dumps(response, ensure_ascii=False).encode("utf-8") + b"\n"
            connection.sendall(encoded)
        except OSError:
            pass
        finally:
            connection.close()

    def run(self) -> None:
        sock_path = self.session_dir / SOCKET_NAME
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server = server
        server.bind(str(sock_path))
        os.chmod(sock_path, 0o600)
        server.listen(8)
        server.setblocking(False)
        try:
            if self._observe_stop_signal():
                self._update(phase="stopped", accepting=False, child_pid=None,
                             queue_depth=0, last_error="")
                return
            self._start_turn(self.initial_prompt, resumed=False)
            self.startup_ready = True
            # Record it: a turn that fails at once also sets phase "failed", so
            # the caller cannot tell startup apart from a fast failure without this.
            self._update(startup_complete=True)
            while True:
                if self._observe_stop_signal():
                    self._terminate_child()
                    self._update(phase="stopped", accepting=False, child_pid=None,
                                 queue_depth=0, last_error="")
                    return
                try:
                    readable, _, _ = select.select([server], [], [], 0.1)
                except InterruptedError:
                    readable = []
                if self._observe_stop_signal():
                    self._terminate_child()
                    self._update(phase="stopped", accepting=False, child_pid=None,
                                 queue_depth=0, last_error="")
                    return
                if readable:
                    try:
                        connection, _ = server.accept()
                    except BlockingIOError:
                        connection = None
                    if connection is not None:
                        self._serve_one(connection)
                while True:
                    if self._observe_stop_signal():
                        break
                    try:
                        handle, code = self.completions.get_nowait()
                    except queue.Empty:
                        break
                    self._finish_turn(handle, code)
                if self.stop_requested:
                    self._terminate_child()
                    self._update(phase="stopped", accepting=False, child_pid=None,
                                 queue_depth=0, last_error="")
                    return
                if self.state.get("phase") == "failed":
                    return
        finally:
            self._terminate_child()
            if self.server is not None:
                self.server.close()
            with contextlib.suppress(FileNotFoundError):
                sock_path.unlink()
            self.event_file.close()


def _supervisor_entry(session_dir: Path, project: Path) -> None:
    supervisor: Supervisor | None = None
    signal_requested = threading.Event()

    def request_stop(_signum: int, _frame: Any) -> None:
        signal_requested.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    try:
        initial_prompt = sys.stdin.buffer.read().decode("utf-8")
        supervisor = Supervisor(session_dir, project, initial_prompt)
        supervisor.signal_requested = signal_requested
        supervisor.run()
    except BaseException as error:  # noqa: BLE001 - a supervisor must report any exit, including signals
        if supervisor is not None:
            try:
                supervisor._terminate_child()
                supervisor._update(phase="failed", accepting=False, child_pid=None,
                                   last_error=f"Supervisor failed: {type(error).__name__}: {error}")
            except BaseException:  # noqa: BLE001, S110 - cleanup must not mask the original failure
                pass
        else:
            try:
                state = _load_state(session_dir)
                state.update({"phase": "failed", "accepting": False,
                              "last_error": f"Supervisor failed: {type(error).__name__}: {error}",
                              "updated_at": utc_now()})
                _atomic_state_write(session_dir, state)
            except BaseException:  # noqa: BLE001, S110 - cleanup must not mask the original failure
                pass
    finally:
        if supervisor is not None:
            try:
                supervisor._terminate_child()
                supervisor.event_file.close()
            except BaseException:  # noqa: BLE001, S110 - cleanup must not mask the original failure
                pass


def _read_events(session_dir: Path) -> dict[str, Any]:
    state = _load_state(session_dir)
    path = Path(state["event_log_path"])
    if path.is_symlink() or not path.is_file():
        raise BridgeError("Session event log is missing or is not a regular file")
    events: list[dict[str, Any]] = []
    with path.open("rb") as stream:
        for number, raw in enumerate(stream, 1):
            try:
                item = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                events.append({"line": number, "malformed": str(error),
                               "raw": raw.decode("utf-8", errors="replace").rstrip("\r\n")})
            else:
                events.append({"line": number, "event": item})
    return {"event_log_path": str(path), "events": events}


def _stop_session(session_dir: Path) -> State:
    try:
        _rpc(session_dir, {"op": "stop"}, timeout=3.0)
    except BridgeError as error:
        state = _load_state(session_dir)
        if state.get("phase") in {"stopped", "failed", "disconnected"}:
            return _public_state(state)
        _mark_disconnected(session_dir, state)
        raise BridgeError(f"Could not deliver stop request: {error}") from error
    deadline = time.monotonic() + SUPERVISOR_SHUTDOWN_TIMEOUT
    while time.monotonic() < deadline:
        try:
            result = _rpc(session_dir, {"op": "status"}, timeout=1.0)
            reported: State = result["state"]
            if reported.get("phase") in {"stopped", "failed"}:
                return reported
        except BridgeError:
            state = _load_state(session_dir)
            if state.get("phase") == "stopped":
                return _public_state(state)
            if state.get("phase") == "failed":
                return _public_state(state)
        time.sleep(0.05)
    raise BridgeError("Timed out waiting for the supervisor to stop Codex")


def _events_command(session_dir: Path) -> None:
    result = _read_events(session_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    start = commands.add_parser("start", help="Start a Coding session for an active ledger task")
    start.add_argument("--project", required=True, type=Path)
    start.add_argument("--task-id", required=True)
    start.add_argument("--store", required=True, type=Path)
    start.add_argument("--request-file", required=True, type=Path,
                       help="UTF-8 file containing the original user request (up to 64 KiB)")
    start.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR)
    for name in ("status", "stop", "events"):
        command = commands.add_parser(name)
        command.add_argument("session")
        command.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR)
    instruct = commands.add_parser("instruct", help="Queue a trusted follow-up instruction")
    instruct.add_argument("session")
    instruct.add_argument("--text", required=True)
    instruct.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR)
    hidden = commands.add_parser("_supervise", help=argparse.SUPPRESS)
    hidden.add_argument("session_dir", type=Path)
    hidden.add_argument("project", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "start":
            print(start_session(args.project, args.task_id, args.store,
                                args.request_file, args.state_dir))
        elif args.command == "_supervise":
            _supervisor_entry(args.session_dir, args.project)
        else:
            session_dir = _task_id_path(args.state_dir, args.session)
            if args.command == "status":
                print(json.dumps(_status(session_dir), ensure_ascii=False, indent=2))
            elif args.command == "instruct":
                result = _rpc(session_dir, {"op": "instruct", "text": args.text})
                print(json.dumps(result["state"], ensure_ascii=False, indent=2))
            elif args.command == "stop":
                print(json.dumps(_stop_session(session_dir), ensure_ascii=False, indent=2))
            elif args.command == "events":
                _events_command(session_dir)
        return 0
    except (BridgeError, OSError, sqlite3.Error) as error:
        print(f"Coding bridge error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
