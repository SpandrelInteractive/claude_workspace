#!/usr/bin/env python3
"""PostToolUse hook: Track Agent call usage for throttle budget.

Increments model tier counters after successful Agent tool calls.
State file: .claude/artifacts/.throttle-state.json
"""

import json
import os
import sys
import time


def _state_path() -> str:
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    return os.path.join(project_dir, ".claude", "artifacts", ".throttle-state.json")


def _load_state() -> dict:
    path = _state_path()
    if not os.path.exists(path):
        return _new_state()
    try:
        with open(path) as f:
            data = json.load(f)
        if data.get("date") != time.strftime("%Y-%m-%d"):
            return _new_state()
        return data
    except (json.JSONDecodeError, OSError):
        return _new_state()


def _new_state() -> dict:
    return {
        "date": time.strftime("%Y-%m-%d"),
        "profile": os.environ.get("SESSION_BUDGET", "medium"),
        "opus_calls": 0,
        "sonnet_calls": 0,
        "haiku_calls": 0,
        "gemini_calls": 0,
        "total_agent_calls": 0,
        "blocked_calls": 0,
    }


def _save_state(state: dict):
    path = _state_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(state, f, indent=2)


def _get_model_tier(tool_input: dict) -> str:
    """Classify Agent call by model tier."""
    model = tool_input.get("model", "")
    if not model:
        return "default"
    m = model.lower()
    if "opus" in m:
        return "opus"
    if "sonnet" in m:
        return "sonnet"
    if "haiku" in m:
        return "haiku"
    return "default"


def main():
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    # Only track Agent calls
    if tool_name != "Agent":
        sys.exit(0)

    tier = _get_model_tier(tool_input)
    state = _load_state()

    # Increment tier counter
    count_key = f"{tier}_calls"
    if count_key in state:
        state[count_key] = state.get(count_key, 0) + 1
    state["total_agent_calls"] = state.get("total_agent_calls", 0) + 1

    _save_state(state)
    sys.exit(0)


if __name__ == "__main__":
    main()
