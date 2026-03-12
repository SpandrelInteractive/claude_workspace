# Observability & Cost Tracking

## Overview

Observability is built on Langfuse (self-hosted) and integrated at three levels:
1. **Automatic** — PostToolUse hook logs every MCP tool call
2. **Workflow** — LangGraph nodes traced via `@observe()` decorator
3. **On-demand** — Manual queries via langfuse-mcp tools

## Langfuse Architecture

```mermaid
graph TB
    subgraph "Data Sources"
        H[PostToolUse Hook<br/>~/.claude/hooks/log-to-langfuse.py]
        OM[orchestrator-mcp<br/>tracing.py @observe]
        M[Manual<br/>langfuse-mcp log_event]
    end

    subgraph "Langfuse Stack"
        LF[Langfuse Server<br/>localhost:3000]
        PG[PostgreSQL<br/>langfuse-db]
    end

    subgraph "Consumers"
        CR[get_cost_report]
        AP[get_agent_performance]
        TR[get_traces]
        UI[Langfuse Web UI]
    end

    H -->|HTTP POST| LF
    OM -->|Python SDK| LF
    M -->|Python SDK| LF
    LF --> PG
    LF --> CR & AP & TR & UI
```

## What Gets Traced

### Automatic (PostToolUse Hook)

Every MCP tool call is logged with:
- **Tool name** (e.g., `mcp__gemini__analyze_files`)
- **Timestamp**
- **Duration** (measured by hook)
- **Input size** (character count of arguments)
- **Agent context** (which subagent, if any)

The hook script receives tool call metadata via stdin from Claude Code's hook system.

### Workflow Tracing (orchestrator-mcp)

Each workflow creates a Langfuse trace with:
- **Trace ID** = workflow_id
- **Spans** per node (plan, route, execute, review, etc.)
- **Generations** per LLM call within nodes
  - Model used
  - Input/output token counts
  - Cost (calculated from model pricing)
  - Latency
- **Scores** for output quality (when Evaluator role assesses)

### Manual Events

Logged via `langfuse-mcp.log_event()` for:
- Significant decisions (model escalation, budget pause)
- Error recovery actions
- User feedback on results

## Hook Implementation

### PostToolUse — log-to-langfuse.py

```
Trigger: After any MCP tool call (matcher: "mcp__*")
Timeout: 5000ms
Input: JSON via stdin with tool_name, tool_input, duration
Output: None (fire-and-forget to Langfuse)
```

**Data flow:**
1. Claude Code executes MCP tool
2. Hook receives call metadata via stdin
3. Script POSTs to Langfuse API (or uses SDK)
4. Non-blocking — failure doesn't affect tool result

### PostToolUse — update-task-artifact.py

```
Trigger: After Task* tool calls (matcher: "Task.*")
Timeout: 3000ms
Input: JSON via stdin with tool_name, tool_input, tool_response
Output: Writes .claude/artifacts/tasks.md
```

**Data flow:**
1. Claude Code calls TaskCreate/TaskUpdate/TaskList
2. Hook parses task data from stdin, updates `.tasks-state.json`
3. Renders markdown task list with status icons and agent attribution
4. Auto-opens in VSCodium on first creation

### PostToolUse — update-workflow-artifact.py

```
Trigger: After orchestrator workflow calls (matcher: "mcp__orchestrator__(run_workflow|workflow_status)")
Timeout: 5000ms
Input: JSON via stdin with tool_name, tool_response
Output: Writes .claude/artifacts/workflow_status.md
```

**Data flow:**
1. Claude Code calls `run_workflow` or `workflow_status`
2. Hook parses workflow status from JSON response
3. Renders workflow progress with completed steps and cost
4. Auto-opens in VSCodium on first creation

### PreToolUse — quota-check.py

```
Trigger: Before Agent tool calls (matcher: "Agent")
Timeout: 3000ms
Input: JSON via stdin with tool_name, tool_input (includes model param)
Output: Warning message if quota low, or empty to proceed
```

**Data flow:**
1. Claude Code prepares to spawn subagent
2. Hook checks cached quota state (file-based, updated by cron)
3. If quota critically low, returns warning message
4. Claude Code sees warning and can adjust model selection

## Cost Reporting

### get_cost_report(period, group_by)

Queries Langfuse for aggregated cost data.

**Example output:**
```json
{
  "period": "24h",
  "total_cost": 1.47,
  "by_model": {
    "claude-opus-4-6": { "calls": 12, "tokens": 45000, "cost": 0.89 },
    "claude-sonnet-4-6": { "calls": 34, "tokens": 120000, "cost": 0.48 },
    "claude-haiku-4-5": { "calls": 15, "tokens": 30000, "cost": 0.05 },
    "gemini-3-flash": { "calls": 89, "tokens": 500000, "cost": 0.00 },
    "gemini-3.1-pro": { "calls": 23, "tokens": 200000, "cost": 0.00 },
    "gemini-2.5-flash-lite": { "calls": 45, "tokens": 100000, "cost": 0.00 }
  },
  "by_agent": {
    "orchestrator": { "calls": 12, "cost": 0.89 },
    "implementer": { "calls": 34, "cost": 0.48 },
    "reviewer": { "calls": 89, "cost": 0.00 }
  }
}
```

### Optimization Feedback Loop

```mermaid
graph LR
    A[Workflow executes] --> B[Langfuse traces]
    B --> C[get_cost_report]
    C --> D{Cost optimal?}
    D -->|No| E[Adjust router thresholds]
    D -->|Yes| F[Continue]
    E --> G[Update budgets.py]

    B --> H[get_agent_performance]
    H --> I{Quality acceptable?}
    I -->|No| J[Escalate model tier]
    I -->|Yes| F

    B --> K[DSPy optimization<br/>Phase 6]
    K --> L[Improved prompts]
```

## Langfuse Self-Hosted Setup

### Docker Compose Services

```yaml
langfuse:
  image: langfuse/langfuse:latest
  ports: ["3000:3000"]
  depends_on: [langfuse-db]
  environment:
    DATABASE_URL: postgresql://langfuse:langfuse@langfuse-db:5432/langfuse
    NEXTAUTH_SECRET: <generated-secret>
    NEXTAUTH_URL: http://localhost:3000
    SALT: <generated-salt>

langfuse-db:
  image: postgres:16
  environment:
    POSTGRES_USER: langfuse
    POSTGRES_PASSWORD: langfuse
    POSTGRES_DB: langfuse
  volumes: ["./langfuse_data:/var/lib/postgresql/data"]
```

### Initial Setup Steps
1. Start containers: `docker compose up -d langfuse langfuse-db`
2. Access UI: http://localhost:3000
3. Create account and project
4. Generate API keys (public + secret)
5. Configure in MCP server env vars

## Critical Path Coverage

| Path | Traced By | Data Captured |
|------|-----------|---------------|
| User request → model selection | PostToolUse hook | Tool call, model chosen |
| Workflow planning | orchestrator-mcp @observe | Task decomposition, model assignments |
| Gemini execution | orchestrator-mcp @observe | Tokens, cost, latency, output |
| Claude subagent execution | PostToolUse hook | Agent tool call, model param |
| Review cycle | orchestrator-mcp @observe | Review findings, approval status |
| Memory operations | PostToolUse hook | search/add calls, hit rate |
| Budget decisions | orchestrator-mcp @observe | Pause events, escalations |
| Task progress | update-task-artifact.py hook | Task list artifact in `.claude/artifacts/tasks.md` |
| Workflow artifacts | update-workflow-artifact.py hook + orchestrator artifacts.py | Plans, reviews, status in `.claude/artifacts/` |
