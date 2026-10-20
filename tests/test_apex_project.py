"""Project setup tool checks; every project is a disposable temporary folder."""

import importlib.util
import json
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "apex_project", Path(__file__).resolve().parents[1] / "controls" / "apex_project.py")
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


    def test_init_writes_a_manifest_pointing_at_this_checkout(self):
        self.assertEqual(project.main(["init", "--root", str(self.root), "--allow", "row/",
                                       "--verify", "true", "--no-review"]), 0)
        manifest = json.loads((self.root / ".apex" / "apex.json").read_text())
        self.assertEqual(manifest, {"source": str(project.SOURCE), "format": project.FORMAT})

    def test_upgrade_adds_the_manifest_and_never_touches_the_rules(self):
        apex = self.root / ".apex"
        apex.mkdir()
        rules = {"verify.json": '{"command": "true", "timeout": 60}', "scope.json": '{"allow": ["row/"]}',
                 "review.json": "{}"}
        for name, text in rules.items():
            (apex / name).write_text(text)
        self.assertEqual(project.find_projects([str(self.root.parent)])[0]["format"], 0)
        result = project.upgrade(str(self.root))
        self.assertEqual((result["from"], result["to"]), (0, project.FORMAT))
        self.assertEqual({name: (apex / name).read_text() for name in rules}, rules)
        self.assertTrue(project.find_projects([str(self.root.parent)])[0]["current"])

    def test_upgrade_refuses_a_newer_format_and_a_missing_folder(self):
        with self.assertRaises(ValueError):
            project.upgrade(str(self.root))
        (self.root / ".apex").mkdir()
        (self.root / ".apex" / "apex.json").write_text(json.dumps({"format": project.FORMAT + 1}))
        with self.assertRaises(ValueError):
            project.upgrade(str(self.root))

    def test_list_skips_dependency_folders(self):
        (self.root / "store" / "node_modules" / "pkg" / ".apex").mkdir(parents=True)
        (self.root / "row" / ".apex").mkdir()
        roots = [entry["root"] for entry in project.find_projects([str(self.root)])]
        self.assertEqual(roots, [str((self.root / "row").resolve())])

    def test_suggest_reads_every_stack_and_skips_placeholders(self):
        (self.root / "App.slnx").write_text("")
        (self.root / "package.json").write_text(json.dumps({"scripts": {
            "test": 'echo "Error: no test specified" && exit 1', "typecheck": "tsc", "build": "vite build"}}))
        (self.root / "yarn.lock").write_text("")
        (self.root / "docs").mkdir()
        proposal = project.suggest(str(self.root))
        self.assertEqual(proposal["kind"], "dotnet+node")
        self.assertEqual(proposal["verify"], "dotnet build && dotnet test && yarn run typecheck && yarn run build")
        self.assertEqual(proposal["allow"], ["docs/"])

    def test_suggest_without_build_files_proposes_no_command(self):
        self.assertEqual(project.suggest(str(self.root / "row"))["verify"], None)


if __name__ == "__main__":
    unittest.main()
