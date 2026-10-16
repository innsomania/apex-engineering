"""Experimental Codex 0.162.0 stdio adapter; not a global desktop sandbox.

Only call this adapter with isolated fixtures until host bypass coverage is complete.
The file broker's rules do not imply containment of native Codex tools.
"""
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import tempfile
import threading
import time
import tomllib

DISABLED = (
    'apps plugins plugin_hooks codex_hooks hooks browser_use browser_use_external '
    'in_app_browser computer_use connectors enable_mcp_apps code_mode code_mode_only '
    'js_repl shell_tool unified_exec experimental_use_unified_exec_tool apply_patch_freeform '
    'multi_agent multi_agent_v2 collab enable_fanout request_permissions request_permissions_tool '
    'search_tool standalone_web_search web_search web_search_cached web_search_request '
    'image_generation imagegenext view_image memories memory_tool tool_suggest tool_search '
    'remote_control remote_plugin workspace_dependencies worktrees'
).split()

TOOL = {
    'name': 'apex_file',
    'description': 'Read or write an explicitly permitted relative UTF-8 file. No other operations.',
    'inputSchema': {'type': 'object', 'properties': {
        'operation': {'type': 'string', 'enum': ['read', 'write']},
        'path': {'type': 'string'}, 'text': {'type': 'string'}},
        'required': ['operation', 'path'], 'additionalProperties': False},
}

INFORMATIONAL_NOTIFICATIONS = {
    'remoteControl/status/changed',
    'account/updated',
    'thread/started',
    'deprecationNotice',
    'thread/status/changed',
    'item/agentMessage/delta',
    'turn/moderationMetadata',
    'thread/tokenUsage/updated',
    'account/rateLimits/updated',
}


def command():
    version = subprocess.run(['codex', '--version'], check=True, capture_output=True, text=True, timeout=10)
    if version.stdout.strip() != 'codex-cli 0.162.0':
        raise RuntimeError('Unsupported Codex version; review protocol and controls before use')
    args = ['codex', '--no-daemon', 'app-server', '--stdio']
    overrides = {'approval_policy': 'never', 'sandbox_mode': 'read-only',
                 'web_search': 'disabled', 'features.code_mode_host': True}
    overrides.update({f'features.{feature}': False for feature in DISABLED})
    config_path = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))) / 'config.toml'
    config = tomllib.loads(config_path.read_text()) if config_path.exists() else {}
    for name in config.get('mcp_servers', {}):
        if not re.fullmatch(r'[A-Za-z0-9_-]+', name):
            raise RuntimeError('Unsupported MCP configuration key')
        overrides[f'mcp_servers.{name}.enabled'] = False
    for key, value in overrides.items():
        args += ['-c', key + '=' + json.dumps(value)]
    return args


def verify_effective_config(effective):
    """Fail closed if a host config override was ignored or an MCP server is active."""
    if not isinstance(effective, dict):
        raise RuntimeError('Codex returned an invalid effective configuration')
    if (effective.get('approval_policy') != 'never'
            or effective.get('sandbox_mode') != 'read-only'
            or effective.get('web_search') != 'disabled'):
        raise RuntimeError('Effective host configuration is not restricted')
    features = effective.get('features') or {}
    if not isinstance(features, dict) or any(features.get(name) is not False for name in DISABLED):
        raise RuntimeError('A disabled native feature is enabled or unverified')
    servers = effective.get('mcp_servers') or {}
    if not isinstance(servers, dict) or any(
            not isinstance(server, dict) or server.get('enabled', True) is not False
            for server in servers.values()):
        raise RuntimeError('Effective MCP configuration is not disabled')


def dispatch_tool_call(broker, params, thread_id, turn_id, seen_calls):
    """Route only fresh calls for this turn to the bounded file broker."""
    call_id = params.get('callId') if isinstance(params, dict) else None
    fresh = isinstance(call_id, str) and call_id not in seen_calls
    if isinstance(call_id, str):
        seen_calls.add(call_id)
    established_turn = (isinstance(thread_id, str) and bool(thread_id)
                        and isinstance(turn_id, str) and bool(turn_id))
    valid = (fresh and established_turn
             and params.get('threadId') == thread_id and params.get('turnId') == turn_id
             and params.get('tool') == 'apex_file' and not params.get('namespace'))
    if valid:
        return broker.dispatch(params.get('arguments'))
    return {'success': False, 'text': 'Unrecognized tool call or replay'}


