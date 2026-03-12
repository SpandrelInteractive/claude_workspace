#!/usr/bin/env python3
"""PostToolUse hook: Auto-trace ALL tool calls to Langfuse.

Sends every tool invocation to Langfuse via REST API for observability.
Uses stdlib urllib only (no external deps).

Fires on: .* (all tools)
Timeout: 2000ms (fire-and-forget to localhost)
"""

import json
import os
import sys
import urllib.request
import uuid
from datetime import datetime, timezone

# Langfuse connection — same creds as .mcp.json langfuse server
LANGFUSE_HOST = os.environ.get("LANGFUSE_HOST", "http://localhost:3000")
LANGFUSE_PUBLIC_KEY = os.environ.get(
    "LANGFUSE_PUBLIC_KEY", "pk-lf-ef1bb4f1-8e40-4027-9eec-6121c6dd750e"
)
LANGFUSE_SECRET_KEY = os.environ.get(
    "LANGFUSE_SECRET_KEY", "sk-lf-81fca270-4ab3-4437-8b39-03fddf6b95a7"
)

# Tools to skip tracing (too noisy / internal)
_SKIP_TOOLS = {"ToolSearch"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_auth_header() -> str:
    """Build HTTP Basic Auth header from public:secret keys."""
    import base64

    creds = f"{LANGFUSE_PUBLIC_KEY}:{LANGFUSE_SECRET_KEY}".encode()
    return "Basic " + base64.b64encode(creds).decode()


def _classify_tool(tool_name: str, tool_input: dict) -> dict:
    """Extract agent role, model, and action category from tool call."""
    info = {"agent": "orchestrator", "action": tool_name, "model": ""}

    if tool_name == "Agent":
        info["agent"] = tool_input.get("subagent_type", "general-purpose")
        info["model"] = tool_input.get("model", "inherited")
        info["action"] = tool_input.get("description", "agent-call")

    elif tool_name.startswith("mcp__"):
        # e.g. mcp__gemini__analyze_files -> server=gemini, action=analyze_files
        parts = tool_name.split("__")
        if len(parts) >= 3:
            info["agent"] = parts[1]  # server name
            info["action"] = parts[2]  # tool name

    elif tool_name in ("Read", "Edit", "Write", "Glob", "Grep"):
        info["action"] = tool_name.lower()
        file_path = tool_input.get("file_path", tool_input.get("path", ""))
        if file_path:
            info["file"] = os.path.basename(file_path)

    elif tool_name == "Bash":
        cmd = tool_input.get("command", "")
        # Sanitize: take first token only, strip args/credentials
        first_token = cmd.split()[0] if cmd.split() else "bash"
        # Use description if available, otherwise just the command name
        desc = tool_input.get("description", "")
        info["action"] = desc[:60] if desc else first_token

    return info


def _send_trace(tool_name: str, tool_input: dict) -> None:
    """Send trace to Langfuse ingestion API."""
    if not all([LANGFUSE_HOST, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY]):
        return

    info = _classify_tool(tool_name, tool_input)
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

    batch = [
        {
            "id": str(uuid.uuid4()),
            "type": "trace-create",
            "timestamp": now,
            "body": {
                "id": trace_id,
                "name": f"{info['agent']}:{info['action']}",
                "metadata": metadata,
                "timestamp": now,
            },
        }
    ]

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
            "Authorization": _make_auth_header(),
        },
        method="POST",
    )

    try:
        urllib.request.urlopen(req, timeout=2)
    except Exception:
        # Fire and forget — don't block tool execution on tracing failure
        pass


def main():
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")

    if not tool_name or tool_name in _SKIP_TOOLS:
        sys.exit(0)

    tool_input = input_data.get("tool_input", {})
    _send_trace(tool_name, tool_input)
    sys.exit(0)


if __name__ == "__main__":
    main()
