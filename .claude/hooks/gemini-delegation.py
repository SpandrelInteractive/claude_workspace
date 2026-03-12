#!/usr/bin/env python3
"""PreToolUse hook: Phase 5 — Gemini delegation enforcement.

Enforces CLAUDE.md delegation rules:
  - 3+ file reads → suggest mcp__gemini__analyze_files
  - Clears counter when analyze_files is used

Tracks unique file reads in .throttle-state.json under "files_read" key.
Uses a 5-minute cooldown after firing to avoid repeated blocking.
"""

import json
import os
import sys
import time

_READ_THRESHOLD = 4  # Block on the 5th unique file read
_COOLDOWN_SECONDS = 300  # 5 minutes between blocks


def _state_path() -> str:
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    return os.path.join(project_dir, ".claude", "artifacts", ".throttle-state.json")


def _load_state() -> dict:
    path = _state_path()
    try:
        with open(path) as f:
            data = json.load(f)
        if data.get("date") == time.strftime("%Y-%m-%d"):
            return data
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return {}


def _save_state(state: dict):
    path = _state_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(state, f, indent=2)


def main():
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    # Track Read tool calls
    if tool_name != "Read":
        sys.exit(0)

    state = _load_state()
    if not state:
        sys.exit(0)

    files_read = state.get("files_read", [])
    last_delegation_block = state.get("last_delegation_block", 0)

    # Get the file being read
    file_path = tool_input.get("file_path", "")
    if not file_path:
        sys.exit(0)

    # Skip config/settings files — these are legitimate individual reads
    skip_patterns = (
        ".json", ".toml", ".yaml", ".yml", ".env", ".md",
        "settings", "config", "package", "requirements", "pyproject",
        ".claude/", "CLAUDE.md", "memory/",
    )
    if any(p in file_path for p in skip_patterns):
        sys.exit(0)

    # Add to tracked files (unique only)
    if file_path not in files_read:
        files_read.append(file_path)
        state["files_read"] = files_read
        _save_state(state)

    # Check threshold
    if len(files_read) <= _READ_THRESHOLD:
        sys.exit(0)

    # Check cooldown
    if time.time() - last_delegation_block < _COOLDOWN_SECONDS:
        sys.exit(0)

    # Fire: deny with suggestion
    state["last_delegation_block"] = time.time()
    _save_state(state)

    reason = (
        f"You've read {len(files_read)} unique source files this session.\n"
        "Per CLAUDE.md: 3+ files → use mcp__gemini__analyze_files for bulk comprehension.\n"
        "This is faster and saves Claude context window.\n"
        f"Files read: {', '.join(os.path.basename(f) for f in files_read[-5:])}\n"
        "Retry this Read if you need a specific file, or switch to analyze_files."
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
