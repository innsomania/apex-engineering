"""Shared type definitions to avoid circular imports."""

from typing import Any

# Hook events and the state file are free-form JSON from the host.
Event = dict[str, Any]
State = dict[str, Any]
