"""Project setup tool checks; every project is a disposable temporary folder."""

import importlib.util
import json
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location(
    "apex_project", Path(__file__).resolve().parents[1] / "Claude" / "apex_project.py")
project = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(project)


class ApexProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "update 1"
        (self.root / "store" / "src").mkdir(parents=True)
        (self.root / "store" / "src" / "page.tsx").write_text("export default 1\n")
        (self.root / "row").mkdir()
        (self.root / "row" / "index.html").write_text("<html>original</html>\n")

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, capture_output=True, text=True, check=True).stdout

    def test_init_creates_repository_settings_and_baseline(self):
        # apex_project runs this through a shell; the interpreter's path can contain spaces.
        verify = f"{shlex.quote(sys.executable)} -c 'print(1)'"
        result = project.init(self.root, ["store/src/"], verify, 60, True,
                              ["row/", "store/node_modules/"])
        self.assertTrue(result["git_initialized"])
        self.assertEqual(result["verify_exit_code"], 0)
        self.assertEqual(json.loads((self.root / ".apex/scope.json").read_text()), {"allow": ["store/src/"]})
        self.assertTrue((self.root / ".apex/review.json").is_file())
        self.assertIn("row/", (self.root / ".gitignore").read_text())
        self.assertEqual(self.git("status", "--porcelain"), "")
        tracked = self.git("ls-files")
        self.assertIn("store/src/page.tsx", tracked)
        self.assertNotIn("row/index.html", tracked)

    def test_failing_verify_is_reported(self):
        result = project.init(self.root, ["store/src/"], "exit 3", 60, False, [])
        self.assertEqual(result["verify_exit_code"], 3)
        self.assertFalse((self.root / ".apex/review.json").exists())

    def test_refuses_subfolder_of_another_repository_and_existing_settings(self):
        project.init(self.root, ["store/src/"], "true", 60, True, [])
        with self.assertRaises(ValueError):
            project.init(self.root, ["store/src/"], "true", 60, True, [])
        with self.assertRaises(ValueError):
            project.init(self.root / "store", ["src/"], "true", 60, True, [])

    def test_requires_scope_and_verify(self):
        with self.assertRaises(ValueError):
            project.init(self.root, [], "true", 60, True, [])
        with self.assertRaises(ValueError):
            project.init(self.root, ["store/src/"], "  ", 60, True, [])
        self.assertFalse((self.root / ".git").exists())


if __name__ == "__main__":
    unittest.main()
