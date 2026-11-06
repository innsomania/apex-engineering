#!/usr/bin/env python3
"""Claude Code and Codex hooks - main entry point."""

import json
import sys
from collections.abc import Sequence
from pathlib import Path

from .baseline import baseline
from .guard import guard
from .output import OUTPUT, RUN
from .stop import stop, unlock


def main(argv: Sequence[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    mode = argv[0] if argv else ""
    RUN["host"] = argv[1] if len(argv) > 1 else "claude"
    try:
        event = json.load(sys.stdin)
    except ValueError:
        event = {}
    if not isinstance(event, dict):
        event = {}

    handler = {"baseline": baseline, "stop": stop, "guard": guard, "unlock": unlock}.get(mode)
    if handler is None or RUN["host"] not in {"claude", "codex"}:
        print(f"usage: {Path(sys.argv[0]).name} baseline|stop|guard|unlock [claude|codex]", file=sys.stderr)
        return 1

    handler(event)
    if OUTPUT:
        print(json.dumps(OUTPUT, ensure_ascii=False))
    return 0
