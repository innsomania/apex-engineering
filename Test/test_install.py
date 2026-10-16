"""Installer integration checks use disposable Codex homes only."""

import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("apex_install", Path(__file__).resolve().parents[1] / "install.py")
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)

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

    def test_fresh_install_loads_entrypoint_and_four_modules(self):
        installer.configure(self.home, "install")
        skill = self.home / "skills/apex-engineering"
        self.assertIn("name: apex-engineering", (skill / "SKILL.md").read_text())
        for area in ("Engineering", "Coding", "Test", "Security"):
            self.assertTrue((skill / area / "WORKFLOW.md").is_file())
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

    def test_hosts_use_distinct_blocks(self):
        installer.configure(self.home, "install", "codex")
        with self.assertRaises(ValueError):
            installer.split_owned((self.home / "AGENTS.md").read_bytes(), "claude")


if __name__ == "__main__":
    unittest.main()
