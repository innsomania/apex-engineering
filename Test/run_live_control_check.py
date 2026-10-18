#!/usr/bin/env python3
"""End-to-end check that the three Apex controls fire in a real project.

The suites in test_verify_hook.py check the hook's branches. This drives the
whole lifecycle instead: it builds a disposable git project, turns the controls
on through apex_project.py, and then calls the hook exactly as Claude Code
does, in order, asserting what the user would actually observe.

It runs no model and needs no network. Usage:

    python3 Test/run_live_control_check.py --output artifacts/live-controls.json
"""

import argparse
import json
import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "Claude" / "hooks" / "apex_verify_hook.py"
PROJECT_CLI = ROOT / "Claude" / "apex_project.py"
SESSION = "live-check"


class CheckFailure(AssertionError):
    pass


class Harness:
    def __init__(self, base: Path) -> None:
        self.project = base / "project"
        self.state = base / "hook-state"
        self.transcripts = base / "transcripts"
        self.project.mkdir()
        self.transcripts.mkdir()
        self.observations: list[dict[str, Any]] = []

    # --- project under test -------------------------------------------------

    def build_project(self) -> None:
        """A small project whose real verify command is its own test suite."""
        (self.project / "src").mkdir()
        (self.project / "tests").mkdir()
        (self.project / "src" / "__init__.py").write_text("")
        (self.project / "tests" / "__init__.py").write_text("")
        (self.project / "src" / "calc.py").write_text(
            "def total(items):\n"
            '    """Sum the items, treating None as zero."""\n'
            "    return sum(item or 0 for item in items)\n")
        (self.project / "tests" / "test_calc.py").write_text(
            "import unittest\n\n"
            "from src.calc import total\n\n\n"
            "class TotalTests(unittest.TestCase):\n"
            "    def test_skips_none(self):\n"
            "        self.assertEqual(total([1, None, 2]), 3)\n")
        (self.project / "README.md").write_text("# Disposable project\n")

    def enable_controls(self) -> dict[str, Any]:
        """Turn the controls on the way a user is told to: through the CLI."""
        # stdlib unittest, so the check needs nothing installed to run anywhere.
        verify = f"{shlex.quote(sys.executable)} -m unittest discover -s tests -t ."
        result = subprocess.run(
            [sys.executable, str(PROJECT_CLI), "init", "--root", str(self.project),
             "--allow", "src/", "--allow", "tests/", "--verify", verify],
            capture_output=True, text=True, timeout=300, check=False)
        if result.returncode != 0:
            raise CheckFailure(f"apex_project.py init failed:\n{result.stdout}\n{result.stderr}")
        report: dict[str, Any] = json.loads(result.stdout)
        (self.project / ".apex" / "review.json").write_text("{}\n")
        return report

    # --- calling the hook the way Claude Code does --------------------------

    def hook(self, mode: str, **event: Any) -> dict[str, Any] | None:
        event.setdefault("session_id", SESSION)
        event.setdefault("cwd", str(self.project))
        env = {**os.environ, "APEX_HOOK_STATE_DIR": str(self.state)}
        result = subprocess.run(
            [sys.executable, str(HOOK), mode], input=json.dumps(event),
            capture_output=True, text=True, timeout=600, check=False, env=env)
        if result.returncode != 0:
            raise CheckFailure(f"hook {mode} exited {result.returncode}: {result.stderr}")
        return json.loads(result.stdout) if result.stdout.strip() else None

    def reviewer_transcript(self, verdict: str, report: str) -> str:
        """A reviewer subagent transcript in the JSONL shape the hook reads."""
        path = self.transcripts / f"reviewer-{verdict.lower()}.jsonl"
        path.write_text(json.dumps({
            "message": {"role": "assistant",
                        "content": [{"type": "text",
                                     "text": f"{report}\n\nAPEX-REVIEW: {verdict}"}]}}) + "\n")
        return str(path)

    def shell(self, *args: str) -> None:
        subprocess.run(args, cwd=self.project, capture_output=True, check=True, timeout=120)

    # --- assertions ---------------------------------------------------------

    def record(self, step: str, expected: str, observed: dict[str, Any] | None, ok: bool) -> None:
        self.observations.append({"step": step, "expected": expected, "passed": ok,
                                  "observed": observed})
        print(f"  {'PASS' if ok else 'FAIL'}  {step}")
        if not ok:
            print(f"        beklenen: {expected}")
            print(f"        gozlenen: {json.dumps(observed, ensure_ascii=False)[:600]}")

    def expect_blocked(self, step: str, observed: dict[str, Any] | None, *,
                       contains: str | tuple[str, ...] = ()) -> bool:
        """Every fragment must appear, so another gate's block cannot satisfy this.

        Naming only the changed file was not enough: when the scope sweep was
        disabled, the review gate blocked instead and listed the same file in
        its own message, which looked like a pass.
        """
        wanted = (contains,) if isinstance(contains, str) else contains
        seen = observed or {}
        reason: str = seen.get("reason", "")
        ok = (bool(observed) and seen.get("decision") == "block"
              and all(fragment in reason for fragment in wanted))
        self.record(step, f"decision=block, reason contains all of {list(wanted)}",
                    observed, ok)
        return ok

    def expect_denied(self, step: str, observed: dict[str, Any] | None, *,
                      contains: str = "") -> bool:
        out = (observed or {}).get("hookSpecificOutput", {})
        reason: str = out.get("permissionDecisionReason", "")
        ok = out.get("permissionDecision") == "deny" and contains in reason
        self.record(step, f'permissionDecision=deny, reason contains "{contains}"', observed, ok)
        return ok

    def expect_allowed(self, step: str, observed: dict[str, Any] | None) -> bool:
        out = (observed or {}).get("hookSpecificOutput", {})
        ok: bool = out.get("permissionDecision") != "deny"
        self.record(step, "no denial", observed, ok)
        return ok

    def expect_turn_may_end(self, step: str, observed: dict[str, Any] | None) -> bool:
        """No block, and not the release the hook grants after MAX_ATTEMPTS.

        Both look like an unblocked turn, so an earlier version of this check
        reported a pass when the only reason nothing blocked was that the hook
        had given up on a verify command that could never succeed.
        """
        gave_up = "still failing after" in (observed or {}).get("systemMessage", "")
        ok = (observed or {}).get("decision") != "block" and not gave_up
        self.record(step, "no block, and no give-up notice", observed, ok)
        return ok