def _command_targets_path(item, path):
    if not path:
        return False
    command = item.get('command')
    if isinstance(command, str):
        return path in command
    if isinstance(command, (list, tuple)):
        return path in ' '.join(part for part in command if isinstance(part, str))
    return False


def run_fixture(broker, prompt, stop_event=None, timeout=90, on_tool=None, direct_write_target=None):
    """Run one isolated turn. ``on_tool`` is a trusted test hook only."""
    return _run_session(broker, prompt, None, stop_event, timeout, on_tool, direct_write_target, None)


def run_session(broker, prompt_provider, stop_event=None, timeout=90, on_tool=None,
                direct_write_target=None, on_turn=None, initial_prompt=None):
    """Run successive user turns on one thread until the provider returns None.

    The provider is trusted host code and is called only between turns. ``on_tool``
    and ``on_turn`` are also trusted host hooks, never derived from model input.
    """
    if not callable(prompt_provider):
        raise TypeError('prompt_provider must be callable')
    if initial_prompt is not None and (not isinstance(initial_prompt, str) or not initial_prompt.strip()):
        raise ValueError('Prompts must be non-empty text')
    return _run_session(broker, initial_prompt, prompt_provider, stop_event, timeout, on_tool,
                        direct_write_target, on_turn)


def _run_session(broker, first_prompt, prompt_provider, stop_event, timeout, on_tool,
                 direct_write_target, on_turn):
    """Own one App Server process and thread for a bounded interactive session."""
    stop_event = stop_event if stop_event is not None else threading.Event()
    report = {'status': 'failed', 'events': [], 'messages': []}
    thread_id = turn_id = None
    interrupted = False
    interrupt_request_id = None
    turn_request_id = 3
    next_request_id = 10
    turn_message_start = 0
    seen_calls = set()
    with tempfile.TemporaryDirectory(prefix='apex-controller-') as cwd, tempfile.TemporaryFile() as errors:
        try:
            process = subprocess.Popen(command(), cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                       stderr=errors, text=True, bufsize=1)
        except BaseException:
            broker.stop()
            raise
        incoming = queue.Queue()
        def reader():
            try:
                for line in process.stdout:
                    incoming.put(json.loads(line))
            except (ValueError, OSError):
                incoming.put({'error': {'message': 'Invalid server stream'}})
            finally:
                incoming.put(None)
        worker = threading.Thread(target=reader, daemon=True)
        worker.start()
        def send(message):
            process.stdin.write(json.dumps(message) + '\n')
            process.stdin.flush()
        def stop():
            nonlocal interrupted, interrupt_request_id, next_request_id
            broker.stop()
            if turn_id and not interrupted:
                interrupt_request_id = 9 if next_request_id == 10 else next_request_id
                next_request_id += 1
                send({'id': interrupt_request_id, 'method': 'turn/interrupt',
                      'params': {'threadId': thread_id, 'turnId': turn_id}})
                interrupted = True
                report['events'].append('interrupt_requested')

        def ask_for_prompt():
            try:
                prompt_text = prompt_provider()
            except KeyboardInterrupt:
                stop_event.set()
                return None
            if prompt_text is not None and (not isinstance(prompt_text, str) or not prompt_text.strip()):
                raise ValueError('Prompts must be non-empty text')
            return prompt_text

        def fail_closed(event, message):
            stop()
            report['events'].append(event)
            report['status'] = 'failed'
            report['error'] = message

        deadline = time.monotonic() + timeout
        try:
            send({'id': 1, 'method': 'initialize', 'params': {
                'clientInfo': {'name': 'apex_control', 'version': '0.1.0'},
                'capabilities': {'experimentalApi': True}}})
            while time.monotonic() < deadline:
                if stop_event.is_set():
                    stop()
                    if not thread_id:
                        report['status'] = 'stopped_before_turn'
                        break
                try:
                    msg = incoming.get(timeout=0.05)
                except queue.Empty:
                    continue
                if msg is None:
                    raise RuntimeError('Codex closed the control stream')
                if not isinstance(msg, dict):
                    fail_closed('malformed_message_denied', 'Codex sent a malformed control message')
                    break
                if 'error' in msg:
                    fail_closed('server_error_denied', 'Codex rejected a control request')
                    break
                method, params = msg.get('method'), msg.get('params', {})
                if method is not None and (not isinstance(method, str) or not method):
                    fail_closed('malformed_message_denied', 'Codex sent a malformed control method')
                    break
                if (method in INFORMATIONAL_NOTIFICATIONS
                        and ('params' not in msg or not isinstance(msg['params'], dict))):
                    fail_closed('malformed_message_denied', 'Codex sent malformed informational notification data')
                    break
                if method is not None and not isinstance(params, dict):
                    fail_closed('malformed_message_denied', 'Codex sent malformed control parameters')
                    break
                turn_notifications = {'turn/started', 'item/started', 'item/completed', 'turn/completed'}
                notifications = turn_notifications | INFORMATIONAL_NOTIFICATIONS
                if (method in turn_notifications
                        and not isinstance(params.get('turn', params.get('item')), dict)):
                    fail_closed('malformed_message_denied', 'Codex sent malformed turn or item data')
                    break
                if method in notifications and 'id' in msg:
                    fail_closed('unexpected_request_denied', 'Codex sent a request where a notification was expected')
                    break
                if method is not None and method not in notifications and method != 'item/tool/call' and 'id' not in msg:
                    fail_closed('unsupported_notification_denied', 'Codex sent an unsupported notification')
                    break
                if method == 'item/tool/call':
                    valid_call = (type(msg.get('id')) in (int, str)
                                  and isinstance(params.get('callId'), str) and bool(params['callId'])
                                  and isinstance(params.get('threadId'), str) and bool(params['threadId'])
                                  and isinstance(params.get('turnId'), str) and bool(params['turnId'])
                                  and isinstance(params.get('tool'), str) and 'arguments' in params)
                    if not valid_call:
                        fail_closed('malformed_message_denied', 'Codex sent a malformed tool call')
                        break
                if msg.get('id') == 1 and 'result' in msg:
                    if not isinstance(msg['result'], dict):
                        fail_closed('malformed_message_denied', 'Codex returned an invalid initialize response')
                        break
                    send({'method': 'initialized', 'params': {}})
                    send({'id': 4, 'method': 'config/read', 'params': {'includeLayers': False, 'cwd': cwd}})
                elif msg.get('id') == 4 and 'result' in msg:
                    if not isinstance(msg['result'], dict):
                        fail_closed('malformed_message_denied', 'Codex returned an invalid config response')
                        break
                    verify_effective_config(msg['result'].get('config'))
                    send({'id': 2, 'method': 'thread/start', 'params': {
                        'cwd': cwd, 'environments': [], 'ephemeral': True,
                        'approvalPolicy': 'never', 'sandbox': 'read-only', 'dynamicTools': [TOOL]}})
                elif msg.get('id') == 2 and 'result' in msg:
                    result = msg['result']
                    if not isinstance(result, dict) or not isinstance(result.get('sandbox'), dict) \
                            or not isinstance(result.get('thread'), dict) \
                            or not isinstance(result.get('approvalPolicy'), str):
                        fail_closed('malformed_message_denied', 'Codex returned an invalid thread response')
                        break
                    sandbox = result['sandbox']
                    if (sandbox.get('type') != 'readOnly' or sandbox.get('networkAccess') is not False
                            or result['approvalPolicy'] != 'never' or result.get('runtimeWorkspaceRoots')):
                        raise RuntimeError('Host did not accept required restrictions')
                    report['host'] = {'sandbox': sandbox, 'approvalPolicy': result['approvalPolicy']}
                    thread_id = result['thread']['id']
                    if not isinstance(thread_id, str) or not thread_id:
                        fail_closed('malformed_message_denied', 'Codex returned an invalid thread ID')
                        break
                    if stop_event.is_set():
                        report['status'] = 'stopped_before_turn'
                        break
                    prompt_text = first_prompt if first_prompt is not None or prompt_provider is None else ask_for_prompt()
                    if stop_event.is_set():
                        report['status'] = 'stopped_before_turn'
                        break
                    if prompt_text is None:
                        report['status'] = 'closed'
                        report['events'].append('session_exit_requested')
                        break
                    deadline = time.monotonic() + timeout
                    send({'id': 3, 'method': 'turn/start', 'params': {
                        'threadId': thread_id, 'environments': [],
                        'input': [{'type': 'text', 'text': prompt_text}]}})
                elif ((msg.get('id') == turn_request_id and 'result' in msg) or method == 'turn/started'):
                    turn_source = msg.get('result') or params
                    if not isinstance(turn_source, dict):
                        fail_closed('malformed_message_denied', 'Codex returned malformed turn data')
                        break
                    turn_data = turn_source.get('turn')
                    if not isinstance(turn_data, dict) or not isinstance(turn_data.get('id'), str) \
                            or not turn_data['id'] or (turn_id and turn_id != turn_data['id']):
                        fail_closed('malformed_message_denied', 'Codex returned an invalid turn ID')
                        break
                    turn_id = turn_data['id']
                elif method == 'item/tool/call':
                    if on_tool:
                        on_tool(params, stop_event)
                    if stop_event.is_set():
                        stop()
                    result = dispatch_tool_call(broker, params, thread_id, turn_id, seen_calls)
                    report['events'].append('tool_accepted' if result['success'] else 'tool_denied')
                    if not isinstance(params, dict) or params.get('tool') != TOOL['name'] or params.get('namespace'):
                        report['events'].append('unsupported_tool_denied')
                    send({'id': msg['id'], 'result': {'success': result['success'],
                          'contentItems': [{'type': 'inputText', 'text': result['text']}]}})
                elif method in ('item/started', 'item/completed'):
                    item = params.get('item')
                    if isinstance(item, dict):
                        item_type = item.get('type')
                        if item_type in ('commandExecution', 'command_execution'):
                            report['events'].append('native_command_observed')
                            if _command_targets_path(item, direct_write_target):
                                if 'direct_write_attempt_observed' not in report['events']:
                                    report['events'].append('direct_write_attempt_observed')
                                if method == 'item/completed' and type(item.get('exitCode')) is int:
                                    report['direct_write_exit_code'] = item['exitCode']
                        if method == 'item/completed' and item_type == 'agentMessage':
                            report['messages'].append(item.get('text', ''))
                elif method == 'turn/completed':
                    turn_data = params['turn']
                    if (not isinstance(turn_data.get('status'), str)
                            or (turn_data.get('id') is not None and turn_data.get('id') != turn_id)):
                        fail_closed('malformed_message_denied', 'Codex returned an invalid turn completion')
                        break
                    turn_status = turn_data['status']
                    report['status'] = turn_status
                    turn_messages = list(report['messages'][turn_message_start:])
                    report.setdefault('turns', []).append({'status': turn_status, 'messages': turn_messages})
                    if on_turn:
                        on_turn({'status': turn_status, 'messages': turn_messages})
                    turn_id = None
                    interrupted = False
                    if turn_status != 'completed' or prompt_provider is None:
                        break
                    if stop_event.is_set():
                        broker.stop()
                        report['status'] = 'stopped'
                        break
                    prompt_text = ask_for_prompt()
                    if stop_event.is_set():
                        broker.stop()
                        report['status'] = 'stopped'
                        break
                    if prompt_text is None:
                        report['events'].append('session_exit_requested')
                        break
                    turn_request_id = next_request_id
                    next_request_id += 1
                    turn_message_start = len(report['messages'])
                    deadline = time.monotonic() + timeout
                    send({'id': turn_request_id, 'method': 'turn/start', 'params': {
                        'threadId': thread_id, 'environments': [],
                        'input': [{'type': 'text', 'text': prompt_text}]}})
                elif method in INFORMATIONAL_NOTIFICATIONS:
                    # These known App Server notifications carry no host actions; their
                    # JSON-RPC envelope and params object were validated above.
                    continue
                elif interrupt_request_id is not None and msg.get('id') == interrupt_request_id and 'result' in msg:
                    report['events'].append('interrupt_acknowledged')
                elif 'id' in msg and isinstance(method, str):
                    fail_closed('unsupported_request_denied', 'Codex sent an unsupported control request')
                    if type(msg['id']) in (int, str):
                        send({'id': msg['id'], 'error': {'code': -32601, 'message': 'Request denied by Apex'}})
                    break
                else:
                    fail_closed('unexpected_message_denied', 'Codex sent an unexpected control message')
                    break
            else:
                stop()
                report['status'] = 'timed_out'
        finally:
            broker.stop()
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            worker.join(timeout=2)
            process.stdin.close()
            process.stdout.close()
    report['broker_events'] = list(broker.events)
    return report
