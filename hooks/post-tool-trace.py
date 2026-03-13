#!/usr/bin/env python3
"""Consolidated PostToolUse hook.

Replaces 6 individual hooks:
  1. langfuse-trace.py — trace all tool calls to Langfuse
  2. throttle-tracker.py — increment Agent call counters
  3. update-task-artifact.py — maintain task list artifact
  4. update-workflow-artifact.py — generate workflow status artifact
  5. memory-save.py — queue workflow outcomes for mem0
  6. doc-tracker.py — track doc staleness

Runs on matcher: .* (all tools)
Timeout: 5000ms
"""

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# Add hooks dir to path for lib imports
sys.path.insert(0, os.path.dirname(__file__))

from lib.state import (
    load_session_state,
    save_session_state,
    load_persistent_state,
    save_persistent_state,
    load_task_state,
    save_task_state,
    artifacts_dir,
)
from lib.langfuse import send_trace, SKIP_TOOLS


# ── Constants ──────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(os.environ["CLAUDE_PROJECT_DIR"])
ARTIFACTS_DIR = PROJECT_ROOT / ".claude" / "artifacts"

# Locate framework docs relative to this hook file's directory.
# Works whether hooks live at .claude/hooks/ or .claude/framework/hooks/
_HOOKS_DIR = Path(__file__).resolve().parent
_FRAMEWORK_ROOT = _HOOKS_DIR.parent  # .claude/ or .claude/framework/
_DOCS_DIR = str(_FRAMEWORK_ROOT / "docs")

# Source directories for doc staleness tracking
_SOURCE_DIRS = {"backend/", "frontend/src/", "orchestrator-mcp/"}
_SOURCE_TO_DOCS = {
    "backend/src/scoring": ["docs/PSD.md", "docs/architecture_flow.md"],
    "backend/src/scraper": ["docs/architecture_flow.md"],
    "backend/src/match": ["docs/PSD.md"],
    "orchestrator-mcp/": [f"{_DOCS_DIR}/workflows.md", f"{_DOCS_DIR}/mcp-servers.md"],
    "frontend/src/": [f"{_DOCS_DIR}/architecture-overview.md"],
    str(_HOOKS_DIR) + "/": [f"{_DOCS_DIR}/observability.md"],
}

STATUS_ICONS_TASK = {
    "pending": "[ ]",
    "in_progress": "[~]",
    "completed": "[x]",
    "blocked": "[!]",
    "cancelled": "[-]",
}

STATUS_ICONS_WORKFLOW = {
    "planning": "[~]", "executing": "[~]", "reviewing": "[~]",
    "paused": "[!]", "completed": "[x]", "cancelled": "[-]", "failed": "[!]",
}


# ── Handler functions ──────────────────────────────────────────────────────

def handle_langfuse_trace(tool_name: str, tool_input: dict, session_id: str) -> None:
    """Trace tool call to Langfuse. (was langfuse-trace.py)"""
    if tool_name in SKIP_TOOLS:
        return
    send_trace(tool_name, tool_input, session_id=session_id)


def handle_throttle_tracker(tool_input: dict, state: dict) -> None:
    """Increment Agent call counters. (was throttle-tracker.py)"""
    model = tool_input.get("model", "")
    if not model:
        tier = "sonnet"  # Default when no model specified
    else:
        m = model.lower()
        if "opus" in m:
            tier = "opus"
        elif "sonnet" in m:
            tier = "sonnet"
        elif "haiku" in m:
            tier = "haiku"
        else:
            tier = "sonnet"  # Unknown → sonnet to avoid black hole

    throttle = state.setdefault("throttle", {})
    count_key = f"{tier}_calls"
    throttle[count_key] = throttle.get(count_key, 0) + 1
    throttle["total_agent_calls"] = throttle.get("total_agent_calls", 0) + 1


