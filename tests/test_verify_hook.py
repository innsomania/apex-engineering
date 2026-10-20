"""Verification hook checks run against disposable git projects only."""

import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "controls" / "claude-code" / "hooks" / "apex_verify_hook.py"


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
            # The hook runs this through a shell, and the interpreter's path can contain spaces.
            json.dumps({"command": f"{shlex.quote(sys.executable)} check.py", "timeout": 60}))

    def git_init(self):
        for args in (["init", "-q"], ["add", "-A"],
                     ["-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qm", "base"]):
            subprocess.run(["git", *args], cwd=self.project, check=True)

    def hook(self, mode, **event):
        event.setdefault("session_id", "s1")
        event.setdefault("cwd", str(self.project))
        env = {**os.environ, "APEX_HOOK_STATE_DIR": str(self.state)}
        if "_home" in event:
            env["HOME"] = event.pop("_home")
        result = subprocess.run([sys.executable, str(HOOK), mode], input=json.dumps(event),
                                capture_output=True, text=True, timeout=60, env=env)
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
        (self.project / ".apex" / "verify.json").write_text("{}")
        self.git_init()
        self.hook("baseline", hook_event_name="UserPromptSubmit")
        (self.project / "value.txt").write_text("changed\n")
        result = self.hook("stop", hook_event_name="Stop")
        self.assertNotIn("decision", result)
        self.assertIn('"command"', result["systemMessage"])

    def scope(self, *allow):
        (self.project / ".apex" / "scope.json").write_text(json.dumps({"allow": list(allow)}))

    def edit(self, target):
        return self.hook("guard", hook_event_name="PreToolUse", tool_name="Edit",
                         tool_input={"file_path": target})

    def test_guard_enforces_scope_patterns(self):
        self.scope("src/", "README.md", "tests/*.py")
        (self.project / "src").mkdir()
        self.assertIsNone(self.edit(str(self.project / "src" / "deep" / "app.js")))
        self.assertIsNone(self.edit("README.md"))
        self.assertIsNone(self.edit(str(self.project / "tests" / "test_app.py")))
        for target in ("value.txt", "srcx/file.js", str(Path(self.temp.name) / "outside.txt"),
                       ".apex/scope.json"):
            result = self.edit(target if target.startswith("/") else str(self.project / target))
            self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny", target)

    def test_guard_allows_claude_code_plan_and_memory_files(self):
        self.scope("src/")
        home = Path(self.temp.name) / "home"
        for target in (home / ".claude" / "plans" / "plan.md",
                       home / ".claude" / "projects" / "p" / "memory" / "note.md"):
            self.assertIsNone(self.hook("guard", hook_event_name="PreToolUse", tool_name="Write",
                                        tool_input={"file_path": str(target)}, _home=str(home)), target)
        denied = self.hook("guard", hook_event_name="PreToolUse", tool_name="Write",
                           tool_input={"file_path": str(home / ".claude" / "settings.json")}, _home=str(home))
        self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_shell_change_outside_scope_blocks_stop(self):
        self.scope("src/")
        (self.project / "src").mkdir()
        self.git_init()
        self.hook("baseline", hook_event_name="UserPromptSubmit")
        (self.project / "src" / "app.js").write_text("ok\n")
        (self.project / "value.txt").write_text("ok\nextra line from a shell command\n")
        result = self.hook("stop", hook_event_name="Stop")
        self.assertEqual(result["decision"], "block")
        self.assertIn("- value.txt", result["reason"])
        self.assertNotIn("src/app.js", result["reason"])
        self.assertEqual(self.run_count(), 0)
        subprocess.run(["git", "checkout", "--", "value.txt"], cwd=self.project, check=True)
        self.assertIsNone(self.hook("stop", hook_event_name="Stop", stop_hook_active=True))
        self.assertEqual(self.run_count(), 1)

    def test_preexisting_dirty_files_are_not_blamed_on_the_turn(self):
        self.scope("src/")
        self.git_init()
        (self.project / "value.txt").write_text("ok\n\n")  # user's own uncommitted edit
        self.hook("baseline", hook_event_name="UserPromptSubmit")
        (self.project / "src").mkdir()
        (self.project / "src" / "new.js").write_text("x\n")
        self.assertIsNone(self.hook("stop", hook_event_name="Stop"))

    def test_committed_change_outside_scope_is_caught(self):
        self.scope("src/")
        self.git_init()
        self.hook("baseline", hook_event_name="UserPromptSubmit")
        (self.project / "notes.md").write_text("sneaky\n")
        for args in (["add", "notes.md"],
                     ["-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qm", "x"]):
            subprocess.run(["git", *args], cwd=self.project, check=True)
        self.assertIn("- notes.md", self.hook("stop", hook_event_name="Stop")["reason"])

    def test_scope_without_verify_config_runs_no_check(self):
        (self.project / ".apex" / "verify.json").unlink()
        self.scope("src/")
        (self.project / "src").mkdir()
        self.git_init()
        self.hook("baseline", hook_event_name="UserPromptSubmit")
        (self.project / "src" / "app.js").write_text("ok\n")
        self.assertIsNone(self.hook("stop", hook_event_name="Stop"))
        self.assertEqual(self.run_count(), 0)

    def tamper_project(self, value="broken"):
        """A project with a scope and a baseline taken before the turn; its check fails by default."""
        self.scope("src/")
        (self.project / "src").mkdir()
        (self.project / "value.txt").write_text(f"{value}\n")
        (self.project / "notes.txt").write_text("notes\n")
        self.git_init()
        self.hook("baseline", hook_event_name="UserPromptSubmit")

    def test_rewriting_the_verify_config_from_a_shell_blocks_stop(self):
        self.tamper_project()
        (self.project / ".apex" / "verify.json").write_text(json.dumps({"command": "true"}))
        result = self.hook("stop", hook_event_name="Stop")
        self.assertEqual(result["decision"], "block")
        self.assertIn(".apex/verify.json", result["reason"])
        self.assertEqual(self.run_count(), 0)
        subprocess.run(["git", "checkout", "--", ".apex"], cwd=self.project, check=True)
        self.assertIsNone(self.hook("stop", hook_event_name="Stop"))  # restored: nothing changed this turn
        (self.project / "src" / "app.js").write_text("x\n")
        self.assertIn("value is wrong", self.hook("stop", hook_event_name="Stop")["reason"])

    def test_widening_the_scope_from_a_shell_blocks_stop(self):
        self.tamper_project()
        (self.project / ".apex" / "scope.json").write_text(json.dumps({"allow": ["src/", "value.txt"]}))
        (self.project / "value.txt").write_text("ok\n")
        result = self.hook("stop", hook_event_name="Stop")
        self.assertEqual(result["decision"], "block")
        self.assertIn(".apex/scope.json", result["reason"])

    def test_creating_a_review_config_from_a_shell_blocks_stop(self):
        self.tamper_project()
        (self.project / ".apex" / "review.json").write_text("{}")
        self.assertIn(".apex/review.json", self.hook("stop", hook_event_name="Stop")["reason"])

    def test_deleting_the_controls_from_a_shell_blocks_stop(self):
        self.tamper_project()
        shutil.rmtree(self.project / ".apex")
        (self.project / "value.txt").write_text("ok\n")
        result = self.hook("stop", hook_event_name="Stop")
        self.assertEqual(result["decision"], "block")
        self.assertIn(".apex/verify.json", result["reason"])
        subprocess.run(["git", "checkout", "--", ".apex"], cwd=self.project, check=True)
        self.assertEqual(self.hook("stop", hook_event_name="Stop")["decision"], "block")

    def test_controls_removed_between_turns_are_the_users_choice(self):
        self.tamper_project()
        shutil.rmtree(self.project / ".apex")
        self.hook("baseline", hook_event_name="UserPromptSubmit")
        self.assertIsNone(self.hook("stop", hook_event_name="Stop"))

    def test_controls_the_user_edits_between_turns_are_accepted(self):
        self.tamper_project()
        self.scope("src/", "value.txt")
        self.hook("baseline", hook_event_name="UserPromptSubmit")
        (self.project / "value.txt").write_text("ok\n")
        self.assertIsNone(self.hook("stop", hook_event_name="Stop"))

    def test_controls_are_watched_without_git(self):
        self.scope("src/")
        self.hook("baseline", hook_event_name="UserPromptSubmit")
        (self.project / ".apex" / "verify.json").write_text(json.dumps({"command": "true"}))
        self.assertIn(".apex/verify.json", self.hook("stop", hook_event_name="Stop")["reason"])

    def test_renaming_a_file_out_of_the_scope_is_caught(self):
        self.tamper_project("ok")
        subprocess.run(["git", "mv", "notes.txt", "src/notes.txt"], cwd=self.project, check=True)
        result = self.hook("stop", hook_event_name="Stop")
        self.assertEqual(result["decision"], "block")
        self.assertIn("- notes.txt", result["reason"])
        self.assertEqual(self.run_count(), 0)

    def test_committing_a_rename_out_of_the_scope_is_caught(self):
        self.tamper_project("ok")
        subprocess.run(["git", "mv", "notes.txt", "src/notes.txt"], cwd=self.project, check=True)
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@e", "commit", "-qm", "mv"],
                       cwd=self.project, check=True)
        result = self.hook("stop", hook_event_name="Stop")
        self.assertEqual(result["decision"], "block")
        self.assertIn("- notes.txt", result["reason"])
        self.assertEqual(self.run_count(), 0)

    def reviewer_transcript(self, *messages):
        path = Path(self.temp.name) / f"reviewer-{len(list(Path(self.temp.name).glob('reviewer-*')))}.jsonl"
        lines = [{"type": "user", "message": {"role": "user", "content": "review"}}]
        for kind, text in messages:
            item = ({"type": "text", "text": text} if kind == "text"
                    else {"type": "tool_use", "name": "SubagentHandback", "input": {"message": text}})
            lines.append({"type": "assistant", "message": {"role": "assistant", "content": [item]}})
        path.write_text("\n".join(json.dumps(line) for line in lines))
        return str(path)

    def review_ready(self):
        (self.project / ".apex" / "review.json").write_text("{}")
        self.git_init()
        self.hook("baseline", hook_event_name="UserPromptSubmit",
                  prompt="Sadece value.txt dosyasındaki metni koru, başka hiçbir şey ekleme.")
        (self.project / "extra.txt").write_text("unrequested\n")

    def test_review_is_required_and_receives_verbatim_instructions(self):
        self.review_ready()
        result = self.hook("stop", hook_event_name="Stop")
        self.assertEqual(result["decision"], "block")
        self.assertIn('subagent_type "apex-reviewer"', result["reason"])
        self.assertIn("- extra.txt", result["reason"])
        instructions = result["reason"].split("Instructions file: ")[1].split("\n")[0]
        self.assertIn("başka hiçbir şey ekleme", Path(instructions).read_text())

    def test_review_pass_releases_only_the_reviewed_tree(self):
        self.review_ready()
        self.hook("stop", hook_event_name="Stop")
        self.hook("stop", hook_event_name="SubagentStop", agent_type="apex-reviewer",
                  agent_transcript_path=self.reviewer_transcript(("tool", "No deviations.\nAPEX-REVIEW: PASS")))
        self.assertIsNone(self.hook("stop", hook_event_name="Stop", stop_hook_active=True))
        (self.project / "extra.txt").write_text("changed after the review\n")
        self.assertEqual(self.hook("stop", hook_event_name="Stop")["decision"], "block")

    def test_review_fail_blocks_with_findings(self):
        self.review_ready()
        self.hook("stop", hook_event_name="SubagentStop", agent_type="apex-reviewer",
                  agent_transcript_path=self.reviewer_transcript(
                      ("text", "APEX-REVIEW: PASS"),  # an earlier draft must not count
                      ("tool", '- extra.txt: unrequested file (instruction: "başka hiçbir şey ekleme")\n'
                               "APEX-REVIEW: FAIL")))
        result = self.hook("stop", hook_event_name="Stop")
        self.assertEqual(result["decision"], "block")
        self.assertIn("unrequested file", result["reason"])

    def test_verdict_is_read_from_the_event_when_the_transcript_is_missing(self):
        """The host also hands over the reviewer's last message; a missing transcript file must not hide it."""
        self.scope("src/")
        (self.project / "src").mkdir()
        (self.project / ".apex" / "review.json").write_text("{}")
        self.git_init()
        self.hook("baseline", hook_event_name="UserPromptSubmit", prompt="add a file")
        (self.project / "src" / "a.txt").write_text("x\n")
        absent = str(Path(self.temp.name) / "no-such-transcript.jsonl")
        self.hook("stop", hook_event_name="SubagentStop", agent_type="apex-reviewer",
                  agent_transcript_path=absent, last_assistant_message="Looks right.\n\nAPEX-REVIEW: PASS")
        self.assertIsNone(self.hook("stop", hook_event_name="Stop"))

    def test_a_failing_verdict_in_the_event_still_blocks(self):
        self.scope("src/")
        (self.project / "src").mkdir()
        (self.project / ".apex" / "review.json").write_text("{}")
        self.git_init()
        self.hook("baseline", hook_event_name="UserPromptSubmit", prompt="add a file")
        (self.project / "src" / "a.txt").write_text("x\n")
        absent = str(Path(self.temp.name) / "no-such-transcript.jsonl")
        self.hook("stop", hook_event_name="SubagentStop", agent_type="apex-reviewer",
                  agent_transcript_path=absent, last_assistant_message="- a.txt: extra\n\nAPEX-REVIEW: FAIL")
        result = self.hook("stop", hook_event_name="Stop")
        self.assertEqual(result["decision"], "block")
        self.assertIn("extra", result["reason"])

    def test_no_verdict_anywhere_counts_as_failure(self):
        self.scope("src/")
        (self.project / "src").mkdir()
        (self.project / ".apex" / "review.json").write_text("{}")
        self.git_init()
        self.hook("baseline", hook_event_name="UserPromptSubmit", prompt="add a file")
        (self.project / "src" / "a.txt").write_text("x\n")
        absent = str(Path(self.temp.name) / "no-such-transcript.jsonl")
        self.hook("stop", hook_event_name="SubagentStop", agent_type="apex-reviewer",
                  agent_transcript_path=absent, last_assistant_message="I could not read the file.")
        self.assertEqual(self.hook("stop", hook_event_name="Stop")["decision"], "block")

    def test_missing_verdict_counts_as_failure(self):
        self.review_ready()
        self.hook("stop", hook_event_name="SubagentStop", agent_type="apex-reviewer",
                  agent_transcript_path=self.reviewer_transcript(("text", "Looks fine to me.")))
        self.assertIn("no APEX-REVIEW verdict", self.hook("stop", hook_event_name="Stop")["reason"])

    def test_coding_subagent_pass_does_not_skip_the_main_review(self):
        self.review_ready()
        self.assertIsNone(self.hook("stop", hook_event_name="SubagentStop", agent_type="apex-coding"))
        self.assertEqual(self.run_count(), 1)
        result = self.hook("stop", hook_event_name="Stop")
        self.assertEqual(result["decision"], "block")
        self.assertIn('subagent_type "apex-reviewer"', result["reason"])
        self.assertEqual(self.run_count(), 1)  # the verified tree is not checked twice

    def test_ignored_review_request_is_reported_to_the_user(self):
        self.review_ready()
        for _ in range(3):
            self.assertEqual(self.hook("stop", hook_event_name="Stop")["decision"], "block")
        result = self.hook("stop", hook_event_name="Stop")
        self.assertNotIn("decision", result)
        self.assertIn("unreviewed", result["systemMessage"])

    def test_controls_in_a_subfolder_trigger_a_warning(self):
        parent = Path(self.temp.name)
        result = self.hook("baseline", hook_event_name="UserPromptSubmit", cwd=str(parent), prompt="x")
        self.assertIn("Apex controls are OFF", result["systemMessage"])
        self.assertIn("project/.apex", result["hookSpecificOutput"]["additionalContext"])
        self.assertIsNone(self.hook("baseline", hook_event_name="UserPromptSubmit", prompt="x"))

    def prompt_then_edit(self, prompt, target=None, cwd=None):
        cwd = cwd or str(self.project)
        result = self.hook("baseline", hook_event_name="UserPromptSubmit", prompt=prompt, cwd=cwd)
        edit = self.hook("guard", hook_event_name="PreToolUse", tool_name="Write", cwd=cwd,
                         tool_input={"file_path": target or str(self.project / "value.txt")})
        return result, edit

    def test_question_and_stop_messages_lock_edits_for_that_turn(self):
        for prompt, kind in (("bu aynisi mi", "question"), ("Neden çalışmıyor?", "question"),
                             ("dur", "stop"), ("ne yapıyorsun ya", "stop"), ("kafayı yiyeceğim", "stop")):
            result, edit = self.prompt_then_edit(prompt)
            self.assertEqual(edit["hookSpecificOutput"]["permissionDecision"], "deny", prompt)
            self.assertIn("blocked for this turn", result["hookSpecificOutput"]["additionalContext"], prompt)
            expected = "wants you to stop" if kind == "stop" else "asked a question"
            self.assertIn(expected, edit["hookSpecificOutput"]["permissionDecisionReason"], prompt)
        for prompt in ("Evet, bu 4 maddeyi uygula.", "Bu dalı main'e birleştir.", "durumu düzelt"):
            result, edit = self.prompt_then_edit(prompt)
            self.assertIsNone(edit, prompt)

    def test_work_requests_phrased_as_questions_or_naming_stop_are_not_locked(self):
        sys.path.insert(0, str(HOOK.parent))
        self.addCleanup(sys.path.remove, str(HOOK.parent))
        import apex_verify_hook
        cases = {"Bunu düzeltir misin?": None, "Login sayfasını yapar mısın": None,
                 "Can you add tests?": None, "Rename the function which parses dates": None,
                 "Show how the cache works in the README": None, "Fix the Stop hook": None,
                 "Add a stop button to the player": None, "Bekle, önce testleri yaz": None,
                 "Kardesim bak bana. Odaklan, tekrar dene.": None,
                 "Islemlere devam etsene neden durdun pek anlayamadım ?": None,
                 "Neden durdun, devam et": None, "Why did you stop? Keep going.": None,
                 "Bu sene ne değişti?": "question", "Docker acmali miyim ?": "question",
                 "Neden bu kadar dusundun atom mu parçalıyorsun ?": "question",
                 "Neden bozuldu?": "question", "How does the cache work": "question",
                 "bu aynisi mi": "question", "dur": "stop", "Bekle!": "stop", "stop it now": "stop"}
        for prompt, kind in cases.items():
            self.assertEqual(apex_verify_hook.classify(prompt), kind, prompt)

    def test_plan_approval_lifts_the_turn_lock(self):
        _result, edit = self.prompt_then_edit("Neden bozuk, düzeltir misin?")
        self.assertEqual(edit["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIsNone(self.hook("unlock", hook_event_name="PostToolUse", tool_name="ExitPlanMode"))
        self.assertIsNone(self.hook("guard", hook_event_name="PreToolUse", tool_name="Edit",
                                    tool_input={"file_path": str(self.project / "value.txt")}))

    def test_shell_change_during_locked_turn_is_reported(self):
        self.git_init()
        self.hook("baseline", hook_event_name="UserPromptSubmit", prompt="neden boş?")
        self.assertIsNone(self.hook("stop", hook_event_name="Stop"))
        (self.project / "value.txt").write_text("changed by shell\n")
        result = self.hook("stop", hook_event_name="Stop")
        self.assertIn("edits were locked", result["systemMessage"])

    def test_turn_lock_applies_without_apex_settings_but_allows_plan_files(self):
        outside = Path(self.temp.name) / "plain"
        outside.mkdir()
        home = Path(self.temp.name) / "home"
        self.hook("baseline", hook_event_name="UserPromptSubmit", prompt="ne oldu?", cwd=str(outside))
        denied = self.hook("guard", hook_event_name="PreToolUse", tool_name="Edit", cwd=str(outside),
                           tool_input={"file_path": str(outside / "a.txt")})
        self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIsNone(self.hook("guard", hook_event_name="PreToolUse", tool_name="Write", cwd=str(outside),
                                    tool_input={"file_path": str(home / ".claude" / "plans" / "p.md")},
                                    _home=str(home)))

    def test_lock_context_is_kept_with_misplaced_controls_warning(self):
        result = self.hook("baseline", hook_event_name="UserPromptSubmit",
                           cwd=self.temp.name, prompt="neden boş?")
        context = result["hookSpecificOutput"]["additionalContext"]
        self.assertIn("asked a question", context)
        self.assertIn("NOT active", context)

    def test_guard_denies_only_the_verify_config(self):
        denied = self.hook("guard", hook_event_name="PreToolUse", tool_name="Edit",
                           tool_input={"file_path": ".apex/verify.json"})
        self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIsNone(self.hook("guard", hook_event_name="PreToolUse", tool_name="Write",
                                    tool_input={"file_path": str(self.project / "value.txt")}))


if __name__ == "__main__":
    unittest.main()