def run(base: Path) -> dict[str, Any]:
    h = Harness(base)
    h.build_project()

    print("\n1. Kontrolleri ac (apex_project.py init, gercek pytest komutuyla)")
    report = h.enable_controls()
    ok = report["verify_exit_code"] == 0
    h.record("init runs the real verify command and reports its exit code",
             "verify_exit_code=0", {"verify_exit_code": report["verify_exit_code"]}, ok)
    h.record("init records the approved scope", "allow=['src/', 'tests/']",
             {"allow": report["allow"]}, report["allow"] == ["src/", "tests/"])

    print("\n2. Tur basliyor (UserPromptSubmit)")
    h.hook("baseline", prompt="Make total() ignore negative numbers.")

    print("\n3. scope: duzenleme izinleri")
    h.expect_allowed("an in-scope file may be edited",
                     h.hook("guard", tool_input={"file_path": "src/calc.py"}))
    h.expect_denied("an out-of-scope file is refused",
                    h.hook("guard", tool_input={"file_path": "README.md"}),
                    contains="outside the approved scope")
    h.expect_denied("the user's own control file is refused",
                    h.hook("guard", tool_input={"file_path": ".apex/verify.json"}),
                    contains="only the user changes it")

    print("\n4. verify: basarisiz birakilan testle tur bitemez")
    (h.project / "src" / "calc.py").write_text(
        "def total(items):\n"
        '    """Sum the items, treating None as zero."""\n'
        "    return sum(item or 0 for item in items) + 1  # deliberate defect\n")
    h.expect_blocked("a failing verify blocks the stop and counts the attempt",
                     h.hook("stop", hook_event_name="Stop"),
                     contains=("attempt 1/3", "Verification", "exited with"))

    print("\n5. verify geciyor ama review borclu")
    (h.project / "src" / "calc.py").write_text(
        "def total(items):\n"
        '    """Sum the items, ignoring None and negatives."""\n'
        "    return sum(item for item in items if item and item > 0)\n")
    h.expect_blocked("a passing verify still requires the independent review",
                     h.hook("stop", hook_event_name="Stop"),
                     contains=("apex-reviewer", "Instructions file:"))

    print("\n6. review: FAIL verdikten sonra tur bitemez")
    h.hook("stop", hook_event_name="SubagentStop", agent_type="apex-reviewer",
           agent_transcript_path=h.reviewer_transcript(
               "FAIL", "The change also drops None handling the user asked to keep."))
    h.expect_blocked("a failing review blocks the stop and reports the finding",
                     h.hook("stop", hook_event_name="Stop"),
                     contains=("deviations from the user's instructions",
                               "drops None handling"))

    print("\n7. review: PASS verdikten sonra tur bitebilir")
    h.hook("stop", hook_event_name="SubagentStop", agent_type="apex-reviewer",
           agent_transcript_path=h.reviewer_transcript("PASS", "Matches the request."))
    h.expect_turn_may_end("a passing review lets the turn end",
                          h.hook("stop", hook_event_name="Stop"))

    print("\n8. scope kacisi: kabuktan yapilan degisiklik de yakalanmali")
    h.hook("baseline", prompt="Tidy the documentation.")
    h.shell("git", "checkout", "-q", "--", ".")
    (h.project / "ESCAPED.md").write_text("written past the edit guard\n")
    h.expect_blocked("a shell write outside the scope blocks the stop",
                     h.hook("stop", hook_event_name="Stop"),
                     contains=("outside the approved scope", "ESCAPED.md"))
    (h.project / "ESCAPED.md").unlink()

    print("\n9. soru kilidi: soru soran turda dosya duzenlenemez")
    h.hook("baseline", prompt="Bu fonksiyon neden None'i atliyor?")
    h.expect_denied("edits are locked for a question turn",
                    h.hook("guard", tool_input={"file_path": "src/calc.py"}),
                    contains="blocked for this turn")
    h.hook("baseline", prompt="Now make that change.")
    h.expect_allowed("the lock clears on the next working prompt",
                     h.hook("guard", tool_input={"file_path": "src/calc.py"}))

    passed = sum(1 for o in h.observations if o["passed"])
    return {"checks": len(h.observations), "passed": passed,
            "python": sys.version.split()[0], "observations": h.observations}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=Path, help="write the observations as JSON")
    args = parser.parse_args(argv)
    if args.output and args.output.exists():
        print(f"{args.output} already exists; choose a new path.", file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory(prefix="apex-live-") as temp:
        result = run(Path(temp))

    print(f"\n{result['passed']}/{result['checks']} kontrol gecti")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        print(f"kanit: {args.output}")
    return 0 if result["passed"] == result["checks"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
