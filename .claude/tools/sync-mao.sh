#!/usr/bin/env bash
# sync-mao.sh — Sync MAO framework from RFPGatherer to claude_workspace template
#
# Usage: .claude/tools/sync-mao.sh [commit message]
#
# Syncs the generic (Part 1) framework components:
#   - Hooks (2 consolidated + shared lib)
#   - All docs (generic framework guides + INDEX.md)
#   - Tools (reset-mcps.sh, sync-mao.sh)
#   - Template settings.local.json (generic permissions, no project-specific Bash allowlists)
#
# Does NOT sync project-specific (Part 2) files:
#   - .mcp.json (project-specific paths + API keys)
#   - Project skills (.claude/skills/rfp_gatherer-*)
#   - Project guide (rfp_gatherer-guide.md)
#   - Artifacts directory contents
#
# Run this after validating MAO framework changes in RFPGatherer.

set -euo pipefail

RFPG="/home/tohigu/projects/spandrel/RFPGatherer"
CW="/home/tohigu/projects/spandrel/claude_workspace"
MSG="${1:-chore: sync MAO framework from RFPGatherer}"

# Verify both repos exist
if [[ ! -d "$RFPG/.claude" ]]; then echo "ERROR: RFPGatherer .claude/ not found"; exit 1; fi
if [[ ! -d "$CW/.claude" ]]; then echo "ERROR: claude_workspace .claude/ not found"; exit 1; fi

echo "=== Syncing MAO framework: RFPGatherer → claude_workspace ==="
echo ""

# 1. Sync hooks — replace entirely (delete old, copy new + lib)
echo "  [hooks] Replacing old hooks with consolidated versions..."
rm -f "$CW/.claude/hooks/"*.py
rm -rf "$CW/.claude/hooks/lib/" "$CW/.claude/hooks/__pycache__/"
cp "$RFPG/.claude/hooks/pre-tool-gate.py" "$CW/.claude/hooks/"
cp "$RFPG/.claude/hooks/post-tool-trace.py" "$CW/.claude/hooks/"
cp -r "$RFPG/.claude/hooks/lib/" "$CW/.claude/hooks/lib/"
echo "    pre-tool-gate.py"
echo "    post-tool-trace.py"
echo "    lib/ (state.py, langfuse.py, decisions.py)"

# 2. Sync docs — all generic docs + INDEX, skip project-specific guide
echo ""
echo "  [docs] Syncing generic framework docs..."
GENERIC_DOCS=(
    "INDEX.md"
    "usage-guide.md"
    "architecture-overview.md"
    "mcp-servers.md"
    "observability.md"
    "rate-limiting.md"
    "workflows.md"
    "agent-roles.md"
    "skills-guide.md"
    "artifacts.md"
    "project-setup-guide.md"
)
for doc in "${GENERIC_DOCS[@]}"; do
    if [[ -f "$RFPG/.claude/docs/$doc" ]]; then
        cp "$RFPG/.claude/docs/$doc" "$CW/.claude/docs/$doc"
        echo "    $doc"
    else
        echo "    SKIP $doc (not found)"
    fi
done

# 3. Sync tools
echo ""
echo "  [tools] Syncing CLI tools..."
cp "$RFPG/.claude/tools/reset-mcps.sh" "$CW/.claude/tools/reset-mcps.sh"
cp "$RFPG/.claude/tools/sync-mao.sh" "$CW/.claude/tools/sync-mao.sh"
chmod +x "$CW/.claude/tools/"*.sh
echo "    reset-mcps.sh"
echo "    sync-mao.sh"

# 4. Sync settings.local.json — generate template version (generic permissions only)
echo ""
echo "  [settings] Generating template settings.local.json..."
cat > "$CW/.claude/settings.local.json" << 'SETTINGS_EOF'
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": ".*",
        "hooks": [
          {
            "type": "command",
            "command": "python3 .claude/hooks/pre-tool-gate.py",
            "timeout": 2000
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": ".*",
        "hooks": [
          {
            "type": "command",
            "command": "python3 .claude/hooks/post-tool-trace.py",
            "timeout": 5000
          }
        ]
      }
    ]
  },
  "permissions": {
    "allow": [
      "mcp__mem0__search_memories",
      "mcp__mem0__add_memory",
      "mcp__mem0__list_memories",
      "mcp__mem0__delete_memory",
      "mcp__mem0__search_graph",
      "mcp__mem0__get_entity",
      "mcp__gemini__analyze_files",
      "mcp__gemini__review_diff",
      "mcp__gemini__explain_architecture",
      "mcp__gemini__refresh_index",
      "mcp__gemini__ask_gemini",
      "mcp__orchestrator__validate_system",
      "mcp__orchestrator__init_session",
      "mcp__orchestrator__run_workflow",
      "mcp__orchestrator__workflow_status",
      "mcp__orchestrator__list_workflows",
      "mcp__orchestrator__cancel_workflow",
      "mcp__orchestrator__get_quota_state",
      "mcp__orchestrator__get_quota_report",
      "mcp__orchestrator__optimize_prompts",
      "mcp__langfuse__get_cost_report",
      "mcp__langfuse__get_agent_performance",
      "mcp__langfuse__get_traces",
      "mcp__langfuse__get_session_summary"
    ]
  },
  "enableAllProjectMcpServers": true,
  "enabledMcpjsonServers": [
    "mem0",
    "gemini",
    "orchestrator",
    "langfuse",
    "sequential-thinking"
  ]
}
SETTINGS_EOF
echo "    settings.local.json (template — no project-specific Bash allowlists)"

# 5. Show diff summary
echo ""
echo "=== Changes in claude_workspace ==="
(cd "$CW" && git status --short)

# 6. Commit and push if there are changes
echo ""
echo "=== Committing claude_workspace ==="
(cd "$CW" && \
    git add .claude/ && \
    if git diff --cached --quiet; then
        echo "  No changes to commit"
    else
        git diff --cached --stat
        echo ""
        read -p "  Commit and push with message '$MSG'? [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            git commit -m "$MSG"
            git push
            echo "  Committed and pushed"
        else
            git reset HEAD -- .claude/ >/dev/null
            echo "  Aborted — changes unstaged"
        fi
    fi
)

echo ""
echo "=== Done ==="
