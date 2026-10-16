#!/usr/bin/env python3
"""Persistent local task ledger. No commands or agents are executed by this tool."""

import argparse
from contextlib import closing, contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import uuid


ROLES = ("Engineering", "Coding", "Test", "Security")
TERMINAL = {"completed", "cancelled"}
TRANSITIONS = {
    "start": ({"queued"}, "active"),
    "review": ({"active"}, "review"),
    "block": ({"queued", "active", "review"}, "blocked"),
    "pause": ({"queued", "active", "review", "blocked"}, "paused"),
    "resume": ({"blocked", "paused"}, "queued"),
    "rework": ({"review"}, "active"),
    "complete": ({"review"}, "completed"),
    "cancel": ({"queued", "active", "review", "blocked", "paused"}, "cancelled"),
}


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def required(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")
    return value.strip()


def file_hash(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class Ledger:
    def __init__(self, path):
        self.path = Path(path).absolute()

    def initialize(self):
        # Explicit initialization only. Never create a ledger during read commands.
        if self.path.exists() or self.path.is_symlink():
            raise ValueError("Ledger path already exists; it will not be replaced")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(descriptor)
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("CREATE TABLE tasks (id TEXT PRIMARY KEY, body TEXT NOT NULL)")
            db.execute("PRAGMA user_version=1")
            db.commit()

    @contextmanager
    def connection(self, write=False):
        if not self.path.is_file() or self.path.is_symlink():
            raise ValueError("Ledger missing or symlinked; initialize an explicit regular file")
        uri = self.path.as_uri() + ("?mode=rw" if write else "?mode=ro")
        db = sqlite3.connect(uri, uri=True, timeout=10)
        try:
            if db.execute("PRAGMA user_version").fetchone()[0] != 1:
                raise ValueError("Unsupported ledger version; no migration attempted")
            db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def get(db, task_id):
        row = db.execute("SELECT body FROM tasks WHERE id=?", (task_id,)).fetchone()
        if row is None:
            raise ValueError(f"Unknown task: {task_id}")
        return json.loads(row[0])

    @staticmethod
    def save(db, task, event, details):
        task["updated_at"] = timestamp()
        task["history"].append({"at": task["updated_at"], "event": event, "details": details})
        db.execute("INSERT OR REPLACE INTO tasks VALUES (?, ?)",
                   (task["id"], json.dumps(task, ensure_ascii=False)))
        return task

    def create(self, project, title, scope, criteria, role="Engineering", dependencies=()):
        if role not in ROLES:
            raise ValueError("Unknown role")
        project = required(project, "project")
        title, scope = required(title, "title"), required(scope, "scope")
        if not criteria:
            raise ValueError("At least one acceptance criterion is required")
        criteria = [required(c, "criterion") for c in criteria]
        if len(set(criteria)) != len(criteria):
            raise ValueError("Acceptance criteria must be unique")
        with self.connection(True) as db:
            deps = list(dict.fromkeys(dependencies))
            for dep in deps:
                existing = self.get(db, dep)
                if existing["project"] != project or existing["state"] == "cancelled":
                    raise ValueError("Dependencies must be uncancelled tasks in the same project")
            now = timestamp()
            task = {"id": "APX-" + uuid.uuid4().hex, "project": project, "title": title,
                    "scope": scope, "role": role, "dependencies": deps, "state": "queued",
                    "criteria": [{"id": str(i + 1), "text": text} for i, text in enumerate(criteria)],
                    "evidence": {}, "reason": "", "created_at": now, "updated_at": now,
                    "history": []}
            return self.save(db, task, "created", {"role": role})

    def list(self, project=None, ready=False):
        with self.connection() as db:
            tasks = [json.loads(row[0]) for row in db.execute("SELECT body FROM tasks ORDER BY rowid")]
            states = {t["id"]: t["state"] for t in tasks}
            return [t for t in tasks if (project is None or t["project"] == project)
                    and (not ready or (t["state"] == "queued"
                         and all(states.get(d) == "completed" for d in t["dependencies"])))]

    def show(self, task_id):
        with self.connection() as db:
            return self.get(db, task_id)

    def assign(self, task_id, role, reason):
        if role not in ROLES:
            raise ValueError("Unknown role")
        reason = required(reason, "reason")
        with self.connection(True) as db:
            task = self.get(db, task_id)
            if task["state"] not in {"queued", "blocked", "paused"}:
                raise ValueError("Assign only queued, blocked, or paused tasks")
            task["role"] = role
            return self.save(db, task, "assigned", {"role": role, "reason": reason})

    def transition(self, task_id, action, reason=""):
        if action not in TRANSITIONS:
            raise ValueError("Unknown transition")
        if action in {"block", "pause", "resume", "rework", "cancel"}:
            reason = required(reason, "reason")
        with self.connection(True) as db:
            task = self.get(db, task_id)
            allowed, target = TRANSITIONS[action]
            if task["state"] not in allowed:
                raise ValueError(f"Cannot {action} a {task['state']} task")
            if action in {"start", "complete"}:
                if any(self.get(db, dep)["state"] != "completed" for dep in task["dependencies"]):
                    raise ValueError("Dependencies are not completed")
            if action == "complete":
                for criterion in task["criteria"]:
                    evidence = task["evidence"].get(criterion["id"])
                    if not evidence or evidence["result"] != "pass":
                        raise ValueError("Every acceptance criterion requires passing evidence")
                    path = Path(evidence["path"])
                    if not path.is_file() or file_hash(path) != evidence["sha256"]:
                        raise ValueError("Evidence file is missing or changed; verify again")
            if action in {"start", "rework", "resume"}:
                task["evidence"] = {}
            task["state"], task["reason"] = target, reason
            return self.save(db, task, action, {"reason": reason})

    def evidence(self, task_id, criterion, result, path, summary, reviewer):
        if result not in {"pass", "fail"} or reviewer not in {"Test", "Security"}:
            raise ValueError("Evidence requires pass/fail and Test or Security reviewer role")
        summary = required(summary, "summary")
        path = Path(path).resolve(strict=True)
        if not path.is_file():
            raise ValueError("Evidence must be a regular file")
        evidence = {"result": result, "path": str(path), "sha256": file_hash(path),
                    "summary": summary, "reviewer": reviewer, "at": timestamp()}
        with self.connection(True) as db:
            task = self.get(db, task_id)
            if task["state"] != "review":
                raise ValueError("Record evidence only during review")
            if criterion not in {c["id"] for c in task["criteria"]}:
                raise ValueError("Unknown acceptance criterion")
            task["evidence"][criterion] = evidence
            return self.save(db, task, "evidence", {"criterion": criterion, **evidence})

    def export(self, destination, project=None):
        destination = Path(destination).absolute()
        marker = "<!-- apex-task-board:v1 -->"
        if destination == self.path or destination.is_symlink():
            raise ValueError("Unsafe board destination")
        if destination.exists() and not destination.read_text().startswith(marker + "\n"):
            raise ValueError("Refusing to replace an unowned note")
        def literal(value):
            # Render user text literally rather than letting it create links/headings/HTML.
            value = str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            for char in "\\`*_{}[]()#+-.!|":
                value = value.replace(char, "\\" + char)
            return value.replace("\n", " ")
        lines = [marker, "# Apex task board", "", "Generated view; edit tasks through the ledger CLI.",
                 "Recorded roles/evidence are assertions, not authenticated approvals.",
                 "", "Snapshot UTC: " + timestamp(), ""]
        for task in self.list(project):
            lines += ["## " + literal(task["title"]), "", f"ID: {task['id']}", "",
                      "Project: " + literal(task["project"]), "",
                      f"State: {task['state']} | Role: {task['role']}", "",
                      "Scope: " + literal(task["scope"]), "",
                      "Dependencies: " + (", ".join(task["dependencies"]) or "none"), "",
                      "Reason: " + literal(task["reason"] or "none"), ""]
            for criterion in task["criteria"]:
                e = task["evidence"].get(criterion["id"])
                lines.append(f"- {criterion['id']}: {literal(criterion['text'])} — "
                             + (e["result"] + ": " + literal(e["summary"]) if e else "unverified"))
                if e:
                    lines.append("  Evidence: " + literal(e["path"]) + "; SHA256: " + e["sha256"])
            lines += ["", "Updated UTC: " + task["updated_at"], ""]
        destination.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=".apex-board-", dir=destination.parent)
        try:
            with os.fdopen(fd, "w") as stream:
                stream.write("\n".join(lines) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, destination)
        finally:
            if os.path.exists(name):
                os.unlink(name)
        return {"board": str(destination), "synchronized": "snapshot only"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", required=True, type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init")
    create = commands.add_parser("create")
    for name in ("project", "title", "scope"):
        create.add_argument("--" + name, required=True)
    create.add_argument("--criterion", action="append", required=True)
    create.add_argument("--role", choices=ROLES, default="Engineering")
    create.add_argument("--depends-on", action="append", default=[])
    listing = commands.add_parser("list")
    listing.add_argument("--project")
    listing.add_argument("--ready", action="store_true")
    show = commands.add_parser("show")
    show.add_argument("id")
    assign = commands.add_parser("assign")
    assign.add_argument("id")
    assign.add_argument("--role", choices=ROLES, required=True)
    assign.add_argument("--reason", required=True)
    for name in TRANSITIONS:
        sub = commands.add_parser(name)
        sub.add_argument("id")
        sub.add_argument("--reason", default="")
    evidence = commands.add_parser("evidence")
    evidence.add_argument("id")
    evidence.add_argument("--criterion", required=True)
    evidence.add_argument("--result", choices=("pass", "fail"), required=True)
    evidence.add_argument("--file", type=Path, required=True)
    evidence.add_argument("--summary", required=True)
    evidence.add_argument("--reviewer", choices=("Test", "Security"), required=True)
    export = commands.add_parser("export")
    export.add_argument("--output", type=Path, required=True)
    export.add_argument("--project")
    args = parser.parse_args()
    ledger = Ledger(args.store)
    try:
        if args.command == "init":
            ledger.initialize()
            result = {"store": str(ledger.path)}
        elif args.command == "create":
            result = ledger.create(args.project, args.title, args.scope, args.criterion,
                                   args.role, args.depends_on)
        elif args.command == "list":
            result = ledger.list(args.project, args.ready)
        elif args.command == "show":
            result = ledger.show(args.id)
        elif args.command == "assign":
            result = ledger.assign(args.id, args.role, args.reason)
        elif args.command == "evidence":
            result = ledger.evidence(args.id, args.criterion, args.result, args.file,
                                     args.summary, args.reviewer)
        elif args.command == "export":
            result = ledger.export(args.output, args.project)
        else:
            result = ledger.transition(args.id, args.command, args.reason)
    except (ValueError, OSError, sqlite3.Error) as error:
        parser.exit(1, f"Task error: {error}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
