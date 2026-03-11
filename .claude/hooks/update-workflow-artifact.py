#!/usr/bin/env python3
"""PostToolUse hook — generates workflow artifacts from orchestrator MCP responses.

Triggers on mcp__orchestrator__run_workflow and mcp__orchestrator__workflow_status.
Extracts structured data from responses and writes artifacts to .claude/artifacts/.

Complements the in-workflow artifact generation in orchestrator-mcp/artifacts.py
by also handling cases where artifacts need updating from the Claude Code side
(e.g., when workflow_status is polled after a Claude subagent completes work).
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


def archive_if_exists(filename: str) -> None:
    """Move existing artifact to archive/ with timestamp suffix."""
    source = ARTIFACTS_DIR / filename
    if not source.exists():
        return

    archive_dir = ARTIFACTS_DIR / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)

    stem = source.stem
    suffix = source.suffix
    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    dest = archive_dir / f"{stem}_{ts}{suffix}"
    shutil.move(str(source), str(dest))


def write_artifact(filename: str, content: str, *, archive: bool = True) -> None:
    """Write artifact file, archiving previous version if it exists."""
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    if archive:
        archive_if_exists(filename)
    (ARTIFACTS_DIR / filename).write_text(content, encoding="utf-8")


def render_status_from_response(data: dict) -> str | None:
    """Render a workflow_status.md from run_workflow or workflow_status response."""
    # Parse the tool response — it's JSON-encoded
    response = data.get("tool_response", "")
    if isinstance(response, str):
        try:
            response = json.loads(response)
        except (json.JSONDecodeError, TypeError):
            return None

    if not isinstance(response, dict):
        return None

    workflow_id = response.get("workflow_id", "?")
    workflow_type = response.get("workflow_type", "?")
    status = response.get("status", "?")
    description = response.get("description", "")
    completed_steps = response.get("completed_steps", [])
    total_cost = response.get("total_cost", 0.0)
    error = response.get("error")
    next_action = response.get("next_action", {})

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    status_icons = {
        "planning": "[~]",
        "executing": "[~]",
        "reviewing": "[~]",
        "paused": "[!]",
        "completed": "[x]",
        "cancelled": "[-]",
        "failed": "[!]",
    }
    icon = status_icons.get(status, "[?]")

    lines = [
        "# Workflow Status",
        "",
        f"> **ID:** `{workflow_id}`",
        f"> **Type:** {workflow_type}",
        f"> **Status:** {icon} {status.upper()}",
        f"> **Updated:** {now}",
        f"> **Cost:** ${total_cost:.2f}",
        "",
        f"**Goal:** {description}",
        "",
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
            lines.append(f"- [{success}] **{step_name}** — {role} ({model})")
        lines.append("")

    if next_action:
        action_type = next_action.get("type", "")
        if action_type == "workflow_complete":
            lines += [
                "## Result",
                "",
                next_action.get("summary", ""),
                "",
            ]
        elif action_type == "review_complete":
            result = next_action.get("result", {})
            if isinstance(result, dict):
                lines += [
                    "## Review Result",
                    "",
                    f"**Verdict:** {'APPROVED' if result.get('approved') else 'CHANGES REQUESTED'}",
                    "",
                    result.get("summary", ""),
                    "",
                ]

    lines += ["---", ""]

    return "\n".join(lines)


def auto_open(filepath: Path) -> None:
    """Open artifact in VSCodium if this is the first time it's created."""
    editor = shutil.which("codium") or shutil.which("code")
    if editor:
        subprocess.Popen(
            [editor, "--reuse-window", str(filepath)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def main():
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return
        data = json.loads(raw)
    except (json.JSONDecodeError, IOError):
        return

    tool_name = data.get("tool_name", "")

    # Only process orchestrator workflow tools
    if tool_name not in (
        "mcp__orchestrator__run_workflow",
        "mcp__orchestrator__workflow_status",
    ):
        return

    content = render_status_from_response(data)
    if content:
        is_new = not (ARTIFACTS_DIR / "workflow_status.md").exists()
        write_artifact("workflow_status.md", content, archive=False)
        if is_new:
            auto_open(ARTIFACTS_DIR / "workflow_status.md")


if __name__ == "__main__":
    main()
