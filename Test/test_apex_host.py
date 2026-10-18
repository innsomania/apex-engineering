"""Focused tests for the persistent opt-in Engineering CLI host."""
import json
import queue
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Engineering'))
import apex_host
import codex_control
from control import Broker

OBSERVED_NOTIFICATION_METHODS = [
    'remoteControl/status/changed',
    'account/updated',
    'thread/started',
    'deprecationNotice',
    'thread/status/changed',
    'item/agentMessage/delta',
    'turn/moderationMetadata',
    'thread/tokenUsage/updated',
    'account/rateLimits/updated',
]


class FakeStdout:
    def __init__(self):
        self.messages = queue.Queue()

    def __iter__(self):
        while True:
            message = self.messages.get()
            if message is None:
                return
            yield json.dumps(message) + '\n'

    def close(self):
        self.messages.put(None)


class FakeStdin:
    def __init__(self, process):
        self.process = process
        self.messages = []

    def write(self, value):
        message = json.loads(value)
        self.messages.append(message)
        self.process.receive(message)
        return len(value)

    def flush(self):
        pass

    def close(self):
        pass


class FakeCodex:
    """Small request-driven App Server fake; no model or external service."""
    def __init__(self, native_target=None, unexpected_request=False, malformed_message=False,
                 observed_notifications=False, malformed_notification=False):
        self.stdout = FakeStdout()
        self.stdin = FakeStdin(self)
        self.turn_number = 0
        self.pending_calls = {}
        self.native_target = native_target
        self.unexpected_request = unexpected_request
        self.malformed_message = malformed_message
        self.observed_notifications = observed_notifications
        self.malformed_notification = malformed_notification
        self.emitted_notifications = []
        self.interrupted = False
        self._lock = threading.Lock()

    def emit(self, message):
        self.stdout.messages.put(message)

    def emit_observed_notifications(self, start, end):
        if not self.observed_notifications:
            return
        for method in OBSERVED_NOTIFICATION_METHODS[start:end]:
            self.emitted_notifications.append(method)
            self.emit({'method': method, 'params': {}})

    def receive(self, message):
        method = message.get('method')
        if method == 'initialize':
            if self.malformed_message:
                self.emit(['malformed'])
                return
            self.emit({'id': message['id'], 'result': {}})
            if self.malformed_notification:
                self.emit({'method': 'account/updated', 'params': []})
                return
            self.emit_observed_notifications(0, 2)
        elif method == 'config/read':
            config = {
                'approval_policy': 'never', 'sandbox_mode': 'read-only', 'web_search': 'disabled',
                'features': {name: False for name in codex_control.DISABLED}, 'mcp_servers': {},
            }
            self.emit({'id': message['id'], 'result': {'config': config}})
        elif method == 'thread/start':
            self.emit({'id': message['id'], 'result': {
                'sandbox': {'type': 'readOnly', 'networkAccess': False},
                'approvalPolicy': 'never', 'runtimeWorkspaceRoots': [], 'thread': {'id': 'one-thread'},
            }})
            self.emit_observed_notifications(2, 4)
        elif method == 'turn/start':
            self._start_turn(message)
        elif method == 'turn/interrupt':
            self.interrupted = True
            self.emit({'id': message['id'], 'result': {}})
            self.emit({'method': 'turn/completed', 'params': {'turn': {'status': 'interrupted'}}})
        elif message.get('id') in self.pending_calls:
            self.pending_calls.pop(message['id'])
            if not self.pending_calls and not self.interrupted:
                self.emit({'method': 'item/completed', 'params': {'item': {
                    'type': 'agentMessage', 'text': f'answer {self.turn_number}',
                }}})
                self.emit({'method': 'turn/completed', 'params': {'turn': {'status': 'completed'}}})

    def _start_turn(self, message):
        self.turn_number += 1
        self.interrupted = False
        turn_id = f'turn-{self.turn_number}'
        self.emit({'id': message['id'], 'result': {'turn': {'id': turn_id}}})
        self.emit({'method': 'turn/started', 'params': {'turn': {'id': turn_id}}})
        self.emit_observed_notifications(4, None)

        if self.native_target and self.turn_number == 1:
            command = ['sh', '-c', f'printf bypass > {self.native_target}']
            self.emit({'method': 'item/started', 'params': {'item': {
                'type': 'commandExecution', 'command': command,
            }}})
            self.emit({'method': 'item/completed', 'params': {'item': {
                'type': 'commandExecution', 'command': command, 'exitCode': 1,
            }}})

        if self.unexpected_request and self.turn_number == 1:
            self.emit({'id': 777, 'method': 'shell/exec', 'params': {'command': 'unexpected'}})
            return

        if self.turn_number == 1:
            calls = [
                ('apex_file', {'operation': 'write', 'path': 'allowed.txt', 'text': 'turn one'}),
                ('apex_file', {'operation': 'write', 'path': 'canary.txt', 'text': 'denied'}),
                ('exec_command', {'command': 'printf bypass > canary.txt'}),
            ]
        else:
            calls = [('apex_file', {'operation': 'write', 'path': 'allowed.txt', 'text': 'turn two'})]

        self.pending_calls = {}
        for index, (tool, arguments) in enumerate(calls):
            call_request_id = self.turn_number * 100 + index + 1
            self.pending_calls[call_request_id] = tool
            self.emit({'id': call_request_id, 'method': 'item/tool/call', 'params': {
                'threadId': 'one-thread', 'turnId': turn_id,
                'callId': f'call-{self.turn_number}-{index}', 'tool': tool,
                'arguments': arguments,
            }})

    def terminate(self):
        self.stdout.messages.put(None)

    def wait(self, timeout=None):
        return 0


class ApexHostTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'allowed.txt').write_text('original')
        (self.root / 'canary.txt').write_text('protected')

    def test_interactive_host_runs_two_turns_on_one_thread_and_brokers_exact_writes(self):
        process = FakeCodex()
        prompts = iter(['second request', ':quit'])
        output = []
        broker_calls = []
        original_dispatch = Broker.dispatch

        def record_dispatch(broker, arguments):
            broker_calls.append(arguments)
            return original_dispatch(broker, arguments)

        args = ['--project-root', str(self.root), '--allow-read', 'allowed.txt',
                '--allow-write', 'allowed.txt', '--prompt', 'first request']
        with patch.object(Broker, 'dispatch', record_dispatch):
            with patch.object(codex_control, 'command', return_value=['fake-codex']):
                with patch.object(codex_control.subprocess, 'Popen', return_value=process):
                    status = apex_host.main(args, prompt_reader=lambda _prompt: next(prompts), output=output.append)

        self.assertEqual(status, 0)
        turns = [message for message in process.stdin.messages if message.get('method') == 'turn/start']
        self.assertEqual(len(turns), 2)
        self.assertEqual([message['params']['threadId'] for message in turns], ['one-thread', 'one-thread'])
        self.assertEqual([message['params']['input'][0]['text'] for message in turns],
                         ['first request', 'second request'])
        self.assertEqual((self.root / 'allowed.txt').read_text(), 'turn two')
        self.assertEqual((self.root / 'canary.txt').read_text(), 'protected')
        self.assertEqual([call['path'] for call in broker_calls],
                         ['allowed.txt', 'canary.txt', 'allowed.txt'])
        self.assertEqual(output, ['Assistant> answer 1', 'Assistant> answer 2'])

    def test_observed_app_server_notifications_are_accepted(self):
        process = FakeCodex(observed_notifications=True)
        broker = Broker(self.root, writable=['allowed.txt'])
        self.addCleanup(broker.close)
        with patch.object(codex_control, 'command', return_value=['fake-codex']):
            with patch.object(codex_control.subprocess, 'Popen', return_value=process):
                report = codex_control.run_session(
                    broker, lambda: None, initial_prompt='exercise observed notifications')

        self.assertEqual(process.emitted_notifications, OBSERVED_NOTIFICATION_METHODS)
        self.assertEqual(report['status'], 'completed')
        self.assertNotIn('unsupported_notification_denied', report['events'])
        self.assertEqual((self.root / 'allowed.txt').read_text(), 'turn one')
        self.assertEqual((self.root / 'canary.txt').read_text(), 'protected')

    def test_invalid_policy_is_rejected_before_codex_starts(self):
        cases = [
            ['--allow-write', '../canary.txt'],
            ['--allow-write', 'allowed.txt', '--allow-write', 'allowed.txt'],
            ['--allow-write', 'allowed.txt', '--allow-read', '/absolute/path'],
            ['--allow-write', 'allowed.txt', '--prompt', '   '],
        ]
        for policy in cases:
            with self.subTest(policy=policy):
                args = ['--project-root', str(self.root), *policy]
                with patch.object(apex_host, 'run_session') as launch:
                    with redirect_stderr(StringIO()):
                        with self.assertRaises(SystemExit) as error:
                            apex_host.main(args)
                self.assertNotEqual(error.exception.code, 0)
                launch.assert_not_called()

        args = ['--project-root', str(self.root / 'missing'), '--allow-write', 'allowed.txt']
        with patch.object(apex_host, 'run_session') as launch:
            with redirect_stderr(StringIO()):
                with self.assertRaises(SystemExit) as error:
                    apex_host.main(args)
        self.assertNotEqual(error.exception.code, 0)
        launch.assert_not_called()

    def test_unsupported_tool_and_native_command_attempt_are_classified(self):
        target = str(self.root / 'canary.txt')
        process = FakeCodex(native_target=target)
        broker = Broker(self.root, readable=['allowed.txt'], writable=['allowed.txt'])
        self.addCleanup(broker.close)
        prompts = iter(['inspect', None])
        with patch.object(codex_control, 'command', return_value=['fake-codex']):
            with patch.object(codex_control.subprocess, 'Popen', return_value=process):
                report = codex_control.run_session(
                    broker, lambda: next(prompts), direct_write_target=target)

        self.assertEqual(report['status'], 'completed')
        self.assertIn('unsupported_tool_denied', report['events'])
        self.assertIn('native_command_observed', report['events'])
        self.assertIn('direct_write_attempt_observed', report['events'])
        self.assertEqual(report['direct_write_exit_code'], 1)
        self.assertEqual((self.root / 'canary.txt').read_text(), 'protected')
        self.assertEqual([event['path'] for event in report['broker_events']
                          if event['event'] == 'completed'], ['allowed.txt'])

    def test_trusted_stop_interrupts_turn_and_denies_pending_write(self):
        process = FakeCodex()
        broker = Broker(self.root, writable=['allowed.txt'])
        self.addCleanup(broker.close)
        stop_event = threading.Event()

        def stop_at_call(_params, event):
            event.set()

        with patch.object(codex_control, 'command', return_value=['fake-codex']):
            with patch.object(codex_control.subprocess, 'Popen', return_value=process):
                report = codex_control.run_session(
                    broker, lambda: 'stop test', stop_event=stop_event, on_tool=stop_at_call)

        self.assertEqual(report['status'], 'interrupted')
        self.assertIn('interrupt_requested', report['events'])
        self.assertIn('interrupt_acknowledged', report['events'])
        self.assertEqual((self.root / 'allowed.txt').read_text(), 'original')
        stopped = next(index for index, event in enumerate(report['broker_events'])
                       if event['event'] == 'stopped')
        self.assertFalse(any(event['event'] == 'admitted'
                             for event in report['broker_events'][stopped + 1:]))

    def test_malformed_and_unexpected_server_messages_fail_closed(self):
        cases = ((FakeCodex(malformed_message=True), None),
                 (FakeCodex(unexpected_request=True), 'trigger request'),
                 (FakeCodex(malformed_notification=True), 'trigger request'))
        for process, initial_prompt in cases:
            with self.subTest(initial_prompt=initial_prompt):
                broker = Broker(self.root, writable=['allowed.txt'])
                self.addCleanup(broker.close)
                prompts = iter([])
                with patch.object(codex_control, 'command', return_value=['fake-codex']):
                    with patch.object(codex_control.subprocess, 'Popen', return_value=process):
                        report = codex_control.run_session(
                            broker, lambda p=prompts: next(p), initial_prompt=initial_prompt)

                self.assertEqual(report['status'], 'failed')
                self.assertTrue(any(event.endswith('_denied') for event in report['events']))
                self.assertEqual((self.root / 'allowed.txt').read_text(), 'original')
                self.assertFalse(broker.dispatch({
                    'operation': 'write', 'path': 'allowed.txt', 'text': 'late',
                })['success'])


if __name__ == '__main__':
    unittest.main()