def handle_task_artifact(data: dict) -> None:
    """Maintain task list artifact. (was update-task-artifact.py)"""
    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})
    tool_response = data.get("tool_response", {})
    session_id = data.get("session_id", "unknown")[:8]

    state = load_task_state()

    if tool_name == "TaskCreate":
        task_id = None
        description = tool_input.get("description", "")
        if isinstance(tool_response, dict):
            task_id = tool_response.get("id") or tool_response.get("task_id")
        if isinstance(tool_response, str):
            for line in tool_response.split("\n"):
                if "id" in line.lower():
                    parts = line.split(":")
                    if len(parts) > 1:
                        task_id = parts[-1].strip().strip('"')
                        break
        if not task_id:
            task_id = f"task_{len(state['tasks']) + 1}"
        state["tasks"][task_id] = {
            "description": description,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "agent": session_id,
            "blocked_by": [],
            "blocks": [],
        }

    elif tool_name == "TaskUpdate":
        task_id = tool_input.get("id") or tool_input.get("task_id") or tool_input.get("taskId", "")
        if task_id and task_id in state["tasks"]:
            task = state["tasks"][task_id]
            if "status" in tool_input:
                task["status"] = tool_input["status"]
            if "description" in tool_input:
                task["description"] = tool_input["description"]
            if "addBlockedBy" in tool_input:
                task["blocked_by"].extend(
                    b for b in tool_input["addBlockedBy"] if b not in task["blocked_by"]
                )
            if "addBlocks" in tool_input:
                task["blocks"].extend(
                    b for b in tool_input["addBlocks"] if b not in task["blocks"]
                )
            task["updated_at"] = datetime.now().isoformat()
            task["agent"] = session_id

    elif tool_name == "TaskList":
        if isinstance(tool_response, list):
            for t in tool_response:
                if isinstance(t, dict) and "id" in t:
                    tid = t["id"]
                    state["tasks"][tid] = {
                        "description": t.get("description", ""),
                        "status": t.get("status", "pending"),
                        "created_at": t.get("created_at", datetime.now().isoformat()),
                        "updated_at": datetime.now().isoformat(),
                        "agent": session_id,
                        "blocked_by": t.get("blocked_by", []),
                        "blocks": t.get("blocks", []),
                    }

    save_task_state(state)

    # Render markdown
    md = _render_tasks_md(state)
    output = ARTIFACTS_DIR / "tasks.md"
    is_new = not output.exists()
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    output.write_text(md)

    if is_new:
        _auto_open(output)


def handle_workflow_artifact(data: dict) -> None:
    """Generate workflow status artifact. (was update-workflow-artifact.py)"""
    response = data.get("tool_response", "")
    if isinstance(response, str):
        try:
            response = json.loads(response)
        except (json.JSONDecodeError, TypeError):
            return

    if not isinstance(response, dict):
        return

    workflow_id = response.get("workflow_id", "?")
    workflow_type = response.get("workflow_type", "?")
    status = response.get("status", "?")
    description = response.get("description", "")
    completed_steps = response.get("completed_steps", [])
    total_cost = response.get("total_cost", 0.0)
    error = response.get("error")
    next_action = response.get("next_action", {})

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    icon = STATUS_ICONS_WORKFLOW.get(status, "[?]")

    lines = [
        "# Workflow Status", "",
        f"> **ID:** `{workflow_id}`",
        f"> **Type:** {workflow_type}",
        f"> **Status:** {icon} {status.upper()}",
        f"> **Updated:** {now}",
        f"> **Cost:** ${total_cost:.2f}", "",
        f"**Goal:** {description}", "",
    ]

    if error:
        lines += [f"**Error:** {error}", ""]

    if completed_steps:
        lines += ["## Completed Steps", ""]
        for s in completed_steps:
            step_name = s.get("step", "?")
            role = s.get("agent_role", "?")
            model = s.get("model_used", "?")
            success = "ok" if s.get("success", True) else "FAILED"
            lines.append(f"- [{success}] **{step_name}** -- {role} ({model})")
        lines.append("")

    if next_action:
        action_type = next_action.get("type", "")
        if action_type == "workflow_complete":
            lines += ["## Result", "", next_action.get("summary", ""), ""]
        elif action_type == "review_complete":
            result = next_action.get("result", {})
            if isinstance(result, dict):
                lines += [
                    "## Review Result", "",
                    f"**Verdict:** {'APPROVED' if result.get('approved') else 'CHANGES REQUESTED'}",
                    "", result.get("summary", ""), "",
                ]

    lines += ["---", ""]

    output = ARTIFACTS_DIR / "workflow_status.md"
    is_new = not output.exists()
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")

    if is_new:
        _auto_open(output)


