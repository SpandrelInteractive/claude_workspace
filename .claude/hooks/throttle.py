#!/usr/bin/env python3
"""PreToolUse hook: Adaptive throttle controller.

Enforces per-session budget limits on expensive model usage.
Tracks Agent tool calls by model tier and blocks when limits exceeded.

State file: .claude/artifacts/.throttle-state.json
Budget profile: SESSION_BUDGET env var (default: medium)
"""

import json
import os
import sys
import time

# Budget profiles (mirrors orchestrator-mcp/budgets.py)
PROFILES = {
    "low": {"max_opus_calls": 0, "max_sonnet_calls": 2},
    "medium": {"max_opus_calls": 2, "max_sonnet_calls": 10},
    "high": {"max_opus_calls": 5, "max_sonnet_calls": 25},
    "unlimited": {"max_opus_calls": -1, "max_sonnet_calls": -1},
}

# Cheaper alternatives to suggest when throttled
ALTERNATIVES = {
    "opus": "model='sonnet', or delegate to mcp__gemini__ask_gemini / mcp__gemini__analyze_files",
    "sonnet": "model='haiku', or delegate to mcp__gemini__ask_gemini / mcp__gemini__analyze_files",
}


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
        # Reset on new day
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


def _get_model_tier(tool_input: dict) -> str | None:
    """Extract model tier from Agent tool input. Returns None if not expensive."""
    model = tool_input.get("model", "")
    if not model:
        return None
    m = model.lower()
    if "opus" in m:
        return "opus"
    if "sonnet" in m:
        return "sonnet"
    # haiku and unrecognized models are cheap — don't throttle
    return None


def main():
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    # Only throttle Agent calls with expensive model parameter
    if tool_name != "Agent":
        sys.exit(0)

    tier = _get_model_tier(tool_input)
    if tier is None:
        sys.exit(0)

    state = _load_state()
    profile_name = state.get("profile", "medium")
    profile = PROFILES.get(profile_name, PROFILES["medium"])

    current = state.get(f"{tier}_calls", 0)
    limit = profile.get(f"max_{tier}_calls", -1)

    # -1 means unlimited
    if limit == -1 or current < limit:
        sys.exit(0)

    # Budget exhausted — block and suggest alternative
    state["blocked_calls"] = state.get("blocked_calls", 0) + 1
    _save_state(state)

    alt = ALTERNATIVES.get(tier, "a cheaper model")
    reason = (
        f"Budget limit reached: {current}/{limit} {tier} Agent calls used "
        f"(profile: {profile_name}).\n"
        f"Try: {alt}\n"
        f"Override: set SESSION_BUDGET=high or SESSION_BUDGET=unlimited in .envrc"
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
