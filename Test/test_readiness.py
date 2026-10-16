"""MVP readiness checks. All mutations are confined to temporary directories."""

import importlib.util
from contextlib import ExitStack
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("apex_readiness_install", ROOT / "install.py")
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="apex readiness ")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.home = self.base / "Codex Home"

    def cli(self, action, *args, home=None):
        env = dict(os.environ, CODEX_HOME=str(home or self.home),
                   PYTHONDONTWRITEBYTECODE="1")
        return subprocess.run([sys.executable, str(ROOT / "install.py"), action, *args],
                              env=env, capture_output=True, text=True, timeout=10)

    def test_cli_round_trip_with_spaces_and_custom_home(self):
        for action in ("install", "status", "uninstall", "uninstall"):
            result = self.cli(action)
            self.assertEqual(result.returncode, 0, result.stderr)
            if action == "status":
                self.assertIn("skill=linked, instructions=present", result.stdout)
        self.assertFalse((self.home / "skills/apex-engineering").exists())

    def test_explicit_home_takes_precedence_over_environment(self):
        explicit = self.base / "Explicit Home"
        result = self.cli("install", "--codex-home", str(explicit))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((explicit / "skills/apex-engineering/SKILL.md").is_file())
        self.assertFalse(self.home.exists())

    def test_status_does_not_create_files(self):
        result = self.cli("status")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("skill=missing, instructions=missing", result.stdout)
        self.assertFalse(self.home.exists())

    def test_cli_conflict_returns_failure_without_mutation(self):
        conflict = self.home / "skills/apex-engineering"
        conflict.mkdir(parents=True)
        result = self.cli("install")
        self.assertEqual(result.returncode, 1)
        self.assertIn("not owned", result.stderr)
        self.assertFalse((self.home / "AGENTS.md").exists())

    def test_agents_symlink_preserves_external_file(self):
        self.home.mkdir()
        external = self.base / "shared-policy.md"
        external.write_bytes(b"user-owned rules")
        (self.home / "AGENTS.md").symlink_to(external)
        with self.assertRaises(ValueError):
            installer.configure(self.home, "install")
        self.assertEqual(external.read_bytes(), b"user-owned rules")
        self.assertFalse((self.home / "skills").exists())

    def test_broken_foreign_skill_link_is_preserved(self):
        link = self.home / "skills/apex-engineering"
        link.parent.mkdir(parents=True)
        target = self.base / "missing-other-checkout"
        link.symlink_to(target)
        with self.assertRaises(ValueError):
            installer.configure(self.home, "install")
        self.assertEqual(link.readlink(), target)
        self.assertFalse((self.home / "AGENTS.md").exists())

    def test_empty_override_allows_install(self):
        self.home.mkdir()
        (self.home / "AGENTS.override.md").write_bytes(b"")
        installer.configure(self.home, "install")
        self.assertTrue((self.home / "skills/apex-engineering/SKILL.md").is_file())

    def test_duplicate_or_incomplete_marker_is_preserved(self):
        self.home.mkdir()
        agents = self.home / "AGENTS.md"
        for data in (installer.block() * 2, installer.START, installer.END):
            with self.subTest(data=data):
                agents.write_bytes(data)
                with self.assertRaises(ValueError):
                    installer.configure(self.home, "install")
                self.assertEqual(agents.read_bytes(), data)
                self.assertFalse((self.home / "skills").exists())

    def test_missing_owned_link_can_be_recreated_without_duplicate_rules(self):
        installer.configure(self.home, "install")
        agents = self.home / "AGENTS.md"
        original = agents.read_bytes()
        (self.home / "skills/apex-engineering").unlink()
        installer.configure(self.home, "install")
        self.assertEqual(agents.read_bytes(), original)
        self.assertTrue((self.home / "skills/apex-engineering/SKILL.md").is_file())

    def test_all_local_markdown_references_resolve_within_package(self):
        """Apex's own documentation only.

        Claude/skills holds vendored third-party copies whose wording is upstream's to fix, and
        whose code samples contain `](...)` that is not a link at all. See
        Engineering/Integrations/VENDORED_SKILLS.md. `.claude/` is tooling state rather than
        package content, and it holds this checkout's worktrees, each a full copy of the package.
        """
        checked = 0
        for document in ROOT.rglob("*.md"):
            parts = document.relative_to(ROOT).parts
            if ".claude" in parts or parts[:2] == ("Claude", "skills"):
                continue
            for target in re.findall(r"\]\(([^)]+)\)", document.read_text()):
                if "://" in target or target.startswith("#"):
                    continue
                resolved = (document.parent / target.split("#")[0]).resolve()
                self.assertTrue(resolved.is_relative_to(ROOT), str(resolved))
                self.assertTrue(resolved.is_file(), f"{document}: {target}")
                checked += 1
        self.assertGreater(checked, 0)

    def partial_write(self, path, mode):
        """Inject a write failure after real partial output in the temp home."""
        original_open = Path.open
        original_fdopen = os.fdopen

        class InterruptedWriter:
            def __init__(self, stream):
                self.stream = stream

            def __enter__(self):
                return self

            def fileno(self):
                return self.stream.fileno()

            def write(self, data):
                self.stream.write(data[:len(data) // 2])
                self.stream.flush()
                raise OSError("simulated interrupted write")

            def __exit__(self, *exc):
                self.stream.close()

        def replacement(candidate, *args, **kwargs):
            requested_mode = args[0] if args else kwargs.get("mode", "r")
            if candidate == path and requested_mode == mode:
                return InterruptedWriter(original_open(candidate, *args, **kwargs))
            return original_open(candidate, *args, **kwargs)

        def fd_replacement(descriptor, *args, **kwargs):
            return InterruptedWriter(original_fdopen(descriptor, *args, **kwargs))

        stack = ExitStack()
        stack.enter_context(patch.object(Path, "open", replacement))
        stack.enter_context(patch.object(os, "fdopen", fd_replacement))
        return stack

    def test_interrupted_install_preserves_original_policy(self):
        self.home.mkdir()
        agents = self.home / "AGENTS.md"
        original = b"# User policy\nPreserve all of this.\n"
        agents.write_bytes(original)
        with self.partial_write(agents, "ab"):
            with self.assertRaises(OSError):
                installer.configure(self.home, "install")
        self.assertEqual(agents.read_bytes(), original,
                         "A failed install must not leave a partial managed block")
        self.assertFalse((self.home / "skills/apex-engineering").exists())
        self.assertEqual(list(self.home.glob(".apex-*")), [])

    def test_interrupted_uninstall_preserves_original_policy(self):
        self.home.mkdir()
        agents = self.home / "AGENTS.md"
        original = b"# User policy\nRule one.\nRule two must survive.\n"
        agents.write_bytes(original)
        installer.configure(self.home, "install")
        installed = agents.read_bytes()
        with self.partial_write(agents, "wb"):
            with self.assertRaises(OSError):
                installer.configure(self.home, "uninstall")
        self.assertEqual(agents.read_bytes(), installed,
                         "A failed uninstall must not truncate user instructions")
        self.assertTrue((self.home / "skills/apex-engineering").is_symlink())
        self.assertEqual(list(self.home.glob(".apex-*")), [])

    def test_publish_failure_preserves_policy_and_cleans_temporary_file(self):
        self.home.mkdir()
        agents = self.home / "AGENTS.md"
        agents.write_bytes(b"original policy")
        with patch.object(installer.os, "replace", side_effect=OSError("simulated publish failure")):
            with self.assertRaises(OSError):
                installer.configure(self.home, "install")
        self.assertEqual(agents.read_bytes(), b"original policy")
        self.assertEqual(list(self.home.glob(".apex-*")), [])
        self.assertFalse((self.home / "skills/apex-engineering").exists())

    def test_sync_failure_preserves_policy(self):
        self.home.mkdir()
        agents = self.home / "AGENTS.md"
        agents.write_bytes(b"original policy")
        with patch.object(installer.os, "fsync", side_effect=OSError("simulated sync failure")):
            with self.assertRaises(OSError):
                installer.configure(self.home, "install")
        self.assertEqual(agents.read_bytes(), b"original policy")
        self.assertEqual(list(self.home.glob(".apex-*")), [])

    def test_original_permissions_survive_install_and_uninstall(self):
        self.home.mkdir()
        agents = self.home / "AGENTS.md"
        agents.write_bytes(b"original policy")
        agents.chmod(0o640)
        for action in ("install", "uninstall"):
            installer.configure(self.home, action)
            self.assertEqual(agents.stat().st_mode & 0o777, 0o640)


if __name__ == "__main__":
    unittest.main()