def handle_memory_save(data: dict) -> None:
    """Queue workflow outcome for mem0 persistence. (was memory-save.py)"""
    try:
        response_str = data.get("tool_response", "")
        if isinstance(response_str, str):
            response = json.loads(response_str)
            if isinstance(response, dict) and "result" in response:
                response = json.loads(response["result"])
        else:
            response = response_str
    except (json.JSONDecodeError, TypeError):
        return

    status = response.get("status", "")
    if status not in ("completed", "failed"):
        return

    outcome = {
        "workflow_id": response.get("workflow_id", "unknown"),
        "type": response.get("workflow_type", response.get("type", "unknown")),
        "status": status,
        "description": response.get("description", ""),
        "steps_completed": len(response.get("completed_steps", [])),
        "total_cost": response.get("total_cost", 0.0),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    error = response.get("error", "")
    if error:
        outcome["error"] = error
    steps = response.get("completed_steps", [])
    if steps:
        outcome["steps"] = [
            {"step": s.get("step", "?"), "model": s.get("model", "?")}
            for s in steps[-5:]
        ]

    # Write to persistent state queue
    pstate = load_persistent_state()
    pstate.setdefault("pending_memory_queue", []).append(outcome)
    save_persistent_state(pstate)

    # Also write legacy file for orchestrator-mcp compatibility
    legacy_path = os.path.join(artifacts_dir(), ".pending-memory-save.json")
    legacy = []
    try:
        with open(legacy_path) as f:
            legacy = json.load(f)
        if not isinstance(legacy, list):
            legacy = [legacy]
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    legacy.append(outcome)
    os.makedirs(os.path.dirname(legacy_path), exist_ok=True)
    with open(legacy_path, "w") as f:
        json.dump(legacy, f, indent=2)


def handle_doc_tracker(tool_input: dict) -> None:
    """Track doc staleness from file modifications. (was doc-tracker.py)"""
    file_path = tool_input.get("file_path", "")
    if not file_path:
        return

    # Check if in tracked source directory
    if not (any(d in file_path for d in _SOURCE_DIRS) or str(_HOOKS_DIR) in file_path):
        return

    # Find related docs
    related_docs = []
    for pattern, docs in _SOURCE_TO_DOCS.items():
        if pattern in file_path:
            related_docs.extend(docs)
    related_docs = list(set(related_docs))
    if not related_docs:
        return

    pstate = load_persistent_state()
    staleness = pstate.setdefault("doc_staleness", {"modified_sources": {}, "stale_docs": {}})

    basename = os.path.basename(file_path)
    staleness["modified_sources"][file_path] = {
        "modified_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "related_docs": related_docs,
    }

    for doc in related_docs:
        if doc not in staleness["stale_docs"]:
            staleness["stale_docs"][doc] = {
                "flagged_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "triggered_by": [],
            }
        triggers = staleness["stale_docs"][doc]["triggered_by"]
        if basename not in triggers:
            triggers.append(basename)

    staleness["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    save_persistent_state(pstate)

    # Write human-readable report
    stale = staleness.get("stale_docs", {})
    if stale:
        lines = [
            "# Documentation Staleness Report",
            f"\n> Last updated: {staleness['last_updated']}", "",
        ]
        for doc, info in stale.items():
            triggers_str = ", ".join(info["triggered_by"])
            lines.append(f"- **{doc}** -- triggered by: {triggers_str}")
        lines.extend(["", "---", f"**{len(stale)}** docs may need review", "",
                       "<!-- Clear this report after updating docs -->"])
        report_path = ARTIFACTS_DIR / "doc_staleness.md"
        ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
        report_path.write_text("\n".join(lines))


# ── Helpers ────────────────────────────────────────────────────────────────

def _render_tasks_md(state: dict) -> str:
    tasks = state.get("tasks", {})
    updated = state.get("updated_at", "never")

    groups = {"in_progress": [], "pending": [], "blocked": [], "completed": [], "cancelled": []}
    for tid, task in tasks.items():
        status = task.get("status", "pending")
        groups.setdefault(status, []).append((tid, task))

    lines = ["# Task List", "", f"> Last updated: {updated}", ""]

    for status in ["in_progress", "blocked", "pending", "completed", "cancelled"]:
        items = groups.get(status, [])
        if not items:
            continue
        label = status.replace("_", " ").title()
        lines.append(f"## {label}")
        lines.append("")
        for tid, task in items:
            icon = STATUS_ICONS_TASK.get(status, "[ ]")
            desc = task.get("description", "")
            agent = task.get("agent", "?")
            lines.append(f"- {icon} **{tid}** -- {desc}  `agent:{agent}`")
            deps = task.get("blocked_by", [])
            if deps:
                lines.append(f"  - Blocked by: {', '.join(deps)}")
            blocks = task.get("blocks", [])
            if blocks:
                lines.append(f"  - Blocks: {', '.join(blocks)}")
        lines.append("")

    total = len(tasks)
    done = len(groups.get("completed", []))
    active = len(groups.get("in_progress", []))
    lines.append("---")
    lines.append(f"**{done}/{total}** completed | **{active}** in progress")
    lines.append("")

    return "\n".join(lines)


def _auto_open(filepath: Path) -> None:
    editor = shutil.which("codium") or shutil.which("code")
    if editor:
        subprocess.Popen(
            [editor, "--reuse-window", str(filepath)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


# ── Main dispatch ──────────────────────────────────────────────────────────

def main():
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return
        data = json.loads(raw)
    except (json.JSONDecodeError, IOError):
        return

    tool_name = data.get("tool_name", "")
    if not tool_name:
        return

    tool_input = data.get("tool_input", {})
    session_id = data.get("session_id", "")

    # 1. Langfuse trace (all tools)
    handle_langfuse_trace(tool_name, tool_input, session_id)

    # 2. Throttle tracker (Agent only)
    if tool_name == "Agent":
        state = load_session_state()
        handle_throttle_tracker(tool_input, state)
        save_session_state(state)

    # 3. Task artifact (Task* tools)
    if tool_name.startswith("Task"):
        handle_task_artifact(data)

    # 4-5. Workflow artifact + memory save (orchestrator workflow tools)
    if tool_name in ("mcp__orchestrator__run_workflow", "mcp__orchestrator__workflow_status"):
        handle_workflow_artifact(data)
        handle_memory_save(data)

    # 6. Doc tracker (Edit/Write)
    if tool_name in ("Edit", "Write"):
        handle_doc_tracker(tool_input)


if __name__ == "__main__":
    main()
