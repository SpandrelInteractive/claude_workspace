#!/usr/bin/env python3
"""PostToolUse hook: Phase 6 — Memory protocol enforcement.

Auto-saves workflow outcomes when workflows complete.
Writes a pending memory file that signals the main Claude process
to persist the outcome to mem0.

Triggers on: mcp__orchestrator__workflow_status, mcp__orchestrator__run_workflow
Condition: response contains status "completed" or "failed"
"""

import json
import os
import sys
import time


def _artifacts_dir() -> str:
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    return os.path.join(project_dir, ".claude", "artifacts")


def main():
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")

    # Only process orchestrator workflow tools
    if tool_name not in (
        "mcp__orchestrator__workflow_status",
        "mcp__orchestrator__run_workflow",
    ):
        sys.exit(0)

    # Parse the tool response
    try:
        response_str = input_data.get("tool_response", "")
        if isinstance(response_str, str):
            # orchestrator tools return JSON strings, sometimes wrapped
            response = json.loads(response_str)
            if isinstance(response, dict) and "result" in response:
                response = json.loads(response["result"])
        else:
            response = response_str
    except (json.JSONDecodeError, TypeError):
        sys.exit(0)

    status = response.get("status", "")
    if status not in ("completed", "failed"):
        sys.exit(0)

    # Extract outcome details
    workflow_id = response.get("workflow_id", "unknown")
    workflow_type = response.get("workflow_type", response.get("type", "unknown"))
    description = response.get("description", "")
    completed_steps = response.get("completed_steps", [])
    total_cost = response.get("total_cost", 0.0)
    error = response.get("error", "")

    # Build memory content
    outcome = {
        "workflow_id": workflow_id,
        "type": workflow_type,
        "status": status,
        "description": description,
        "steps_completed": len(completed_steps),
        "total_cost": total_cost,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    if error:
        outcome["error"] = error
    if completed_steps:
        outcome["steps"] = [
            {"step": s.get("step", "?"), "model": s.get("model", "?")}
            for s in completed_steps[-5:]  # Last 5 steps
        ]

    # Write pending memory file
    artifacts_dir = _artifacts_dir()
    os.makedirs(artifacts_dir, exist_ok=True)
    pending_path = os.path.join(artifacts_dir, ".pending-memory-save.json")

    # Append to existing pending saves (queue)
    pending = []
    try:
        with open(pending_path) as f:
            pending = json.load(f)
        if not isinstance(pending, list):
            pending = [pending]
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    pending.append(outcome)

    with open(pending_path, "w") as f:
        json.dump(pending, f, indent=2)

    sys.exit(0)


if __name__ == "__main__":
    main()
