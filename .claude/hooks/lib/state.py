"""Shared state management for hooks.

Consolidates 6 state files into 3:
- .session-state.json  — daily-reset state (throttle, read tracker, cooldowns, session validation)
- .persistent-state.json — cross-day state (doc staleness)
- .tasks-state.json — task tracking (unchanged)
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

_SESSION_ID_FILE = Path(os.getenv(
    "SESSION_STATE_FILE",
    os.path.expanduser("~/.claude-session-id"),
))


def artifacts_dir() -> str:
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    return os.path.join(project_dir, ".claude", "artifacts")


def _path(filename: str) -> str:
    return os.path.join(artifacts_dir(), filename)


# ---------------------------------------------------------------------------
# Session state (daily reset)
# ---------------------------------------------------------------------------

_SESSION_STATE_FILE = ".session-state.json"


def _default_session_state() -> dict:
    return {
        "date": time.strftime("%Y-%m-%d"),
        # Session validation (was .session-validated)
        "session": {
            "validated": False,
            "validated_at": None,
            "services": {},
            "context_loaded": [],
        },
        # Throttle counters (was .throttle-state.json)
        "throttle": {
            "profile": os.environ.get("SESSION_BUDGET", "medium"),
            "opus_calls": 0,
            "sonnet_calls": 0,
            "haiku_calls": 0,
            "gemini_calls": 0,
            "total_agent_calls": 0,
            "blocked_calls": 0,
        },
        # Read tracker for gemini delegation (was .read-tracker.json)
        "reads": {
            "files_read": [],
            "last_delegation_block": 0,
        },
        # Pending actions cooldown (was .pending-actions-state.json)
        "pending_actions": {
            "last_reminder": 0,
        },
        # Task gate dismiss flag
        "task_gate_dismissed": False,
    }


def load_session_state() -> dict:
    path = _path(_SESSION_STATE_FILE)
    try:
        with open(path) as f:
            data = json.load(f)
        if data.get("date") == time.strftime("%Y-%m-%d"):
            return data
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return _default_session_state()


def save_session_state(state: dict) -> None:
    path = _path(_SESSION_STATE_FILE)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(state, f, indent=2)


# ---------------------------------------------------------------------------
# Persistent state (cross-day)
# ---------------------------------------------------------------------------

_PERSISTENT_STATE_FILE = ".persistent-state.json"


def load_persistent_state() -> dict:
    path = _path(_PERSISTENT_STATE_FILE)
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {
            "doc_staleness": {"modified_sources": {}, "stale_docs": {}},
            "pending_memory_queue": [],
        }


def save_persistent_state(state: dict) -> None:
    path = _path(_PERSISTENT_STATE_FILE)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(state, f, indent=2)


# ---------------------------------------------------------------------------
# Task state (unchanged structure, different load path)
# ---------------------------------------------------------------------------

_TASK_STATE_FILE = ".tasks-state.json"


def load_task_state() -> dict:
    path = _path(_TASK_STATE_FILE)
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {"tasks": {}, "updated_at": None}


def save_task_state(state: dict) -> None:
    from datetime import datetime
    path = _path(_TASK_STATE_FILE)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    state["updated_at"] = datetime.now().isoformat()
    with open(path, "w") as f:
        json.dump(state, f, indent=2)


# ---------------------------------------------------------------------------
# Session ID file
# ---------------------------------------------------------------------------

def write_session_id(session_id: str) -> None:
    """Write session_id to shared file (once per session)."""
    if not session_id:
        return
    try:
        existing = _SESSION_ID_FILE.read_text().strip()
        if existing == session_id:
            return
    except (FileNotFoundError, PermissionError):
        pass
    try:
        _SESSION_ID_FILE.write_text(session_id)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Breadcrumb compatibility (read by orchestrator-mcp session.py)
# ---------------------------------------------------------------------------

def write_breadcrumb_compat(state: dict) -> None:
    """Write .session-validated breadcrumb for orchestrator-mcp compatibility."""
    session = state.get("session", {})
    if not session.get("validated"):
        return
    path = _path(".session-validated")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = {
        "date": state["date"],
        "timestamp": time.time(),
        "validated_at": session.get("validated_at", ""),
        "services": session.get("services", {}),
        "context_loaded": session.get("context_loaded", []),
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


# ---------------------------------------------------------------------------
# Legacy state migration
# ---------------------------------------------------------------------------

def migrate_legacy_states() -> dict | None:
    """Read legacy state files and return merged session state, or None if no legacy files."""
    adir = artifacts_dir()
    today = time.strftime("%Y-%m-%d")
    state = _default_session_state()
    found_legacy = False

    # Migrate .throttle-state.json
    throttle_path = os.path.join(adir, ".throttle-state.json")
    try:
        with open(throttle_path) as f:
            legacy = json.load(f)
        if legacy.get("date") == today:
            for key in ("opus_calls", "sonnet_calls", "haiku_calls", "gemini_calls",
                        "total_agent_calls", "blocked_calls", "profile"):
                if key in legacy:
                    state["throttle"][key] = legacy[key]
            state["task_gate_dismissed"] = legacy.get("task_gate_dismissed", False)
            found_legacy = True
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass

    # Migrate .read-tracker.json
    read_path = os.path.join(adir, ".read-tracker.json")
    try:
        with open(read_path) as f:
            legacy = json.load(f)
        if legacy.get("date") == today:
            state["reads"]["files_read"] = legacy.get("files_read", [])
            state["reads"]["last_delegation_block"] = legacy.get("last_delegation_block", 0)
            found_legacy = True
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass

    # Migrate .pending-actions-state.json
    pa_path = os.path.join(adir, ".pending-actions-state.json")
    try:
        with open(pa_path) as f:
            legacy = json.load(f)
        if legacy.get("date") == today:
            state["pending_actions"]["last_reminder"] = legacy.get("last_reminder", 0)
            found_legacy = True
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass

    # Migrate .session-validated
    sv_path = os.path.join(adir, ".session-validated")
    try:
        with open(sv_path) as f:
            legacy = json.load(f)
        if legacy.get("date") == today:
            state["session"]["validated"] = True
            state["session"]["validated_at"] = legacy.get("validated_at", "")
            state["session"]["services"] = legacy.get("services", {})
            state["session"]["context_loaded"] = legacy.get("context_loaded", [])
            found_legacy = True
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass

    return state if found_legacy else None
