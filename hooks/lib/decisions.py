"""Hook decision formatting utilities."""

from __future__ import annotations

import json
import sys


def deny(reason: str) -> None:
    """Print deny decision and exit."""
    result = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    print(json.dumps(result))
    sys.exit(0)


def allow() -> None:
    """Allow the tool call and exit."""
    sys.exit(0)


def message(text: str) -> None:
    """Print informational message (non-blocking) and exit."""
    print(text, file=sys.stderr)
    sys.exit(0)
