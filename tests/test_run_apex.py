"""Exercise launcher argument boundaries without contacting a model."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

LAUNCHER = Path(__file__).resolve().parents[1] / 'run_apex.py'


class LauncherTests(unittest.TestCase):
    def test_host_routing_preserves_literal_task_and_native_arguments(self):
        task = 'Fix `literal` $(text) with spaces; do not execute this as shell'
        for host, arguments in (
            ('codex', ['exec', '-C', '/tmp/project with spaces']),
            ('claude', ['-p', '--allowedTools', 'Read,Edit']),
            ('opencode', ['--format', 'json']),
        ):
            with self.subTest(host=host):
                result = subprocess.run(
                    [sys.executable, str(LAUNCHER), '--host', host, '--dry-run',
                     '--task', task, '--', *arguments],
                    check=True, capture_output=True, text=True,
                )
                command = json.loads(result.stdout)
                self.assertEqual(command[0], host)
                self.assertTrue(command[-1].endswith(task))
                if host == 'claude':
                    self.assertEqual(command[-2], '--')
                if host != 'codex':
                    self.assertNotIn('skills.include_instructions=false', command)
                for argument in arguments:
                    self.assertIn(argument, command)

    def test_portable_outputs_guidance_without_starting_host(self):
        result = subprocess.run(
            [sys.executable, str(LAUNCHER), '--host', 'portable', '--task', 'Small task'],
            check=True, capture_output=True, text=True,
        )
        self.assertIn(str(LAUNCHER.parent / 'SKILL.md'), result.stdout)
        self.assertTrue(result.stdout.rstrip().endswith('Small task'))
