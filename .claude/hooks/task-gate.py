#!/usr/bin/env python3
"""PreToolUse hook: Phase 3 — Workflow/task enforcement.

One-time reminder when 5+ Agent calls are made without any task tracking
or workflow usage. Fires once per session, then writes a dismiss flag.

Encourages structured work (TaskCreate or run_workflow) for complex tasks.
"""

import json
import os
import sys
import time

_STATE_FILE = ".throttle-state.json"
_TASK_STATE_FILE = ".tasks-state.json"
_DISMISS_KEY = "task_gate_dismissed"

# Tools that indicate structured work is already happening
_STRUCTURED_TOOLS = {
    "mcp__orchestrator__run_workflow",
    "mcp__orchestrator__workflow_status",
}

# Threshold: after this many Agent calls without structure, fire once
_AGENT_THRESHOLD = 5


def _artifacts_dir() -> str:
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    return os.path.join(project_dir, ".claude", "artifacts")


def _load_throttle_state() -> dict:
    path = os.path.join(_artifacts_dir(), _STATE_FILE)
    try:
        with open(path) as f:
            data = json.load(f)
        if data.get("date") == time.strftime("%Y-%m-%d"):
            return data
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return {}


def _save_throttle_state(state: dict):
    path = os.path.join(_artifacts_dir(), _STATE_FILE)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(state, f, indent=2)


def _has_task_tracking() -> bool:
    """Check if tasks have been created this session."""
    path = os.path.join(_artifacts_dir(), _TASK_STATE_FILE)
    if not os.path.exists(path):
        return False
    try:
        with open(path) as f:
            data = json.load(f)
        return len(data.get("tasks", {})) > 0
    except (json.JSONDecodeError, OSError):
        return False


def main():
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")

    # Only check Agent calls
    if tool_name != "Agent":
        sys.exit(0)

    state = _load_throttle_state()

    # Already dismissed this session — skip
    if state.get(_DISMISS_KEY):
        sys.exit(0)

    # Check if structured work is happening
    if _has_task_tracking():
        sys.exit(0)

    # Check agent call count
    total = state.get("total_agent_calls", 0)
    if total < _AGENT_THRESHOLD:
        sys.exit(0)

    # Fire once: deny with suggestion, then set dismiss flag
    state[_DISMISS_KEY] = True
    _save_throttle_state(state)

    reason = (
        f"You've spawned {total} Agent subprocesses without structured tracking.\n"
        "For complex multi-step work, consider:\n"
        "  - TaskCreate to track progress across steps\n"
        "  - run_workflow for managed multi-agent execution\n"
        "This gate fires once per session. Retry your Agent call to proceed."
    )

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
