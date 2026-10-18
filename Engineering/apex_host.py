"""Opt-in interactive Engineering host backed by the isolated Codex adapter."""
import argparse
import signal
import sys
import threading
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from codex_control import run_session
from control import Broker, Denied, relative_path


def _allowlist(parser: argparse.ArgumentParser, label: str,
                paths: Sequence[str]) -> tuple[str, ...]:
    try:
        result = tuple(relative_path(path) for path in paths)
    except Denied as error:
        parser.error(f'invalid {label} path: {error}')
    if len(set(result)) != len(result):
        parser.error(f'{label} paths must be unique')
    return result


def main(argv: Sequence[str] | None = None, stop_event: threading.Event | None = None,
         prompt_reader: Callable[[str], str] = input,
         output: Callable[[str], None] = print) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', type=Path, required=True,
                        help='project directory used as the broker root')
    parser.add_argument('--allow-read', action='append', default=[], metavar='RELATIVE_PATH',
                        help='exact file path the model may read; repeat as needed')
    parser.add_argument('--allow-write', action='append', required=True, metavar='RELATIVE_PATH',
                        help='exact file path the model may write; repeat as needed')
    parser.add_argument('--prompt', help='optional initial user turn; later turns are read interactively')
    args = parser.parse_args(argv)

    readable = _allowlist(parser, 'read', args.allow_read)
    writable = _allowlist(parser, 'write', args.allow_write)
    if args.prompt is not None and not args.prompt.strip():
        parser.error('initial prompt must be non-empty text')
    try:
        root = args.project_root.expanduser().resolve(strict=True)
    except (OSError, RuntimeError):
        parser.error('project root must be an existing directory')
    if not root.is_dir():
        parser.error('project root must be an existing directory')

    broker = Broker(root, readable=readable, writable=writable)
    stop_event = stop_event if stop_event is not None else threading.Event()
    previous_sigint = signal.getsignal(signal.SIGINT)
    waiting_for_input = [False]

    def handle_sigint(*_: Any) -> None:
        if waiting_for_input[0]:
            raise KeyboardInterrupt
        stop_event.set()

    def prompt_provider() -> str | None:
        while True:
            waiting_for_input[0] = True
            try:
                prompt = prompt_reader('You> ')
            except EOFError:
                return None
            except KeyboardInterrupt:
                stop_event.set()
                return None
            finally:
                waiting_for_input[0] = False
            if prompt.strip().lower() in (':quit', ':stop'):
                return None
            if prompt.strip():
                return prompt

    def show_turn(turn: dict[str, Any]) -> None:
        for message in turn['messages']:
            output(f"Assistant> {message}")

    signal.signal(signal.SIGINT, handle_sigint)
    try:
        try:
            report = run_session(broker, prompt_provider, stop_event=stop_event,
                                 on_turn=show_turn, initial_prompt=args.prompt)
        except (OSError, RuntimeError, ValueError) as error:
            report = {'status': 'failed', 'error': str(error), 'broker_events': list(broker.events)}
    finally:
        signal.signal(signal.SIGINT, previous_sigint)
        broker.close()

    if report.get('status') == 'failed' and report.get('error'):
        print(f"Controlled Engineering host failed: {report['error']}", file=sys.stderr)
    elif report.get('status') == 'interrupted':
        output('Controlled turn interrupted; completed file writes remain in place.')
    elif report.get('status') in ('stopped', 'stopped_before_turn'):
        output('Controlled session stopped.')

    if stop_event.is_set() or report.get('status') in ('interrupted', 'stopped', 'stopped_before_turn'):
        return 130
    return 0 if report.get('status') in ('completed', 'closed') else 1


if __name__ == '__main__':
    raise SystemExit(main())
