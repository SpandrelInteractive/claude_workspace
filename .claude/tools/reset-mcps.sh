#!/usr/bin/env bash
# Reset MCP servers by killing their processes.
# Claude Code auto-restarts MCP servers on next tool call.
#
# Usage:
#   reset-mcps.sh              # reset all MCP servers
#   reset-mcps.sh mem0 gemini  # reset specific servers only

set -euo pipefail

MCP_CONFIG="/home/tohigu/projects/spandrel/RFPGatherer/.mcp.json"

# Map server names to process signatures for reliable matching
declare -A SERVER_PATTERNS=(
  [mem0]="mem0-mcp"
  [gemini]="gemini-delegate"
  [orchestrator]="orchestrator-mcp"
  [langfuse]="langfuse-mcp"
  [sequential-thinking]="server-sequential-thinking"
)

reset_server() {
  local name="$1"
  local pattern="${SERVER_PATTERNS[$name]:-}"

  if [[ -z "$pattern" ]]; then
    echo "Unknown MCP server: $name"
    echo "Available: ${!SERVER_PATTERNS[*]}"
    return 1
  fi

  local pids
  pids=$(pgrep -f "$pattern" 2>/dev/null || true)

  if [[ -z "$pids" ]]; then
    echo "[$name] No running process found"
    return 0
  fi

  echo "[$name] Killing PIDs: $pids"
  echo "$pids" | xargs kill 2>/dev/null || true

  # Wait briefly for processes to terminate
  sleep 0.5

  # Verify they're gone
  if pgrep -f "$pattern" >/dev/null 2>&1; then
    echo "[$name] Force killing..."
    pgrep -f "$pattern" | xargs kill -9 2>/dev/null || true
  fi

  echo "[$name] Reset complete (will auto-restart on next tool call)"
}

# Determine which servers to reset
if [[ $# -eq 0 ]]; then
  targets=("${!SERVER_PATTERNS[@]}")
else
  targets=("$@")
fi

echo "Resetting MCP servers: ${targets[*]}"
echo "---"

for server in "${targets[@]}"; do
  reset_server "$server"
done

echo "---"
echo "Done. MCP servers will reconnect on next tool call."
