"""The skill catalog keeps its rules, and the repository ships exactly one skill."""

import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = json.loads((ROOT / "catalog" / "skills.json").read_text(encoding="utf-8"))
CATEGORIES = {"engineering-practice", "review-and-quality", "security", "extend-and-guard", "web-and-ui"}
STATUSES = {"planned", "installed", "provided", "removed"}
REQUIRED = {"id", "category", "status", "source", "path", "pinned_ref", "license", "install", "hosts",
            "reviewed", "why", "overlaps_ae", "removal"}
HOSTS = {"claude-code", "codex", "opencode"}
CAP = 4


class CatalogTests(unittest.TestCase):
    def test_every_entry_is_complete(self):
        for entry in CATALOG["skills"]:
            self.assertFalse(REQUIRED - entry.keys(), entry.get("id"))
            self.assertIn(entry["category"], CATEGORIES, entry["id"])
            self.assertIn(entry["status"], STATUSES, entry["id"])
            self.assertEqual(set(entry["hosts"]), HOSTS, entry["id"])
            self.assertTrue(set(entry["hosts"].values()) <= {"verified", "unverified"}, entry["id"])
            self.assertTrue(entry["source"].startswith("https://"), entry["id"])

    def test_ids_are_unique(self):
        ids = [entry["id"] for entry in CATALOG["skills"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_no_category_exceeds_its_cap(self):
        for category in CATEGORIES:
            count = sum(1 for e in CATALOG["skills"] if e["category"] == category and e["status"] != "removed")
            self.assertLessEqual(count, CAP, category)

    def test_an_installed_skill_was_reviewed_and_pinned(self):
        for entry in CATALOG["skills"]:
            if entry["status"] == "installed":
                self.assertTrue(entry["reviewed"] and entry["pinned_ref"], entry["id"])
                self.assertNotEqual(entry["license"], "unverified", entry["id"])

    def test_a_verified_host_belongs_to_an_installed_skill(self):
        for entry in CATALOG["skills"]:
            if "verified" in entry["hosts"].values():
                self.assertEqual(entry["status"], "installed", entry["id"])

    def test_the_repository_ships_exactly_one_skill(self):
        tracked = subprocess.run(["git", "ls-files", "*SKILL.md"], cwd=ROOT, capture_output=True,
                                 text=True, check=True).stdout.split()
        self.assertEqual(tracked, ["SKILL.md"])


if __name__ == "__main__":
    unittest.main()
