"""Opt-in Codex CLI session with exact project-file permissions."""
import argparse
import json
from pathlib import Path
import signal
import threading

from control import Broker, Denied, relative_path
from codex_control import run_fixture


def _allowlist(parser, label, paths):
    try:
        result = tuple(relative_path(path) for path in paths)
    except Denied as error:
        parser.error(f'invalid {label} path: {error}')
    if len(set(result)) != len(result):
        parser.error(f'{label} paths must be unique')
    return result


def main(argv=None, stop_event=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', type=Path, required=True,
                        help='project directory used as the broker root')
    parser.add_argument('--allow-read', action='append', default=[], metavar='RELATIVE_PATH',
                        help='exact file path the model may read; repeat as needed')
    parser.add_argument('--allow-write', action='append', required=True, metavar='RELATIVE_PATH',
                        help='exact file path the model may write; repeat as needed')
    parser.add_argument('--prompt', required=True, help='task prompt for this isolated session')
    args = parser.parse_args(argv)

    readable = _allowlist(parser, 'read', args.allow_read)
    writable = _allowlist(parser, 'write', args.allow_write)
    try:
        root = args.project_root.expanduser().resolve(strict=True)
    except (OSError, RuntimeError):
        parser.error('project root must be an existing directory')
    if not root.is_dir():
        parser.error('project root must be an existing directory')

    broker = Broker(root, readable=readable, writable=writable)
    stop_event = stop_event if stop_event is not None else threading.Event()
    previous_sigint = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, lambda *_: stop_event.set())
    try:
        try:
            report = run_fixture(broker, args.prompt, stop_event=stop_event)
        except (OSError, RuntimeError) as error:
            report = {'status': 'failed', 'error': str(error), 'broker_events': list(broker.events)}
    finally:
        signal.signal(signal.SIGINT, previous_sigint)
        broker.close()

    print(json.dumps(report, ensure_ascii=False))
    if stop_event.is_set():
        return 130
    return 0 if report.get('status') == 'completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
