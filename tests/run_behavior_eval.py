#!/usr/bin/env python3
"""Run one bounded Apex/Codex C++ task, then independently verify its result.

Requires an authenticated Codex CLI and a working C++ compiler. The model may
change only the disposable fixture. No real project or global setting is edited.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from run_apex import host_command

HEADER = """#pragma once
struct Document { int owner_id; int tenant_id; };
inline bool can_read(bool authenticated, int user_id, int tenant_id, Document doc) {
    return authenticated && user_id == doc.owner_id;
}
"""
VISIBLE_TEST = """#include "access.hpp"
#include <cassert>
int main() {
    assert(can_read(true, 7, 10, {7, 10}));
    assert(!can_read(true, 8, 10, {7, 10}));
}
"""
INDEPENDENT_TEST = """#include "access.hpp"
#include <cassert>
int main() {
    for (bool auth : {false, true})
        for (int user : {7, 8})
            for (int tenant : {10, 20})
                for (int owner : {7, 8})
                    for (int document_tenant : {10, 20})
                        assert(can_read(auth, user, tenant, {owner, document_tenant})
                               == (auth && user == owner && tenant == document_tenant));
}
""".replace('#include <cassert>', '#include <cassert>\n#include <initializer_list>')


def run_evaluation(output, host="codex"):
    codex = shutil.which(host)
    compiler = shutil.which("c++")
    if not codex or not compiler:
        raise RuntimeError("The selected host CLI and a C++ compiler are required; environment unchanged.")
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="apex-behavior-") as directory:
        base = Path(directory)
        workspace = base / "workspace"
        workspace.mkdir()
        (workspace / "access.hpp").write_text(HEADER)
        (workspace / "test_access.cpp").write_text(VISIBLE_TEST)
        (workspace / "AGENTS.md").write_text(
            "This is a bounded C++17 bug-fix fixture. Edit only access.hpp and "
            "test_access.cpp. Keep the public signature. Do not install dependencies, "
            "create planning documents, or change any global files. This fixture is not a Git repository. Compile with "
            "c++ -std=c++17 test_access.cpp -o test_access and run ./test_access.\n"
        )
        initial_rules = (workspace / "AGENTS.md").read_bytes()
        hidden = base / "independent.cpp"
        hidden.write_text(INDEPENDENT_TEST)
        oracle = base / "independent-test"
        build = [compiler, "-std=c++17", "-I", str(workspace), str(hidden), "-o", str(oracle)]
        subprocess.run(build, check=True, capture_output=True, text=True)
        baseline = subprocess.run([str(oracle)], capture_output=True)
        if baseline.returncode == 0:
            raise RuntimeError("Invalid fixture: baseline unexpectedly passed.")

        prompt = (
            f"Target project: {workspace}. Work only in this directory; use absolute paths "
            "if a tool defaults to another directory. For this bounded C++ software bug fix: "
            "Document access leaks when tenants have overlapping user IDs. "
            "Authenticated users should read only their own documents in their "
            "current tenant; other access must be denied. Fix access.hpp, add "
            "focused regression coverage in test_access.cpp, and run the relevant "
            "tests. The behavior and scope are approved; implement directly. "
            "State what you actually verified."
        )
        if host == "codex":
            arguments = ["--no-daemon", "-a", "never", "exec", "--ignore-user-config",
                         "--ephemeral", "--skip-git-repo-check", "--sandbox", "workspace-write",
                         "-C", str(workspace), "--json", "-o", str(output / "agent-result.md")]
        elif host == "claude":
            arguments = ["-p", "--output-format", "json", "--no-session-persistence",
                         "--permission-mode", "dontAsk", "--allowedTools",
                         "Read,Edit,Write,Bash(c++ *),Bash(./test_access),Bash(cat *),Bash(pwd),Bash(ls *),Bash(wc *),Bash(cd *),Bash(echo *)"]
        else:
            arguments = ["--standalone", "--format", "json", "--auto"]
        events_path = output / f"{host}-events.jsonl"
        with events_path.open("w") as events, (output / f"{host}-stderr.log").open("w") as errors:
            result = subprocess.run(
                [codex, *host_command(host, prompt, arguments)[1:]],
                cwd=workspace, env={**os.environ, "PWD": str(workspace)},
                stdout=events, stderr=errors, timeout=300,
            )
        if result.returncode:
            raise RuntimeError(f"{host} exited {result.returncode}; see {events_path}.")
        subprocess.run(build, check=True, capture_output=True, text=True)
        subprocess.run([str(oracle)], check=True, capture_output=True)
        if (workspace / "test_access.cpp").read_text() == VISIBLE_TEST:
            raise RuntimeError("Agent did not add regression coverage.")
        visible = base / "visible-test"
        subprocess.run([compiler, "-std=c++17", str(workspace / "test_access.cpp"),
                        "-o", str(visible)], check=True, capture_output=True, text=True)
        subprocess.run([str(visible)], check=True, capture_output=True)
        if (workspace / "AGENTS.md").read_bytes() != initial_rules:
            raise RuntimeError("Agent modified fixture instructions outside scope.")
        unexpected = {p.name for p in workspace.iterdir()} - {
            "access.hpp", "test_access.cpp", "AGENTS.md", "test_access"
        }
        if unexpected:
            raise RuntimeError(f"Unexpected fixture files: {sorted(unexpected)}")
        events = [json.loads(line) for line in events_path.read_text().splitlines() if line.strip()]
        usage = next((event.get("usage", {}) for event in reversed(events)
                      if event.get("type") == "turn.completed"), {})
        if host == "claude":
            final = next((e for e in reversed(events) if e.get("type") == "result"), {})
            if final.get("permission_denials"):
                raise RuntimeError("Claude verification blocked by tool permissions; inspect permission_denials in host events.")
            if final.get("is_error"):
                raise RuntimeError(f"Claude task failed: {final.get('result', '')}")
            usage = final.get("usage", {})
            (output / "agent-result.md").write_text(final.get("result", ""))
        if host == "opencode":
            errors = [event for event in events if event.get("type") == "error"]
            if errors:
                raise RuntimeError("OpenCode reported an error; inspect host events.")
            steps = [event.get("part", {}).get("tokens", {}) for event in events
                     if event.get("type") == "step_finish"]
            usage = {
                "input_tokens": sum(step.get("input", 0) for step in steps),
                "output_tokens": sum(step.get("output", 0) for step in steps),
                "cache_read_tokens": sum(step.get("cache", {}).get("read", 0) for step in steps),
                "cache_write_tokens": sum(step.get("cache", {}).get("write", 0) for step in steps),
            }
            (output / "agent-result.md").write_text("\n\n".join(
                event.get("part", {}).get("text", "") for event in events if event.get("type") == "text"
            ))
        commands = [event["item"] for event in events
                    if event.get("type") == "item.completed"
                    and event.get("item", {}).get("type") == "command_execution"]
        for name in ("access.hpp", "test_access.cpp"):
            shutil.copyfile(workspace / name, output / name)
        report = {
            "baseline": "failed as expected",
            "usage": usage,
            "uncached_input_tokens": (usage.get("input_tokens", 0) - usage.get("cached_input_tokens", 0)) if host == "codex" else None,
            "execution_mode": f"run_apex.py {host} session; explicit Apex entry point",
            "cli_version": subprocess.run([codex, "--version"], capture_output=True, text=True, check=True).stdout.strip(),
            "command_count": len(commands) if host == "codex" else None,
            "failed_commands": sum(command.get("exit_code", 0) != 0 for command in commands) if host == "codex" else None,
            "fixture_scope": "passed; instructions preserved and no unexpected top-level files",
            "measurement_limit": "Single run; cumulative usage includes cached context and host instructions. Not a billing or causal benchmark.",
            "independent_access_cases": 32,
            "independent_result": "passed",
            "agent_regression_tests": "added and passed",
            "fixed_source_sha256": hashlib.sha256((workspace / "access.hpp").read_bytes()).hexdigest(),
            "scope": "one C++ tenant-authorization fixture; not a benchmark of every supported stack",
            "module_use": f"inspect {host}-events.jsonl for available host evidence",
        }
        (output / "result.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--host", choices=("codex", "claude", "opencode"), default="codex")
    args = parser.parse_args()
    run_evaluation(args.output.resolve(), args.host)
