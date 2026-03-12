# Observability & Cost Tracking

## Overview

Observability is built on Langfuse (self-hosted) and a 7-phase hook system that enforces orchestration rules and tracks usage automatically.

## Langfuse Architecture

```mermaid
graph TB
    subgraph "Data Sources"
        OM[orchestrator-mcp<br/>tracing.py @observe]
        M[Manual<br/>langfuse-mcp log_event]
        MS[memory-save.py<br/>workflow outcomes]
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

    OM -->|Python SDK| LF
    M -->|Python SDK| LF
    MS -->|pending file| LF
    LF --> PG
    LF --> CR & AP & TR & UI
```

## Hook System — MAO Enforcement

The Multi-Agent Orchestration (MAO) enforcement system uses Claude Code hooks to automatically enforce cost, model selection, and workflow discipline.

### Hook Registry

#### PreToolUse Hooks (run before tool execution)

| Matcher | Hook | Phase | Description |
|---------|------|-------|-------------|
| `.*` | `session-gate.py` | 1 | Hard-blocks ALL tools until `init_session` writes daily breadcrumb |
| `Agent` | `throttle.py` | 2 | Blocks Agent calls when model tier budget exhausted |
| `Agent` | `model-gate.py` | 4 | Enforces cheapest-capable-first model selection |
| `Agent` | `task-gate.py` | 3 | One-time reminder after 5+ agents without task tracking |
| `Read` | `gemini-delegation.py` | 5 | Suggests analyze_files after 5+ unique source file reads |

#### PostToolUse Hooks (run after tool execution)

| Matcher | Hook | Phase | Description |
|---------|------|-------|-------------|
| `Agent` | `throttle-tracker.py` | 2 | Increments call counters per model tier |
| `Task.*` | `update-task-artifact.py` | — | Maintains live task list artifact |
| `mcp__orchestrator__*` | `update-workflow-artifact.py` | — | Renders workflow status artifact |
| `mcp__orchestrator__*` | `memory-save.py` | 6 | Auto-captures workflow outcomes for mem0 |
| `(Edit\|Write)` | `doc-tracker.py` | 7 | Tracks source changes and flags stale docs |

### Phase 1: Session Gate (`session-gate.py`)

```
Trigger: PreToolUse on ALL tools (matcher: ".*")
Timeout: 2000ms
```

**Behavior:**
- Blocks every tool call until `init_session` from orchestrator-mcp is called
- `init_session` validates health (proxy, Qdrant, Ollama, Langfuse), checks quota, writes breadcrumb
- Breadcrumb: `.claude/artifacts/.session-validated` (JSON with date, services, context)
- Resets daily (midnight boundary)
- Whitelists: `validate_system`, `init_session`, `ToolSearch`
- Bootstrap escape: create `.mao-bootstrap` file in project root to bypass during initial setup

### Phase 2: Adaptive Throttle (`throttle.py` + `throttle-tracker.py`)

```
Trigger: PreToolUse + PostToolUse on Agent
Timeout: 1000ms each
State: .claude/artifacts/.throttle-state.json
```

**Budget profiles** (matches orchestrator-mcp `budgets.py`):

| Profile | Max Opus | Max Sonnet | Gemini |
|---------|----------|------------|--------|
| low | 0 | 2 | Unlimited |
| **medium** (default) | 2 | 10 | Unlimited |
| high | 5 | 25 | Unlimited |
| unlimited | No limit | No limit | Unlimited |

- Override via `SESSION_BUDGET` env var in `.envrc`
- Haiku calls are never throttled
- State resets daily
- When blocked: suggests cheaper model or Gemini delegation

### Phase 3: Task Gate (`task-gate.py`)

```
Trigger: PreToolUse on Agent
Timeout: 1000ms
```

- Fires once per session after 5+ Agent calls without `TaskCreate` or `run_workflow`
- Suggests structured work: `TaskCreate` for progress tracking, `run_workflow` for managed execution
- Auto-dismisses after firing once (writes dismiss flag to throttle state)

### Phase 4: Model Selection Gate (`model-gate.py`)

```
Trigger: PreToolUse on Agent
Timeout: 1000ms
```

Enforces cheapest-capable-first model hierarchy:
- **Explore/Plan/claude-code-guide** subagent types → blocks opus and sonnet
- **model=opus** → requires justifying keywords (debug, architecture, investigate, diagnose, etc.)
- **model=sonnet** → blocks short/simple tasks without implementation keywords

### Phase 5: Gemini Delegation (`gemini-delegation.py`)

```
Trigger: PreToolUse on Read
Timeout: 1000ms
```

- Tracks unique source file reads in throttle state
- After 5+ unique reads, blocks next Read with suggestion to use `analyze_files`
- Skips config/settings/markdown files (legitimate individual reads)
- 5-minute cooldown between blocks
- Retry allowed (the deny is a nudge, not a hard stop)

### Phase 6: Memory Auto-Save (`memory-save.py`)

```
Trigger: PostToolUse on mcp__orchestrator__(run_workflow|workflow_status)
Timeout: 2000ms
```

- When workflow reaches status=completed or status=failed
- Writes outcome summary to `.claude/artifacts/.pending-memory-save.json`
- Queue format: main Claude process should check and persist to mem0

### Phase 7: Documentation Sync (`doc-tracker.py`)

```
Trigger: PostToolUse on Edit|Write
Timeout: 1000ms
```

- Tracks source file modifications in `backend/`, `frontend/src/`, `orchestrator-mcp/`, `.claude/hooks/`
- Maps source patterns to related doc files
- Writes `.claude/artifacts/.doc-staleness.json` (machine-readable) and `doc_staleness.md` (human-readable)
- Accumulates triggers across edits within session

## Workflow Tracing (orchestrator-mcp)

Each workflow creates a Langfuse trace with:
- **Trace ID** = workflow_id
- **Spans** per node (plan, route, execute, review, etc.)
- **Generations** per LLM call within nodes
  - Model used
  - Input/output token counts
  - Cost (calculated from model pricing)
  - Latency
- **Scores** for output quality (when Evaluator role assesses)

## Cost Reporting

### get_cost_report(period)

Returns session throttle state and budget usage:

```json
{
  "period": "24h",
  "throttle": {
    "profile": "medium",
    "limits": {"max_opus_calls": 2, "max_sonnet_calls": 10},
    "usage": {"opus_calls": 1, "sonnet_calls": 3, "haiku_calls": 5, "total_agent_calls": 9},
    "remaining": {"opus": 1, "sonnet": 7}
  },
  "langfuse": "See http://localhost:3000 for detailed traces"
}
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
| Session initialization | session-gate.py + init_session | Service health, breadcrumb |
| Agent model selection | model-gate.py | Model denied/allowed, reason |
| Budget enforcement | throttle.py + throttle-tracker.py | Calls per tier, blocks |
| Workflow planning | orchestrator-mcp @observe | Task decomposition, model assignments |
| Gemini execution | orchestrator-mcp @observe | Tokens, cost, latency, output |
| Claude subagent execution | throttle-tracker.py | Agent calls per model tier |
| Review cycle | orchestrator-mcp @observe | Review findings, approval status |
| Workflow completion | memory-save.py | Outcome saved for mem0 |
| Source modifications | doc-tracker.py | Modified files, stale docs flagged |
| Task progress | update-task-artifact.py | Task list artifact |
| Workflow artifacts | update-workflow-artifact.py | Plans, reviews, status |
