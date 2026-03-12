#!/usr/bin/env python3
"""PostToolUse hook: Phase 7 — Documentation sync tracker.

Tracks source file modifications and flags when related documentation
may need updating. Writes a staleness report to an artifact file.

Triggers on: Edit, Write tool calls
Tracks: source files in backend/, frontend/src/, orchestrator-mcp/
Checks: corresponding docs in docs/, .claude/docs/
"""

import json
import os
import sys
import time

# Source directories to track
_SOURCE_DIRS = {"backend/", "frontend/src/", "orchestrator-mcp/"}

# Documentation directories to check for staleness
_DOC_DIRS = {"docs/", ".claude/docs/"}

# Mapping from source patterns to related doc files
_SOURCE_TO_DOCS = {
    "backend/src/scoring": ["docs/PSD.md", "docs/architecture_flow.md"],
    "backend/src/scraper": ["docs/architecture_flow.md"],
    "backend/src/match": ["docs/PSD.md"],
    "orchestrator-mcp/": [".claude/docs/workflows.md", ".claude/docs/mcp-servers.md"],
    "frontend/src/": [".claude/docs/architecture-overview.md"],
    ".claude/hooks/": [".claude/docs/observability.md"],
}


def _artifacts_dir() -> str:
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    return os.path.join(project_dir, ".claude", "artifacts")


def _is_source_file(file_path: str) -> bool:
    """Check if the file is in a tracked source directory."""
    return any(d in file_path for d in _SOURCE_DIRS) or ".claude/hooks/" in file_path


def _find_related_docs(file_path: str) -> list[str]:
    """Find documentation files related to the modified source file."""
    related = []
    for pattern, docs in _SOURCE_TO_DOCS.items():
        if pattern in file_path:
            related.extend(docs)
    return list(set(related))


def main():
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    # Only track Edit and Write calls
    if tool_name not in ("Edit", "Write"):
        sys.exit(0)

    file_path = tool_input.get("file_path", "")
    if not file_path or not _is_source_file(file_path):
        sys.exit(0)

    # Find related docs
    related_docs = _find_related_docs(file_path)
    if not related_docs:
        sys.exit(0)

    # Load existing tracker state
    artifacts_dir = _artifacts_dir()
    tracker_path = os.path.join(artifacts_dir, ".doc-staleness.json")

    tracker = {}
    try:
        with open(tracker_path) as f:
            tracker = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    # Update tracker
    if "modified_sources" not in tracker:
        tracker["modified_sources"] = {}
    if "stale_docs" not in tracker:
        tracker["stale_docs"] = {}

    # Record the modification
    basename = os.path.basename(file_path)
    tracker["modified_sources"][file_path] = {
        "modified_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "related_docs": related_docs,
    }

    # Mark docs as potentially stale
    for doc in related_docs:
        if doc not in tracker["stale_docs"]:
            tracker["stale_docs"][doc] = {
                "flagged_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "triggered_by": [],
            }
        triggers = tracker["stale_docs"][doc]["triggered_by"]
        if basename not in triggers:
            triggers.append(basename)

    tracker["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")

    # Save tracker
    os.makedirs(artifacts_dir, exist_ok=True)
    with open(tracker_path, "w") as f:
        json.dump(tracker, f, indent=2)

    # Write human-readable staleness report
    report_path = os.path.join(artifacts_dir, "doc_staleness.md")
    stale = tracker.get("stale_docs", {})
    if stale:
        lines = [
            "# Documentation Staleness Report",
            f"\n> Last updated: {tracker['last_updated']}",
            "",
        ]
        for doc, info in stale.items():
            triggers = ", ".join(info["triggered_by"])
            lines.append(f"- **{doc}** — triggered by: {triggers}")

        lines.extend([
            "",
            "---",
            f"**{len(stale)}** docs may need review",
            "",
            "<!-- Clear this report after updating docs -->",
        ])

        with open(report_path, "w") as f:
            f.write("\n".join(lines))

    sys.exit(0)


if __name__ == "__main__":
    main()
