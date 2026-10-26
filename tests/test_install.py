"""Installer integration checks use disposable Codex homes only."""

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("apex_install", Path(__file__).resolve().parents[1] / "install.py")
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)

    def test_guidance_hosts_round_trip_preserves_rules_and_settings(self):
        for host in ("opencode", "portable"):
            with self.subTest(host=host):
                home = self.home / host
                home.mkdir()
                rules = home / "AGENTS.md"
                original = b"# User rules\n"
                rules.write_bytes(original)
                settings = home / "opencode.json"
                settings.write_bytes(b'{"custom": true}\n')
                installer.configure(home, "install", host)
                installed = rules.read_bytes()
                self.assertTrue(installed.startswith(original))
                self.assertEqual((home / "skills/apex-engineering").resolve(), installer.SOURCE)
                self.assertIn("hooks=unsupported", installer.configure(home, "status", host))
                installer.configure(home, "install", host)
                self.assertEqual(rules.read_bytes(), installed)
                self.assertEqual(sorted(p.name for p in home.iterdir()),
                                 ["AGENTS.md", "opencode.json", "skills"])
                installer.configure(home, "uninstall", host)
                self.assertEqual(rules.read_bytes(), original)
                self.assertEqual(settings.read_bytes(), b'{"custom": true}\n')
                self.assertFalse(os.path.lexists(home / "skills/apex-engineering"))

    def test_portable_cli_requires_explicit_destination(self):
        import contextlib
        import io
        from unittest.mock import patch
        with patch("sys.argv", ["install.py", "install", "--host", "portable"]):
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    installer.main()
        self.assertEqual(error.exception.code, 2)

    def test_opencode_cli_uses_xdg_config_directory(self):
        import contextlib
        import io
        from unittest.mock import patch
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(self.home)}):
            with patch("sys.argv", ["install.py", "install", "--host", "opencode"]):
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(installer.main(), 0)
        self.assertTrue((self.home / "opencode/skills/apex-engineering/SKILL.md").is_file())
        self.assertTrue((self.home / "opencode/AGENTS.md").is_file())

    def test_preserves_rules_is_idempotent_and_removes_only_owned_content(self):
        original = "# Existing policy\r\nTürkçe kurallar".encode()
        agents = self.home / "AGENTS.md"
        agents.write_bytes(original)
        installer.configure(self.home, "install")
        installed = agents.read_bytes()
        self.assertTrue(installed.startswith(original))
        self.assertEqual((self.home / "skills/apex-engineering").resolve(), installer.SOURCE)
        installer.configure(self.home, "install")
        self.assertEqual(agents.read_bytes(), installed)
        appended = b"\n# Later user edits\n"
        agents.write_bytes(installed + appended)
        installer.configure(self.home, "uninstall")
        self.assertEqual(agents.read_bytes(), original + appended)
        self.assertFalse((self.home / "skills/apex-engineering").exists())

    def test_conflicting_skill_is_untouched(self):
        conflict = self.home / "skills/apex-engineering"
        conflict.mkdir(parents=True)
        sentinel = conflict / "user.txt"
        sentinel.write_text("keep")
        with self.assertRaises(ValueError):
            installer.configure(self.home, "install")
        self.assertEqual(sentinel.read_text(), "keep")
        self.assertFalse((self.home / "AGENTS.md").exists())

    def test_override_blocks_install_before_mutation(self):
        (self.home / "AGENTS.override.md").write_text("existing override")
        with self.assertRaises(ValueError):
            installer.configure(self.home, "install")
        self.assertFalse((self.home / "skills").exists())

    def test_modified_managed_instructions_are_not_deleted(self):
        installer.configure(self.home, "install")
        agents = self.home / "AGENTS.md"
        edited = agents.read_bytes().replace(b"For software", b"For all software")
        agents.write_bytes(edited)
        with self.assertRaises(ValueError):
            installer.configure(self.home, "uninstall")
        self.assertEqual(agents.read_bytes(), edited)
        self.assertTrue((self.home / "skills/apex-engineering").is_symlink())

    def test_fresh_install_loads_entrypoint_and_the_guides(self):
        installer.configure(self.home, "install")
        skill = self.home / "skills/apex-engineering"
        self.assertIn("name: apex-engineering", (skill / "SKILL.md").read_text())
        for guide in ("engineering/workflow.md", "coding/workflow.md", "test.md", "security.md"):
            self.assertTrue((skill / "guides" / guide).is_file(), guide)
        self.assertIn("instructions=present", installer.configure(self.home, "status"))

    def test_claude_install_links_skill_and_agent_and_preserves_rules(self):
        original = "# Existing Claude rules\nTürkçe yanıt ver\n".encode()
        claude_md = self.home / "CLAUDE.md"
        claude_md.write_bytes(original)
        installer.configure(self.home, "install", "claude")
        installed = claude_md.read_bytes()
        self.assertTrue(installed.startswith(original))
        self.assertIn(b"apex-engineering skill", installed)
        self.assertEqual((self.home / "skills/apex-engineering").resolve(), installer.SOURCE)
        agent = self.home / "agents/apex-coding.md"
        self.assertIn("name: apex-coding", agent.read_text())
        self.assertFalse((self.home / "AGENTS.md").exists())
        self.assertIn("host=claude, skill=linked, instructions=present",
                      installer.configure(self.home, "status", "claude"))
        installer.configure(self.home, "install", "claude")
        self.assertEqual(claude_md.read_bytes(), installed)
        installer.configure(self.home, "uninstall", "claude")
        self.assertEqual(claude_md.read_bytes(), original)
        self.assertFalse(os.path.lexists(agent))
        self.assertFalse(os.path.lexists(self.home / "skills/apex-engineering"))

    def test_claude_conflicting_agent_blocks_install_before_mutation(self):
        agent = self.home / "agents/apex-coding.md"
        agent.parent.mkdir(parents=True)
        agent.write_text("user agent")
        with self.assertRaises(ValueError):
            installer.configure(self.home, "install", "claude")
        self.assertEqual(agent.read_text(), "user agent")
        self.assertFalse((self.home / "skills").exists())
        self.assertFalse((self.home / "CLAUDE.md").exists())

    def test_claude_hooks_merge_with_user_settings_and_uninstall_cleanly(self):
        import json
        settings = self.home / "settings.json"
        user = {"enabledPlugins": {"x@y": True},
                "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo mine"}]}]}}
        settings.write_text(json.dumps(user))
        installer.configure(self.home, "install", "claude")
        installed = json.loads(settings.read_text())
        self.assertEqual(installed["enabledPlugins"], user["enabledPlugins"])
        self.assertEqual(installed["hooks"]["Stop"][0], user["hooks"]["Stop"][0])
        for event in ("UserPromptSubmit", "Stop", "SubagentStop", "PreToolUse", "PostToolUse"):
            self.assertTrue(any("apex_verify_hook.py" in hook["command"]
                                for group in installed["hooks"][event] for hook in group["hooks"]))
        self.assertIn("hooks=present", installer.configure(self.home, "status", "claude"))
        before = settings.read_text()
        installer.configure(self.home, "install", "claude")
        self.assertEqual(settings.read_text(), before)
        installer.configure(self.home, "uninstall", "claude")
        self.assertEqual(json.loads(settings.read_text()), user)

    def test_claude_install_links_only_the_skill_and_its_two_agents(self):
        installer.configure(self.home, "install", "claude")
        self.assertEqual(sorted(path.name for path in (self.home / "skills").iterdir()), ["apex-engineering"])
        self.assertEqual(sorted(path.name for path in (self.home / "agents").iterdir()),
                         ["apex-coding.md", "apex-reviewer.md"])
        for link in (self.home / "agents").iterdir():
            self.assertTrue(link.resolve().is_file(), link)

    def test_claude_invalid_settings_block_install_before_mutation(self):
        (self.home / "settings.json").write_text("{broken")
        with self.assertRaises(ValueError):
            installer.configure(self.home, "install", "claude")
        self.assertEqual((self.home / "settings.json").read_text(), "{broken")
        self.assertFalse((self.home / "skills").exists())

    def test_codex_install_adds_hooks_and_reviewer_and_uninstall_keeps_user_hooks(self):
        import json
        user_hook = {"matcher": "Bash", "hooks": [{"type": "command", "command": "my-check"}]}
        (self.home / "hooks.json").write_text(json.dumps({"hooks": {"PreToolUse": [user_hook]}}))
        message = installer.configure(self.home, "install", "codex")
        self.assertIn("/hooks", message)
        hooks = json.loads((self.home / "hooks.json").read_text())["hooks"]
        self.assertEqual(set(hooks), {"UserPromptSubmit", "Stop", "SubagentStop", "PreToolUse"})
        guard = hooks["PreToolUse"][-1]
        self.assertEqual(guard["matcher"], "apply_patch")
        self.assertTrue(guard["hooks"][0]["command"].endswith(" guard codex"))
        self.assertEqual((self.home / "agents/apex-reviewer.toml").resolve(),
                         installer.CODEX_AGENTS / "apex-reviewer.toml")
        self.assertIn("hooks=present", installer.configure(self.home, "status", "codex"))
        installer.configure(self.home, "install", "codex")
        self.assertEqual(json.loads((self.home / "hooks.json").read_text())["hooks"], hooks)
        installer.configure(self.home, "uninstall", "codex")
        self.assertEqual(json.loads((self.home / "hooks.json").read_text()), {"hooks": {"PreToolUse": [user_hook]}})
        self.assertFalse((self.home / "agents/apex-reviewer.toml").exists())

    def test_hosts_use_distinct_blocks(self):
        installer.configure(self.home, "install", "codex")
        with self.assertRaises(ValueError):
            installer.split_owned((self.home / "AGENTS.md").read_bytes(), "claude")


if __name__ == "__main__":
    unittest.main()
