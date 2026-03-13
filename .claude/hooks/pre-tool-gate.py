#!/usr/bin/env python3
"""Consolidated PreToolUse hook.

Replaces 6 individual hooks:
  1. session-gate.py — session validation + session_id write
  2. pending-actions.py — pending memory/doc staleness reminders
  3. throttle.py — Agent budget enforcement
  4. model-gate.py — model selection enforcement
  5. task-gate.py — task tracking nudge
  6. gemini-delegation.py — Read delegation enforcement

Runs on matcher: .* (all tools)
Timeout: 2000ms
"""

import json
import os
import sys
import time

# Add hooks dir to path for lib imports
sys.path.insert(0, os.path.dirname(__file__))

from lib.state import (
    load_session_state,
    save_session_state,
    load_persistent_state,
    write_session_id,
    write_breadcrumb_compat,
    migrate_legacy_states,
)
from lib.decisions import deny, allow, message


# ── Constants ──────────────────────────────────────────────────────────────

# Session gate whitelist
_WHITELIST = {
    "mcp__orchestrator__validate_system",
    "mcp__orchestrator__init_session",
    "ToolSearch",
}

_BOOTSTRAP_FLAG = ".mao-bootstrap"

# Throttle budget profiles
PROFILES = {
    "low": {"max_opus_calls": 0, "max_sonnet_calls": 2},
    "medium": {"max_opus_calls": 2, "max_sonnet_calls": 10},
    "high": {"max_opus_calls": 5, "max_sonnet_calls": 25},
    "unlimited": {"max_opus_calls": -1, "max_sonnet_calls": -1},
}

ALTERNATIVES = {
    "opus": "model='sonnet', or delegate to mcp__gemini__ask_gemini / mcp__gemini__analyze_files",
    "sonnet": "model='haiku', or delegate to mcp__gemini__ask_gemini / mcp__gemini__analyze_files",
}

# Model gate keywords
_OPUS_KEYWORDS = {
    "debug", "ambiguous", "architecture", "sign-off", "final decision",
    "complex analysis", "design review", "root cause", "investigate",
    "diagnose", "critical", "production issue",
}

_SONNET_KEYWORDS = {
    "implement", "refactor", "test", "multi-file", "migration",
    "rewrite", "convert", "build", "create feature", "add feature",
    "fix bug", "write tests", "integration",
}

_CHEAP_SUBAGENTS = {"Explore", "Plan", "claude-code-guide", "statusline-setup"}

# Gemini delegation
_READ_THRESHOLD = 4
_READ_COOLDOWN_SECONDS = 300

# Pending actions
_PENDING_COOLDOWN_SECONDS = 600

# Task gate
_AGENT_THRESHOLD = 5

# Read file patterns to skip (config/settings — legitimate individual reads)
_READ_SKIP_PATTERNS = (
    ".json", ".toml", ".yaml", ".yml", ".env", ".md",
    "settings", "config", "package", "requirements", "pyproject",
    ".claude/", "CLAUDE.md", "memory/",
)


# ── Gate functions ─────────────────────────────────────────────────────────

def gate_session(tool_name: str, state: dict) -> None:
    """Block all tools until session is validated. (was session-gate.py)"""
    if tool_name in _WHITELIST:
        return

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    bootstrap_path = os.path.join(project_dir, _BOOTSTRAP_FLAG)
    if os.path.exists(bootstrap_path):
        return

    if state["session"].get("validated"):
        return

    deny(
        f"Session not initialized. Tool '{tool_name}' is blocked.\n"
        "You MUST call init_session from orchestrator-mcp before any other action.\n"
        "This validates that all infrastructure services are healthy."
    )


