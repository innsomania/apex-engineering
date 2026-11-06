"""The single JSON object a hook run prints, and the host it runs for."""

from typing import Any

OUTPUT: dict[str, Any] = {}
RUN = {"host": "claude"}  # set once by main() from the command line


def emit(payload: dict[str, Any]) -> None:
    """Merge into the single JSON object main() prints; Claude Code reads one object."""
    for key, value in payload.items():
        if key == "systemMessage" and key in OUTPUT:
            OUTPUT[key] += "\n" + value
        elif key == "hookSpecificOutput" and "additionalContext" in OUTPUT.get(key, {}):
            context = OUTPUT[key]["additionalContext"]
            OUTPUT[key] = {**OUTPUT[key], **value}
            if "additionalContext" in value:
                OUTPUT[key]["additionalContext"] = context + "\n\n" + value["additionalContext"]
        else:
            OUTPUT[key] = value
