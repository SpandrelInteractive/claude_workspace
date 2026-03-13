"""Shared Langfuse tracing for hooks."""

from __future__ import annotations

import base64
import json
import os
import urllib.request
import uuid
from datetime import datetime, timezone

LANGFUSE_HOST = os.environ.get("LANGFUSE_HOST", "http://localhost:3000")
LANGFUSE_PUBLIC_KEY = os.environ.get(
    "LANGFUSE_PUBLIC_KEY", "pk-lf-ef1bb4f1-8e40-4027-9eec-6121c6dd750e"
)
LANGFUSE_SECRET_KEY = os.environ.get(
    "LANGFUSE_SECRET_KEY", "sk-lf-81fca270-4ab3-4437-8b39-03fddf6b95a7"
)

# Tools to skip tracing (too noisy / internal)
SKIP_TOOLS = {"ToolSearch"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _auth_header() -> str:
    creds = f"{LANGFUSE_PUBLIC_KEY}:{LANGFUSE_SECRET_KEY}".encode()
    return "Basic " + base64.b64encode(creds).decode()


def classify_tool(tool_name: str, tool_input: dict) -> dict:
    """Extract agent role, model, and action category from tool call."""
    info = {"agent": "orchestrator", "action": tool_name, "model": ""}

    if tool_name == "Agent":
        info["agent"] = tool_input.get("subagent_type", "general-purpose")
        info["model"] = tool_input.get("model", "inherited")
        info["action"] = tool_input.get("description", "agent-call")
    elif tool_name.startswith("mcp__"):
        parts = tool_name.split("__")
        if len(parts) >= 3:
            info["agent"] = parts[1]
            info["action"] = parts[2]
    elif tool_name in ("Read", "Edit", "Write", "Glob", "Grep"):
        info["action"] = tool_name.lower()
        file_path = tool_input.get("file_path", tool_input.get("path", ""))
        if file_path:
            info["file"] = os.path.basename(file_path)
    elif tool_name == "Bash":
        desc = tool_input.get("description", "")
        if desc:
            info["action"] = desc[:60]
        else:
            cmd = tool_input.get("command", "")
            info["action"] = cmd.split()[0] if cmd.split() else "bash"

    return info


def send_trace(tool_name: str, tool_input: dict, session_id: str = "") -> None:
    """Send trace to Langfuse ingestion API (fire-and-forget)."""
    if not all([LANGFUSE_HOST, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY]):
        return

    info = classify_tool(tool_name, tool_input)
    now = _now_iso()
    trace_id = str(uuid.uuid4())

    metadata = {
        "tool_name": tool_name,
        "agent": info["agent"],
        "action": info["action"],
        "source": "posttooluse-hook",
    }
    if info.get("model"):
        metadata["model"] = info["model"]
    if info.get("file"):
        metadata["file"] = info["file"]

    trace_body = {
        "id": trace_id,
        "name": f"{info['agent']}:{info['action']}",
        "metadata": metadata,
        "timestamp": now,
    }
    if session_id:
        trace_body["sessionId"] = session_id

    batch = [{
        "id": str(uuid.uuid4()),
        "type": "trace-create",
        "timestamp": now,
        "body": trace_body,
    }]

    # Add generation span for Agent calls with model info
    if info.get("model") and info["model"] != "inherited":
        batch.append({
            "id": str(uuid.uuid4()),
            "type": "generation-create",
            "timestamp": now,
            "body": {
                "id": str(uuid.uuid4()),
                "traceId": trace_id,
                "name": info["action"],
                "model": info["model"],
                "metadata": {"agent": info["agent"]},
                "startTime": now,
                "endTime": now,
            },
        })

    payload = json.dumps({"batch": batch}).encode()
    req = urllib.request.Request(
        f"{LANGFUSE_HOST}/api/public/ingestion",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": _auth_header(),
        },
        method="POST",
    )

    try:
        urllib.request.urlopen(req, timeout=2)
    except Exception:
        pass
