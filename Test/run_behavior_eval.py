#!/usr/bin/env python3
"""Run one bounded Apex/Codex C++ task, then independently verify its result.

Requires an authenticated Codex CLI and a working C++ compiler. The model may
change only the disposable fixture. No real project or global setting is edited.
"""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile


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


def run_evaluation(output):
    codex = shutil.which("codex")
    compiler = shutil.which("c++")
    if not codex or not compiler:
        raise RuntimeError("Codex CLI and a C++ compiler are required; environment unchanged.")
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
            "create planning documents, or change any global files. Compile with "
            "c++ -std=c++17 test_access.cpp -o test_access and run ./test_access.\n"
        )
        hidden = base / "independent.cpp"
        hidden.write_text(INDEPENDENT_TEST)
        oracle = base / "independent-test"
        build = [compiler, "-std=c++17", "-I", str(workspace), str(hidden), "-o", str(oracle)]
        subprocess.run(build, check=True, capture_output=True, text=True)
        baseline = subprocess.run([str(oracle)], capture_output=True)
        if baseline.returncode == 0:
            raise RuntimeError("Invalid fixture: baseline unexpectedly passed.")

        prompt = (
            "Use $apex-engineering for this bounded C++ software bug fix. "
            "Document access leaks when tenants have overlapping user IDs. "
            "Authenticated users should read only their own documents in their "
            "current tenant; other access must be denied. Fix access.hpp, add "
            "focused regression coverage in test_access.cpp, and run the relevant "
            "tests. The behavior and scope are approved; implement directly. "
            "Use the applicable Apex Engineering, Coding, Security, and Test "
            "references and state what you actually verified."
        )
        events_path = output / "codex-events.jsonl"
        with events_path.open("w") as events, (output / "codex-stderr.log").open("w") as errors:
            result = subprocess.run(
                [codex, "--no-daemon", "-a", "never", "exec", "--ignore-user-config",
                 "--ephemeral", "--skip-git-repo-check", "--sandbox", "workspace-write",
                 "-C", str(workspace), "--json", "-o", str(output / "agent-result.md"), prompt],
                stdout=events, stderr=errors, timeout=300,
            )
        if result.returncode:
            raise RuntimeError(f"Codex exited {result.returncode}; see {events_path}.")
        subprocess.run(build, check=True, capture_output=True, text=True)
        subprocess.run([str(oracle)], check=True, capture_output=True)
        if (workspace / "test_access.cpp").read_text() == VISIBLE_TEST:
            raise RuntimeError("Agent did not add regression coverage.")
        visible = base / "visible-test"
        subprocess.run([compiler, "-std=c++17", str(workspace / "test_access.cpp"),
                        "-o", str(visible)], check=True, capture_output=True, text=True)
        subprocess.run([str(visible)], check=True, capture_output=True)
        for name in ("access.hpp", "test_access.cpp"):
            shutil.copyfile(workspace / name, output / name)
        report = {
            "baseline": "failed as expected",
            "independent_access_cases": 32,
            "independent_result": "passed",
            "agent_regression_tests": "added and passed",
            "fixed_source_sha256": hashlib.sha256((workspace / "access.hpp").read_bytes()).hexdigest(),
            "scope": "one C++ tenant-authorization fixture; not a benchmark of every supported stack",
            "module_use": "inspect codex-events.jsonl command events for reference reads",
        }
        (output / "result.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run_evaluation(args.output.resolve())
