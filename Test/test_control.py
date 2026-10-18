"""Focused file-broker boundary tests; no model or external service required."""
import json
import os
import signal
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Engineering'))
import codex_control
import controlled_cli
from control import Broker


class FakeStdin:
    def __init__(self):
        self.messages = []

    def write(self, value):
        self.messages.append(value)
        return len(value)

    def flush(self):
        pass

    def close(self):
        pass


class FakeCodex:
    def __init__(self, messages):
        self.stdin = FakeStdin()
        self.stdout = StringIO(''.join(json.dumps(message) + '\n' for message in messages))

    def terminate(self):
        pass

    def wait(self, timeout=None):
        return 0


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'allowed.txt').write_text('original')
        (self.root / 'protected.txt').write_text('protected')
        self.broker = Broker(self.root, ['allowed.txt'], ['allowed.txt', 'new.txt'])
        self.addCleanup(self.broker.close)

    def call(self, operation, path, **extra):
        return self.broker.dispatch(dict(operation=operation, path=path, **extra))

    @staticmethod
    def fake_codex_messages(tool_calls=(), status='completed', host_items=()):
        config = {
            'approval_policy': 'never', 'sandbox_mode': 'read-only', 'web_search': 'disabled',
            'features': {name: False for name in codex_control.DISABLED}, 'mcp_servers': {},
        }
        messages = [
            {'id': 1, 'result': {}},
            {'id': 4, 'result': {'config': config}},
            {'id': 2, 'result': {
                'sandbox': {'type': 'readOnly', 'networkAccess': False},
                'approvalPolicy': 'never', 'runtimeWorkspaceRoots': [], 'thread': {'id': 'thread'},
            }},
            {'id': 3, 'result': {'turn': {'id': 'turn'}}},
            {'method': 'turn/started', 'params': {'turn': {'id': 'turn'}}},
        ]
        messages.extend(host_items)
        for index, call in enumerate(tool_calls, start=10):
            params = {'threadId': 'thread', 'turnId': 'turn', 'callId': f'call-{index}', **call}
            messages.append({'id': index, 'method': 'item/tool/call', 'params': params})
        if status == 'interrupted':
            messages.append({'id': 9, 'result': {}})
        messages.append({'method': 'turn/completed', 'params': {'turn': {'status': status}}})
        return messages

    def run_fake_codex(self, messages, **kwargs):
        process = FakeCodex(messages)
        with patch.object(codex_control, 'command', return_value=['fake-codex']):
            with patch.object(codex_control.subprocess, 'Popen', return_value=process):
                report = codex_control.run_fixture(self.broker, 'Fake Codex test', **kwargs)
        return report, process

    def test_authorized_read_write_and_create(self):
        self.assertEqual(self.call('read', 'allowed.txt')['text'], 'original')
        self.assertTrue(self.call('write', 'allowed.txt', text='updated')['success'])
        self.assertTrue(self.call('write', 'new.txt', text='new')['success'])
        self.assertEqual((self.root / 'allowed.txt').read_text(), 'updated')
        self.assertEqual((self.root / 'new.txt').read_text(), 'new')

    def test_denials_preserve_protected_state(self):
        for path in ['protected.txt', '../protected.txt', str(self.root / 'protected.txt'),
                     './allowed.txt', 'x/../allowed.txt', 'x//allowed.txt', 'allowed.txt\x00', 'x\\allowed.txt']:
            with self.subTest(path=path):
                self.assertFalse(self.call('write', path, text='attack')['success'])
        self.assertEqual((self.root / 'protected.txt').read_text(), 'protected')
        self.assertEqual((self.root / 'allowed.txt').read_text(), 'original')

    def test_policy_change_process_network_unknown_and_extra_fields_denied(self):
        for operation in ['shell', 'exec', 'network', 'change_policy', 'resume', 'delete']:
            self.assertFalse(self.call(operation, 'allowed.txt')['success'])
        self.assertFalse(self.call('write', 'allowed.txt', text='attack', approved=True)['success'])
        self.assertFalse(self.broker.dispatch([])['success'])
        self.assertEqual((self.root / 'allowed.txt').read_text(), 'original')

    def test_final_symlinks_and_hardlinks_denied(self):
        file = self.root / 'allowed.txt'
        file.unlink()
        file.symlink_to(self.root / 'protected.txt')
        self.assertFalse(self.call('read', 'allowed.txt')['success'])
        self.assertFalse(self.call('write', 'allowed.txt', text='attack')['success'])
        file.unlink()
        os.link(self.root / 'protected.txt', file)
        self.assertFalse(self.call('read', 'allowed.txt')['success'])
        self.assertFalse(self.call('write', 'allowed.txt', text='attack')['success'])
        self.assertEqual((self.root / 'protected.txt').read_text(), 'protected')

    def test_parent_symlink_denied_even_when_exact_path_allowed(self):
        (self.root / 'link').symlink_to(self.root, target_is_directory=True)
        broker = Broker(self.root, ['link/protected.txt'], ['link/protected.txt'])
        self.addCleanup(broker.close)
        for operation in ['read', 'write']:
            args = dict(operation=operation, path='link/protected.txt')
            if operation == 'write':args['text'] = 'attack'
            self.assertFalse(broker.dispatch(args)['success'])
        self.assertEqual((self.root / 'protected.txt').read_text(), 'protected')

    def test_nonregular_file_denied_without_blocking(self):
        path = self.root / 'allowed.txt'
        path.unlink()
        os.mkfifo(path)
        self.assertFalse(self.call('read', 'allowed.txt')['success'])
        self.assertFalse(self.call('write', 'allowed.txt', text='attack')['success'])

    def test_byte_and_call_budgets(self):
        broker = Broker(self.root, ['allowed.txt'], ['allowed.txt'], max_bytes=3, max_calls=2)
        self.addCleanup(broker.close)
        self.assertFalse(broker.dispatch({'operation': 'read', 'path': 'allowed.txt'})['success'])
        self.assertFalse(broker.dispatch({'operation': 'write', 'path': 'allowed.txt', 'text': '1234'})['success'])
        self.assertFalse(broker.dispatch({'operation': 'write', 'path': 'allowed.txt', 'text': 'ok'})['success'])
        self.assertEqual((self.root / 'allowed.txt').read_text(), 'original')

    def test_stop_is_terminal_across_threads(self):
        self.broker.stop()
        results = []
        thread = threading.Thread(target=lambda: results.append(self.call('write', 'allowed.txt', text='late')))
        thread.start();thread.join(timeout=2)
        self.assertFalse(thread.is_alive())
        self.assertFalse(results[0]['success'])
        self.assertFalse(self.call('resume', 'allowed.txt')['success'])
        stop = next(i for i,e in enumerate(self.broker.events) if e['event'] == 'stopped')
        self.assertFalse(any(e['event'] == 'admitted' for e in self.broker.events[stop + 1:]))
        self.assertEqual((self.root / 'allowed.txt').read_text(), 'original')

    def test_direct_host_tool_names_cannot_reach_the_file_broker(self):
        seen = set()
        for index, tool in enumerate(['exec_command', 'functions.exec_command', 'commandExecution']):
            with self.subTest(tool=tool):
                result = codex_control.dispatch_tool_call(self.broker, {
                    'threadId': 'thread', 'turnId': 'turn', 'callId': f'bypass-{index}',
                    'tool': tool,
                    'arguments': {'operation': 'write', 'path': 'allowed.txt', 'text': 'bypass'},
                }, 'thread', 'turn', seen)
                self.assertFalse(result['success'])
        self.assertEqual(self.broker.events, [])
        self.assertEqual((self.root / 'allowed.txt').read_text(), 'original')

    def test_early_file_call_without_established_thread_or_turn_is_denied(self):
        result = codex_control.dispatch_tool_call(self.broker, {
            'callId': 'early-call', 'tool': 'apex_file',
            'arguments': {'operation': 'write', 'path': 'allowed.txt', 'text': 'bypass'},
        }, None, None, set())
        self.assertFalse(result['success'])
        self.assertEqual(self.broker.events, [])
        self.assertEqual((self.root / 'allowed.txt').read_text(), 'original')

    def test_fake_codex_denies_direct_tool_attempt_then_allows_broker_write(self):
        messages = self.fake_codex_messages(tool_calls=[
            {'tool': 'exec_command', 'arguments': {
                'command': f'printf bypass > {self.root / "protected.txt"}',
            }},
            {'tool': 'apex_file', 'arguments': {
                'operation': 'write', 'path': 'allowed.txt', 'text': 'via broker',
            }},
        ])
        report, process = self.run_fake_codex(messages)
        self.assertEqual(report['status'], 'completed')
        self.assertEqual(report['events'].count('tool_denied'), 1)
        self.assertEqual(report['events'].count('tool_accepted'), 1)
        self.assertEqual((self.root / 'allowed.txt').read_text(), 'via broker')
        self.assertEqual((self.root / 'protected.txt').read_text(), 'protected')
        self.assertTrue(any('turn/start' in message for message in process.stdin.messages))

    def test_fake_codex_trusted_stop_denies_pending_broker_write(self):
        stop = threading.Event()
        messages = self.fake_codex_messages(tool_calls=[{
            'tool': 'apex_file', 'arguments': {
                'operation': 'write', 'path': 'allowed.txt', 'text': 'late write',
            },
        }], status='interrupted')

        def request_stop(_params, event):
            event.set()

        report, _ = self.run_fake_codex(messages, stop_event=stop, on_tool=request_stop)
        self.assertEqual(report['status'], 'interrupted')
        self.assertIn('interrupt_requested', report['events'])
        self.assertIn('interrupt_acknowledged', report['events'])
        self.assertEqual((self.root / 'allowed.txt').read_text(), 'original')
        stopped = next(i for i, event in enumerate(report['broker_events']) if event['event'] == 'stopped')
        self.assertFalse(any(event['event'] == 'admitted' for event in report['broker_events'][stopped + 1:]))

    def test_fake_codex_records_a_targeted_native_write_attempt_without_raw_command(self):
        target = str(self.root / 'protected.txt')
        messages = self.fake_codex_messages(host_items=[
            {'method': 'item/started', 'params': {'item': {
                'type': 'commandExecution', 'command': ['sh', '-c', f'printf bypass > {target}'],
            }}},
            {'method': 'item/completed', 'params': {'item': {
                'type': 'commandExecution', 'command': ['sh', '-c', f'printf bypass > {target}'],
                'exitCode': 1,
            }}},
        ])
        report, _ = self.run_fake_codex(messages, direct_write_target=target)
        self.assertIn('direct_write_attempt_observed', report['events'])
        self.assertEqual(report['direct_write_exit_code'], 1)
        self.assertNotIn(target, json.dumps(report))
        self.assertEqual((self.root / 'protected.txt').read_text(), 'protected')

    def test_effective_host_configuration_must_keep_bypass_routes_disabled(self):
        config = {
            'approval_policy': 'never', 'sandbox_mode': 'read-only', 'web_search': 'disabled',
            'features': {name: False for name in codex_control.DISABLED}, 'mcp_servers': {},
        }
        codex_control.verify_effective_config(config)
        config['features']['shell_tool'] = True
        with self.assertRaisesRegex(RuntimeError, 'native feature'):
            codex_control.verify_effective_config(config)

    def test_cli_rejects_invalid_allowlist_before_starting_a_model(self):
        args = ['--project-root', str(self.root), '--allow-write', '../protected.txt',
                '--prompt', 'Do not start']
        with patch.object(controlled_cli, 'run_fixture') as launch:
            with redirect_stderr(StringIO()):
                with self.assertRaises(SystemExit) as error:
                    controlled_cli.main(args)
        self.assertNotEqual(error.exception.code, 0)
        launch.assert_not_called()

    def test_cli_passes_exact_permissions_and_trusted_stop_to_the_session(self):
        handlers = []
        previous_handler = signal.getsignal(signal.SIGINT)

        def capture_handler(_signum, handler):
            handlers.append(handler)
            return previous_handler

        def controlled_session(broker, _prompt, stop_event):
            self.assertTrue(broker.dispatch({
                'operation': 'write', 'path': 'allowed.txt', 'text': 'via cli',
            })['success'])
            self.assertFalse(broker.dispatch({
                'operation': 'write', 'path': 'protected.txt', 'text': 'bypass',
            })['success'])
            handlers[0]()
            self.assertTrue(stop_event.is_set())
            broker.stop()
            return {'status': 'interrupted', 'broker_events': list(broker.events)}

        args = ['--project-root', str(self.root), '--allow-read', 'allowed.txt',
                '--allow-write', 'allowed.txt', '--prompt', 'Controlled test']
        with patch.object(controlled_cli.signal, 'signal', side_effect=capture_handler):
            with patch.object(controlled_cli, 'run_fixture', side_effect=controlled_session) as launch:
                with redirect_stdout(StringIO()):
                    status = controlled_cli.main(args)
        self.assertEqual(status, 130)
        self.assertTrue(launch.called)
        self.assertEqual((self.root / 'allowed.txt').read_text(), 'via cli')
        self.assertEqual((self.root / 'protected.txt').read_text(), 'protected')

    def test_closed_broker_and_permission_input_mutation(self):
        permissions = ['allowed.txt']
        broker = Broker(self.root, writable=permissions)
        permissions.append('protected.txt')
        self.assertFalse(broker.dispatch({'operation': 'write', 'path': 'protected.txt', 'text': 'attack'})['success'])
        broker.close()
        self.assertFalse(broker.dispatch({'operation': 'write', 'path': 'allowed.txt', 'text': 'late'})['success'])

    def test_adapter_startup_failure_stops_broker(self):
        with patch.object(codex_control, 'command', side_effect=RuntimeError('Unsupported host')):
            with self.assertRaises(RuntimeError):
                codex_control.run_fixture(self.broker, 'No model call')
        self.assertFalse(self.call('write', 'allowed.txt', text='late')['success'])

    def test_adapter_disconnect_stops_broker(self):
        with patch.object(codex_control, 'command', return_value=[sys.executable, '-c', 'pass']):
            with self.assertRaises((RuntimeError, BrokenPipeError)):
                codex_control.run_fixture(self.broker, 'Do not run a model', timeout=2)
        self.assertFalse(self.call('write', 'allowed.txt', text='late')['success'])
        self.assertEqual((self.root / 'allowed.txt').read_text(), 'original')

    def test_adapter_timeout_stops_broker(self):
        with patch.object(codex_control, 'command', return_value=[sys.executable, '-c',
                                                                'import time; time.sleep(10)']):
            result = codex_control.run_fixture(self.broker, 'Do not run a model', timeout=0.05)
        self.assertEqual(result['status'], 'timed_out')
        self.assertFalse(self.call('write', 'allowed.txt', text='late')['success'])
        self.assertEqual((self.root / 'allowed.txt').read_text(), 'original')


if __name__ == '__main__':
    unittest.main()