def gate_pending_actions(state: dict) -> list[str]:
    """Check for pending actions (non-blocking). (was pending-actions.py)"""
    pa = state.get("pending_actions", {})
    if time.time() - pa.get("last_reminder", 0) < _PENDING_COOLDOWN_SECONDS:
        return []

    reminders = []
    pstate = load_persistent_state()

    # Check pending memory queue
    queue = pstate.get("pending_memory_queue", [])
    if queue:
        reminders.append(f"{len(queue)} workflow outcome(s) need persisting to mem0")

    # Check legacy pending memory file
    from lib.state import artifacts_dir
    legacy_path = os.path.join(artifacts_dir(), ".pending-memory-save.json")
    try:
        with open(legacy_path) as f:
            legacy = json.load(f)
        if isinstance(legacy, list) and legacy:
            reminders.append(f"{len(legacy)} workflow outcome(s) in .pending-memory-save.json need persisting to mem0")
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass

    # Check doc staleness
    stale = pstate.get("doc_staleness", {}).get("stale_docs", {})
    if stale:
        docs = ", ".join(stale.keys())
        reminders.append(f"{len(stale)} doc(s) may be stale: {docs}")

    if reminders:
        state["pending_actions"]["last_reminder"] = time.time()

    return reminders


def gate_throttle(tool_input: dict, state: dict) -> None:
    """Enforce Agent budget limits. (was throttle.py)"""
    tier = _get_model_tier_strict(tool_input)
    if tier is None:
        return

    throttle = state.get("throttle", {})
    profile_name = throttle.get("profile", "medium")
    profile = PROFILES.get(profile_name, PROFILES["medium"])

    current = throttle.get(f"{tier}_calls", 0)
    limit = profile.get(f"max_{tier}_calls", -1)

    if limit == -1 or current < limit:
        return

    throttle["blocked_calls"] = throttle.get("blocked_calls", 0) + 1
    save_session_state(state)

    alt = ALTERNATIVES.get(tier, "a cheaper model")
    deny(
        f"Budget limit reached: {current}/{limit} {tier} Agent calls used "
        f"(profile: {profile_name}).\n"
        f"Try: {alt}\n"
        f"Override: set SESSION_BUDGET=high or SESSION_BUDGET=unlimited in .envrc"
    )


def gate_model(tool_input: dict) -> None:
    """Enforce model selection rules. (was model-gate.py)"""
    model = tool_input.get("model", "")
    if not model:
        return

    model_lower = model.lower()
    subagent_type = tool_input.get("subagent_type", "")
    description = tool_input.get("description", "")
    prompt = tool_input.get("prompt", "")
    combined_text = f"{description} {prompt}"

    # Cheap subagents should never use expensive models
    if subagent_type in _CHEAP_SUBAGENTS:
        if "opus" in model_lower:
            deny(f"subagent_type='{subagent_type}' doesn't need opus. "
                 "Remove the model param to use the default, or use model='haiku'.")
        if "sonnet" in model_lower:
            deny(f"subagent_type='{subagent_type}' doesn't need sonnet. "
                 "Remove the model param to use the default, or use model='haiku'.")

    # Opus requires justifying keywords
    if "opus" in model_lower:
        if not _text_contains_any(combined_text, _OPUS_KEYWORDS):
            deny(
                "model='opus' is reserved for: ambiguous debugging, architecture sign-off, "
                "final decisions, complex root cause analysis.\n"
                f"Task: \"{description}\"\n"
                "Try: model='sonnet' for implementation, or delegate to Gemini."
            )

    # Sonnet should have implementation-like keywords for short descriptions
    if "sonnet" in model_lower:
        if len(combined_text) < 50 and not _text_contains_any(combined_text, _SONNET_KEYWORDS):
            deny(
                "model='sonnet' is for: multi-file implementation, tests, refactoring.\n"
                f"Task looks simple: \"{description}\"\n"
                "Try: model='haiku' for simple tasks, or delegate to Gemini."
            )


