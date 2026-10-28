import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / "AGENTS.md"
SOURCES = [ROOT / "controls" / "claude-code" / "hooks" / "apex_verify_hook.py", ROOT / "install.py",
           ROOT / "controls" / "apex_worker.py"]


class ProjectMapTests(unittest.TestCase):
    """A stale map sends every session to the wrong place, so it must name only what exists."""

    def test_map_stays_short(self):
        self.assertLessEqual(len(MAP.read_text().split()), 300)

    def test_claude_imports_the_same_map(self):
        self.assertEqual((ROOT / "CLAUDE.md").read_text().strip(), "@AGENTS.md")

    def test_every_named_path_exists(self):
        paths = [p for p in re.findall(r"`([^`\s]+)`", MAP.read_text()) if "/" in p or re.search(r"\.\w+$", p)]
        self.assertTrue(paths)
        for path in paths:
            if "*" in path:
                self.assertTrue(list(ROOT.glob(path)), path)
            else:
                self.assertTrue((ROOT / path).exists(), path)

    def test_every_named_function_and_constant_exists(self):
        code = "".join(source.read_text() for source in SOURCES)
        for name in re.findall(r"`(\w+)\(\)`", MAP.read_text()):
            self.assertIn(f"def {name}(", code, name)
        for name in re.findall(r"`([A-Z][A-Z_]+)`", MAP.read_text()):
            self.assertRegex(code, rf"\n{name}(: [^=\n]+)? = ", name)


if __name__ == "__main__":
    unittest.main()
