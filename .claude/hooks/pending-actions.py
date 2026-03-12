#!/usr/bin/env python3
"""PreToolUse hook: Surfaces pending actions that need Claude's attention.

Checks for:
1. Pending memory saves (.pending-memory-save.json) — workflow outcomes to persist to mem0
2. Doc staleness report (.doc-staleness.json) — docs that may need updating

Non-blocking: outputs a message but does NOT deny the tool call.
Rate-limited: only fires once every 10 minutes to avoid noise.

Fires on: .* (all tools, via PreToolUse)
"""

import json
import os
import sys
import time

_COOLDOWN_SECONDS = 600  # 10 minutes between reminders
_STATE_FILE = ".pending-actions-state.json"


def _artifacts_dir() -> str:
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    return os.path.join(project_dir, ".claude", "artifacts")


def _load_cooldown_state() -> dict:
    path = os.path.join(_artifacts_dir(), _STATE_FILE)
    try:
        with open(path) as f:
            data = json.load(f)
        if data.get("date") == time.strftime("%Y-%m-%d"):
            return data
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return {"date": time.strftime("%Y-%m-%d"), "last_reminder": 0}


def _save_cooldown_state(state: dict):
    path = os.path.join(_artifacts_dir(), _STATE_FILE)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(state, f, indent=2)


def _check_pending_memories() -> str | None:
    path = os.path.join(_artifacts_dir(), ".pending-memory-save.json")
    try:
        with open(path) as f:
            pending = json.load(f)
        if isinstance(pending, list) and len(pending) > 0:
            return f"{len(pending)} workflow outcome(s) in .pending-memory-save.json need persisting to mem0"
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return None


def _check_doc_staleness() -> str | None:
    path = os.path.join(_artifacts_dir(), ".doc-staleness.json")
    try:
        with open(path) as f:
            tracker = json.load(f)
        stale = tracker.get("stale_docs", {})
        if stale:
            docs = ", ".join(stale.keys())
            return f"{len(stale)} doc(s) may be stale: {docs}"
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return None


def main():
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    # Check cooldown
    state = _load_cooldown_state()
    if time.time() - state.get("last_reminder", 0) < _COOLDOWN_SECONDS:
        sys.exit(0)

    # Collect pending actions
    reminders = []
    mem_msg = _check_pending_memories()
    if mem_msg:
        reminders.append(mem_msg)
    doc_msg = _check_doc_staleness()
    if doc_msg:
        reminders.append(doc_msg)

    if not reminders:
        sys.exit(0)

    # Fire: output non-blocking message and update cooldown
    state["last_reminder"] = time.time()
    _save_cooldown_state(state)

    # Use stdout message — NOT a deny decision, just informational
    message = "PENDING ACTIONS:\n" + "\n".join(f"  - {r}" for r in reminders)
    message += "\n\nProcess these when you have a natural pause in your current work."
    # Print to stderr so it shows as hook output without blocking
    print(message, file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    main()
