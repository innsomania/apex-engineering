"""Parse compact duration strings such as "1h30m" or "45s"."""

import re

_UNITS = {"h": 3600, "m": 60, "s": 1}
_PART = re.compile(r"(\d+)([hms])")


def parse_duration(text: str) -> int:
    """Return the number of seconds in text.

    Units are h, m and s, each at most once, largest first: "2h", "90m", "1h5s", "1h1m1s".
    Anything else, including the empty string, raises ValueError.
    """
    match = _PART.search(text)
    if not match:
        raise ValueError(f"invalid duration: {text!r}")
    value, unit = match.groups()
    return int(value) * _UNITS[unit]
