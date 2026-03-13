#!/usr/bin/env bash
# Reset MCP servers by killing their processes.
#
# WARNING: Killing an MCP server mid-session permanently removes its tools
# for the rest of the Claude Code session. Tools will NOT auto-reconnect.
# Only use this when you're prepared to restart Claude Code afterward,
# or when the server is already broken and you have nothing to lose.
#
# Usage:
#   reset-mcps.sh                     # reset all MCP servers (destructive)
#   reset-mcps.sh mem0 gemini         # reset specific servers only
#   reset-mcps.sh --check             # check server health without killing
#   reset-mcps.sh --check langfuse    # check specific server health

set -euo pipefail

MCP_CONFIG="${CLAUDE_PROJECT_DIR:-.}/.mcp.json"

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

  echo "[$name] Reset complete (restart Claude Code to restore tools)"
}

check_server() {
  local name="$1"
  local pattern="${SERVER_PATTERNS[$name]:-}"

  if [[ -z "$pattern" ]]; then
    echo "[$name] Unknown server"
    return 1
  fi

  local pids
  pids=$(pgrep -f "$pattern" 2>/dev/null || true)

  if [[ -z "$pids" ]]; then
    echo "[$name] NOT RUNNING"
    return 1
  fi

  local pid_count
  pid_count=$(echo "$pids" | wc -l)
  echo "[$name] RUNNING ($pid_count processes)"
  return 0
}

# Parse flags
CHECK_ONLY=false
if [[ "${1:-}" == "--check" ]]; then
  CHECK_ONLY=true
  shift
fi

# Determine which servers to target
if [[ $# -eq 0 ]]; then
  targets=("${!SERVER_PATTERNS[@]}")
else
  targets=("$@")
fi

if $CHECK_ONLY; then
  echo "MCP server health check:"
  echo "---"
  for server in "${targets[@]}"; do
    check_server "$server" || true
  done
  echo "---"
  exit 0
fi

# Destructive path — warn
echo "⚠  WARNING: Killing MCP servers removes their tools for this session."
echo "   You will need to restart Claude Code to get them back."
echo ""
echo "Resetting MCP servers: ${targets[*]}"
echo "---"

for server in "${targets[@]}"; do
  reset_server "$server"
done

echo "---"
echo "Done. Restart Claude Code to restore tools."
