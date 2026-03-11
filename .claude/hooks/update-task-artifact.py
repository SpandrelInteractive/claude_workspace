#!/usr/bin/env python3
"""PostToolUse hook — maintains a live task list artifact in .claude/artifacts/tasks.md

Triggers on Task* tool calls. Incrementally updates a JSON state file and
regenerates a human-readable markdown artifact that can be viewed in a split pane.

Multi-agent aware: captures session_id to attribute tasks to agents.
"""

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR", Path(__file__).resolve().parents[2]))
ARTIFACTS_DIR = PROJECT_ROOT / ".claude" / "artifacts"
STATE_FILE = ARTIFACTS_DIR / ".tasks-state.json"
OUTPUT_FILE = ARTIFACTS_DIR / "tasks.md"

STATUS_ICONS = {
    "pending": "[ ]",
    "in_progress": "[~]",
    "completed": "[x]",
    "blocked": "[!]",
    "cancelled": "[-]",
}


def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, IOError):
            pass
    return {"tasks": {}, "updated_at": None}


def save_state(state):
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = datetime.now().isoformat()
    STATE_FILE.write_text(json.dumps(state, indent=2))


def update_from_tool_call(state, data):
    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})
    tool_response = data.get("tool_response", {})
    session_id = data.get("session_id", "unknown")[:8]

    if tool_name == "TaskCreate":
        task_id = None
        description = tool_input.get("description", "")
        # Extract task ID from response
        if isinstance(tool_response, dict):
            task_id = tool_response.get("id") or tool_response.get("task_id")
        if isinstance(tool_response, str):
            # Try to parse task ID from text response
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
        task_id = tool_input.get("id") or tool_input.get("task_id", "")
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
        # Full refresh from TaskList response
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

    return state


def render_markdown(state):
    tasks = state.get("tasks", {})
    updated = state.get("updated_at", "never")

    # Group by status
    groups = {"in_progress": [], "pending": [], "blocked": [], "completed": [], "cancelled": []}
    for tid, task in tasks.items():
        status = task.get("status", "pending")
        groups.setdefault(status, []).append((tid, task))

    lines = [
        "# Task List",
        "",
        f"> Last updated: {updated}",
        "",
    ]

    # Active work first
    for status in ["in_progress", "blocked", "pending", "completed", "cancelled"]:
        items = groups.get(status, [])
        if not items:
            continue

        label = status.replace("_", " ").title()
        lines.append(f"## {label}")
        lines.append("")

        for tid, task in items:
            icon = STATUS_ICONS.get(status, "[ ]")
            desc = task.get("description", "")
            agent = task.get("agent", "?")
            lines.append(f"- {icon} **{tid}** — {desc}  `agent:{agent}`")

            deps = task.get("blocked_by", [])
            if deps:
                lines.append(f"  - Blocked by: {', '.join(deps)}")
            blocks = task.get("blocks", [])
            if blocks:
                lines.append(f"  - Blocks: {', '.join(blocks)}")

        lines.append("")

    # Summary
    total = len(tasks)
    done = len(groups.get("completed", []))
    active = len(groups.get("in_progress", []))
    lines.append("---")
    lines.append(f"**{done}/{total}** completed | **{active}** in progress")
    lines.append("")

    return "\n".join(lines)


def main():
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return
        data = json.loads(raw)
    except (json.JSONDecodeError, IOError):
        return

    state = load_state()
    state = update_from_tool_call(state, data)
    save_state(state)

    md = render_markdown(state)
    is_new = not OUTPUT_FILE.exists()
    OUTPUT_FILE.write_text(md)

    # Auto-open in VSCodium on first creation
    if is_new:
        editor = shutil.which("codium") or shutil.which("code")
        if editor:
            subprocess.Popen(
                [editor, "--reuse-window", str(OUTPUT_FILE)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )


if __name__ == "__main__":
    main()
