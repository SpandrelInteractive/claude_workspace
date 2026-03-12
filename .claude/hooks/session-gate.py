#!/usr/bin/env python3
"""PreToolUse hook: Hard-block ALL tools until session is validated.

Exit code 2 = tool call BLOCKED.
Only validate_system and init_session are allowed through before validation.
"""

import json
import os
import sys
import time


def _breadcrumb_path() -> str:
    """Get the session breadcrumb file path."""
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    return os.path.join(project_dir, ".claude", "artifacts", ".session-validated")


def _is_validated() -> bool:
    """Check if today's session breadcrumb exists."""
    path = _breadcrumb_path()
    if not os.path.exists(path):
        return False
    try:
        with open(path) as f:
            data = json.load(f)
        return data.get("date") == time.strftime("%Y-%m-%d")
    except (json.JSONDecodeError, OSError):
        return False


# Tools that are allowed BEFORE session validation
_WHITELIST = {
    "mcp__orchestrator__validate_system",
    "mcp__orchestrator__init_session",
    # Bootstrap: allow ToolSearch so deferred tools can be loaded
    "ToolSearch",
}

# First-time setup: if the hook infrastructure itself is being set up
# (no breadcrumb dir exists yet), allow through to avoid deadlock
_BOOTSTRAP_FLAG = ".mao-bootstrap"


def main():
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        # Can't parse input — allow through to avoid breaking things
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")

    # Always allow whitelisted tools
    if tool_name in _WHITELIST:
        sys.exit(0)

    # Bootstrap escape: if .mao-bootstrap exists in project root, skip gate
    # This allows first-time setup to complete. Remove file after setup.
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    bootstrap_path = os.path.join(project_dir, _BOOTSTRAP_FLAG)
    if os.path.exists(bootstrap_path):
        sys.exit(0)

    # Check if session is validated
    if _is_validated():
        sys.exit(0)

    # Session NOT validated — block the tool call
    reason = (
        f"Session not initialized. Tool '{tool_name}' is blocked.\n"
        "You MUST call init_session from orchestrator-mcp before any other action.\n"
        "This validates that all infrastructure services are healthy."
    )

    # Use JSON permission decision for clean blocking
    result = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    print(json.dumps(result))
    sys.exit(0)


if __name__ == "__main__":
    main()
