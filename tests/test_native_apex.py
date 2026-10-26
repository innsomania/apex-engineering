"""Compile the native prototype and exercise real exec with disposable fake hosts."""
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class NativeApexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = shutil.which("c++")
        if not compiler:
            raise RuntimeError("C++ compiler required; environment unchanged")
        cls.temp = tempfile.TemporaryDirectory(prefix="apex-native-test-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.base = Path(cls.temp.name)
        cls.binary = cls.base / "apex"
        subprocess.run([compiler, "-std=c++17", "-Wall", "-Wextra", "-Wpedantic",
                        str(ROOT / "native/apex.cpp"), "-o", str(cls.binary)], check=True)
        cls.project = cls.base / "project with spaces"
        cls.project.mkdir()
        cls.hosts = cls.base / "bin"
        cls.hosts.mkdir()
        for host in ("codex", "claude", "opencode"):
            executable = cls.hosts / host
            script = (
                "import json, os, sys\n"
                "print(json.dumps({'argv': sys.argv[1:], 'cwd': os.getcwd(), 'pwd': os.environ['PWD']}))\n"
                "sys.exit(23)\n"
            )
            executable.write_text(
                "#!/bin/sh\nexec " + shlex.quote(sys.executable) + " -c " + shlex.quote(script) + ' "$@"\n'
            )
            executable.chmod(0o700)

    def run_native(self, *arguments, host_path=None):
        return subprocess.run(
            [str(self.binary), "--apex-root", str(ROOT), "--project", str(self.project), *arguments],
            env={**os.environ, "PATH": str(host_path or self.hosts)},
            capture_output=True, text=True, timeout=10,
        )

    def test_hosts_preserve_arguments_directory_and_exit_status(self):
        marker = self.project / "unexpected"
        task = f"Fix `literal` $(touch '{marker}'); preserve quotes and Türkçe"
        for host in ("codex", "claude", "opencode"):
            with self.subTest(host=host):
                result = self.run_native("--host", host, "--task", task, "--", "--example", "value with spaces")
                self.assertEqual(result.returncode, 23, result.stderr)
                record = json.loads(result.stdout)
                self.assertEqual(record["cwd"], str(self.project.resolve()))
                self.assertEqual(record["pwd"], record["cwd"])
                expected = {"codex": ["-c", "skills.include_instructions=false"],
                            "claude": [], "opencode": ["run"]}[host]
                expected += ["--example", "value with spaces"]
                if host == "claude":
                    expected += ["--"]
                self.assertEqual(record["argv"][:-1], expected)
                self.assertTrue(record["argv"][-1].endswith(task))
                self.assertIn(str(ROOT / "SKILL.md"), record["argv"][-1])
                self.assertFalse(marker.exists())

    def test_dry_run_does_not_launch_host_and_missing_host_fails(self):
        empty = self.base / "empty"
        empty.mkdir(exist_ok=True)
        preview = self.run_native("--task", "Example", "--dry-run", host_path=empty)
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertIn("Example", preview.stdout)
        missing = self.run_native("--task", "Example", host_path=empty)
        self.assertEqual(missing.returncode, 127)
        self.assertIn("Cannot start codex", missing.stderr)

    def test_invalid_input_is_rejected_before_launch(self):
        for arguments in (("--host", "unknown", "--task", "Example"), (),
                          ("--task",), ("--task", "Example", "--project", str(self.base / "absent")),
                          ("--task", "Example", "--apex-root", str(self.project))):
            with self.subTest(arguments=arguments):
                result = self.run_native(*arguments)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(result.stdout, "")
