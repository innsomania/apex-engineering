"""Bounded file broker. The caller must independently contain all other tools."""
import contextlib
import os
import stat
import threading
import uuid
from collections.abc import Iterable
from pathlib import Path
from typing import Any


class Denied(ValueError):
    pass


def relative_path(value: object) -> str:
    if not isinstance(value, str) or not value or '\\' in value or '\x00' in value:
        raise Denied('Invalid relative path')
    if value.startswith('/') or any(p in ('', '.', '..') for p in value.split('/')):
        raise Denied('Path must be a canonical relative path')
    return value


class Broker:
    """No process, network, delete, permission-change, or resume operation exists.

    stop() and dispatch() are serialized. An already admitted operation may finish
    before stop() returns; no operation is admitted after the stop event.
    """
    def __init__(self, root: str | os.PathLike[str], readable: Iterable[str] = (),
                 writable: Iterable[str] = (), max_bytes: int = 65536, max_calls: int = 100) -> None:
        self._readable = frozenset(relative_path(p) for p in readable)
        self._writable = frozenset(relative_path(p) for p in writable)
        if type(max_bytes) is not int or max_bytes < 1 or type(max_calls) is not int or max_calls < 1:
            raise ValueError('Budgets must be positive integers')
        self._max_bytes, self._remaining = max_bytes, max_calls
        self._lock = threading.RLock()
        self._stopped = False
        self.events: list[dict[str, str]] = []
        self._fd: int | None = os.open(Path(root), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)

    def stop(self) -> None:
        with self._lock:
            if not self._stopped:
                self._stopped = True
                self.events.append({'event': 'stopped'})

    def close(self) -> None:
        with self._lock:
            self.stop()
            if self._fd is not None:
                os.close(self._fd)
                self._fd = None

    def _parent(self, path: str) -> int:
        if self._fd is None:
            raise Denied('Session closed')
        fd = os.dup(self._fd)
        try:
            for part in path.split('/')[:-1]:
                new = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = new
            return fd
        except BaseException:
            os.close(fd)
            raise

    @staticmethod
    def _regular(info: os.stat_result) -> None:
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise Denied('Only regular files with one link are supported')

    def dispatch(self, arguments: object) -> dict[str, Any]:
        with self._lock:
            try:
                if self._stopped:
                    raise Denied('Session stopped; a new trusted session is required')
                if self._remaining <= 0:
                    self.stop()
                    raise Denied('Call budget exhausted')
                self._remaining -= 1
                if not isinstance(arguments, dict):
                    raise Denied('Expected an object')
                operation = arguments.get('operation')
                keys = {'operation', 'path', 'text'} if operation == 'write' else {'operation', 'path'}
                if operation not in ('read', 'write') or set(arguments) != keys:
                    raise Denied('Unsupported operation or fields')
                path = relative_path(arguments['path'])
                allowed = self._writable if operation == 'write' else self._readable
                if path not in allowed:
                    raise Denied('Path is outside the session permission list')
                self.events.append({'event': 'admitted', 'operation': operation, 'path': path})
                parent = self._parent(path)
                name = path.split('/')[-1]
                try:
                    if operation == 'read':
                        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
                        with os.fdopen(fd, 'rb') as stream:
                            self._regular(os.fstat(stream.fileno()))
                            data = stream.read(self._max_bytes + 1)
                        if len(data) > self._max_bytes:
                            raise Denied('File exceeds byte budget')
                        result = data.decode('utf-8')
                    else:
                        if not isinstance(arguments['text'], str):
                            raise Denied('Expected UTF-8 text')
                        data = arguments['text'].encode('utf-8')
                        if len(data) > self._max_bytes:
                            raise Denied('Write exceeds byte budget')
                        mode = 0o600
                        try:
                            info = os.stat(name, dir_fd=parent, follow_symlinks=False)
                            self._regular(info)
                            mode = stat.S_IMODE(info.st_mode) & 0o777
                        except FileNotFoundError:
                            pass
                        temporary = '.apex-' + uuid.uuid4().hex
                        try:
                            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                         mode, dir_fd=parent)
                            with os.fdopen(fd, 'wb') as stream:
                                stream.write(data)
                                stream.flush()
                                os.fsync(stream.fileno())
                            os.replace(temporary, name, src_dir_fd=parent, dst_dir_fd=parent)
                        finally:
                            with contextlib.suppress(FileNotFoundError):
                                os.unlink(temporary, dir_fd=parent)
                        result = 'Written'
                    self.events.append({'event': 'completed', 'operation': operation, 'path': path})
                    return {'success': True, 'text': result}
                finally:
                    os.close(parent)
            except (ValueError, OSError, UnicodeError) as error:
                # No raw OS paths, input text, or credentials in the event trace.
                self.events.append({'event': 'denied', 'reason': type(error).__name__})
                return {'success': False,
                        'text': str(error) if isinstance(error, Denied) else 'File operation rejected'}