def gate_task(state: dict) -> None:
    """One-time nudge for task tracking. (was task-gate.py)"""
    if state.get("task_gate_dismissed"):
        return

    # Check if tasks exist
    from lib.state import load_task_state
    tasks = load_task_state()
    if tasks.get("tasks"):
        return

    total = state.get("throttle", {}).get("total_agent_calls", 0)
    if total < _AGENT_THRESHOLD:
        return

    state["task_gate_dismissed"] = True
    save_session_state(state)

    deny(
        f"You've spawned {total} Agent subprocesses without structured tracking.\n"
        "For complex multi-step work, consider:\n"
        "  - TaskCreate to track progress across steps\n"
        "  - run_workflow for managed multi-agent execution\n"
        "This gate fires once per session. Retry your Agent call to proceed."
    )


def gate_gemini_delegation(tool_input: dict, state: dict) -> None:
    """Enforce Read delegation to Gemini. (was gemini-delegation.py)"""
    file_path = tool_input.get("file_path", "")
    if not file_path:
        return

    # Skip config/settings files
    if any(p in file_path for p in _READ_SKIP_PATTERNS):
        return

    reads = state.get("reads", {})
    files_read = reads.get("files_read", [])
    last_block = reads.get("last_delegation_block", 0)

    # Track unique reads
    if file_path not in files_read:
        files_read.append(file_path)
        reads["files_read"] = files_read
        save_session_state(state)

    if len(files_read) <= _READ_THRESHOLD:
        return

    if time.time() - last_block < _READ_COOLDOWN_SECONDS:
        return

    reads["last_delegation_block"] = time.time()
    save_session_state(state)

    deny(
        f"You've read {len(files_read)} unique source files this session.\n"
        "Per CLAUDE.md: 3+ files -> use mcp__gemini__analyze_files for bulk comprehension.\n"
        "This is faster and saves Claude context window.\n"
        f"Files read: {', '.join(os.path.basename(f) for f in files_read[-5:])}\n"
        "Retry this Read if you need a specific file, or switch to analyze_files."
    )


# ── Helpers ────────────────────────────────────────────────────────────────

def _get_model_tier_strict(tool_input: dict) -> str | None:
    """Extract model tier from Agent input. Returns None if not expensive."""
    model = tool_input.get("model", "")
    if not model:
        return None
    m = model.lower()
    if "opus" in m:
        return "opus"
    if "sonnet" in m:
        return "sonnet"
    return None


def _text_contains_any(text: str, keywords: set[str]) -> bool:
    text_lower = text.lower()
    return any(kw in text_lower for kw in keywords)


# ── Main dispatch ──────────────────────────────────────────────────────────

def main():
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    # Load consolidated state (with legacy migration)
    state = load_session_state()
    if not state.get("_migrated"):
        legacy = migrate_legacy_states()
        if legacy:
            # Merge legacy into new state (preserve any new-state fields already set)
            for section in ("throttle", "reads", "pending_actions", "session"):
                if section in legacy:
                    for k, v in legacy[section].items():
                        if state.get(section, {}).get(k) in (None, 0, False, [], ""):
                            state.setdefault(section, {})[k] = v
            if legacy.get("task_gate_dismissed"):
                state["task_gate_dismissed"] = True
            state["_migrated"] = True
            save_session_state(state)

    # Write session_id to shared file
    session_id = input_data.get("session_id", "")
    if session_id and state["session"].get("validated"):
        write_session_id(session_id)

    # Gate 1: Session validation (blocks if not initialized)
    gate_session(tool_name, state)

    # Gate 2: Pending actions (non-blocking reminders)
    reminders = gate_pending_actions(state)
    if reminders:
        save_session_state(state)
        msg = "PENDING ACTIONS:\n" + "\n".join(f"  - {r}" for r in reminders)
        msg += "\n\nProcess these when you have a natural pause in your current work."
        print(msg, file=sys.stderr)

    # Gates 3-5: Agent-specific gates
    if tool_name == "Agent":
        gate_throttle(tool_input, state)
        gate_model(tool_input)
        gate_task(state)

    # Gate 6: Read delegation
    if tool_name == "Read":
        gate_gemini_delegation(tool_input, state)

    allow()


if __name__ == "__main__":
    main()
