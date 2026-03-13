# MAO Framework — Technical Design Document

**Version:** 2.0
**Date:** 2026-03-13
**Status:** Implemented

---

## 1. System Architecture

### 1.1 Overview

```
┌─────────────────────────────────────────────────────────────────┐
│ Claude Code CLI (Opus 4.6 — Outer Orchestrator)                 │
├──────────┬──────────┬──────────┬──────────┬─────────────────────┤
│ PreTool  │ PostTool │ Skills   │ Artifacts│ Agent Tool          │
│ Gate     │ Trace    │ (md)     │ (md)     │ (Sonnet/Haiku)      │
├──────────┴──────────┴──────────┴──────────┴─────────────────────┤
│                    MCP Server Layer                              │
│ ┌────────────┐ ┌──────────┐ ┌────────┐ ┌────────┐ ┌─────────┐ │
│ │orchestrator│ │ gemini   │ │ mem0   │ │langfuse│ │seq-think│ │
│ │ -mcp       │ │-delegate │ │ -mcp   │ │ -mcp   │ │         │ │
│ └─────┬──────┘ └────┬─────┘ └───┬────┘ └───┬────┘ └─────────┘ │
├───────┼─────────────┼───────────┼───────────┼───────────────────┤
│       │     Infrastructure Layer│           │                   │
│  ┌────▼─────┐  ┌────▼────┐  ┌──▼───┐  ┌───▼────┐              │
│  │ Proxy v2 │  │ Ollama  │  │Qdrant│  │Langfuse│              │
│  │ :1338    │  │ :11434  │  │:6333 │  │ :3000  │              │
│  └────┬─────┘  └─────────┘  └──────┘  └───▲────┘              │
│       │                                     │                   │
│  ┌────▼──────────────┐  ┌──────────────────┘                   │
│  │ Gemini API        │  │  OTEL Collector :4318                │
│  │ (Google)          │  │  → OTEL Bridge → Langfuse            │
│  └───────────────────┘  └──────────────────────────────────────┘
```

### 1.2 Component Registry

| Component | Location | Language | Transport |
|-----------|----------|----------|-----------|
| orchestrator-mcp | ai-infra/orchestrator-mcp/ | Python | MCP stdio |
| gemini-delegate | ai-infra/gemini-delegate/ | Python | MCP stdio |
| mem0-mcp | ai-infra/mem0-mcp/ | Python | MCP stdio |
| langfuse-mcp | ai-infra/langfuse-mcp/ | Python | MCP stdio |
| Proxy v2 | ai-infra/proxy/ | Node.js | HTTP :1338 |
| OTEL Bridge | ai-infra/otel-bridge/ | Python | File tail |
| pre-tool-gate | .claude/framework/hooks/ | Python | Claude hook |
| post-tool-trace | .claude/framework/hooks/ | Python | Claude hook |

### 1.3 Data Stores

| Store | Service | Port | Purpose | Persistence |
|-------|---------|------|---------|-------------|
| Qdrant | Docker | 6333 | Memory vector embeddings | Docker volume |
| Neo4j | Docker | 7687 | Memory knowledge graph | Docker volume |
| PostgreSQL | Docker | 5432 (internal) | Langfuse data | Docker volume |
| SQLite | Local file | N/A | Workflow checkpoints | orchestrator-mcp/checkpoints.db |
| JSON files | Local fs | N/A | Session/persistent/task state | .claude/artifacts/*.json |

---

## 2. Hook System

### 2.1 Pre-Tool Gate (`pre-tool-gate.py`)

Executes before every tool call. 6 gates run in sequence. First blocking gate wins.

```
Input: Claude Code hook JSON (stdin)
  → parse tool_name, tool_input, session_id
  → Gate 1: Session Gate
  → Gate 2: Pending Actions
  → Gate 3: Throttle Gate
  → Gate 4: Model Gate
  → Gate 5: Task Gate
  → Gate 6: Gemini Delegation Gate
Output: JSON {decision: "allow"} or {decision: "block", message: "..."}
```

**Gate 1 — Session Gate**
- Checks: `.claude/artifacts/.session-validated` exists with today's date
- Whitelist: `init_session`, `validate_system`, `ToolSearch`
- Block: all other tools until session validated
- Side effect: writes session_id to `~/.claude-session-id`

**Gate 2 — Pending Actions**
- Checks: pending memory saves or stale docs in persistent state
- Action: non-blocking reminder (10-minute cooldown)
- Never blocks

**Gate 3 — Throttle Gate**
- Checks: Agent call counters against budget profile limits
- Profile: from `SESSION_BUDGET` env var (default: medium)
- Block: if opus/sonnet/total limits exceeded
- Counters: read from `.session-state.json`

**Gate 4 — Model Gate**
- Checks: Agent tool's `model` param against `subagent_type`
- Rules:
  - Opus blocked for: Explore, Plan, claude-code-guide
  - Sonnet blocked for: Explore
- Block: with suggestion to use cheaper model

**Gate 5 — Task Gate**
- Checks: total_agent_calls > 5 AND no TaskCreate used
- Action: one-shot reminder (dismissed after first fire)
- Never blocks

**Gate 6 — Gemini Delegation Gate**
- Checks: unique source files read > threshold (default: 4)
- Trigger: only on Read tool
- Skip: config files (.json, .yaml, .env, .md, .toml, .cfg, .ini, .lock)
- Cooldown: 5 minutes between suggestions
- Action: suggest `analyze_files` instead

### 2.2 Post-Tool Trace (`post-tool-trace.py`)

Executes after every tool call. 6 handlers run sequentially. All are non-blocking.

```
Input: Claude Code hook JSON (stdin)
  → parse tool_name, tool_input, output, session_id
  → Handler 1: Langfuse Trace
  → Handler 2: Throttle Tracker
  → Handler 3: Task Artifact
  → Handler 4: Workflow Artifact
  → Handler 5: Memory Save
  → Handler 6: Doc Tracker
```

**Handler 1 — Langfuse Trace**
- Fires: all tools except ToolSearch
- Sends: POST to Langfuse `/api/public/ingestion`
- Payload: trace with name, metadata (source, agent, tool_name, model), sessionId
- Auth: Basic (LANGFUSE_PUBLIC_KEY:LANGFUSE_SECRET_KEY)
- Timeout: 3 seconds, fire-and-forget

**Handler 2 — Throttle Tracker**
- Fires: Agent tool calls only
- Extracts: model tier from tool_input.model (opus/sonnet/haiku)
- Increments: tier counter + total_agent_calls in session state
- Fallback: unknown models → "sonnet" tier

**Handler 3 — Task Artifact**
- Fires: TaskCreate, TaskUpdate, TaskGet, TaskList
- Reads: `.tasks-state.json`
- Generates: `.claude/artifacts/tasks.md` (formatted checklist)
- Archives: previous version to `archive/`

**Handler 4 — Workflow Artifact**
- Fires: `mcp__orchestrator__run_workflow`, `mcp__orchestrator__workflow_status`
- Parses: workflow result from tool output
- Generates: `.claude/artifacts/workflow_status.md`

**Handler 5 — Memory Save**
- Fires: `mcp__orchestrator__run_workflow` when status is "completed"
- Writes: outcome to `.persistent-state.json` pending memory queue
- Queue consumed by: `init_session()` on next session start

**Handler 6 — Doc Tracker**
- Fires: Edit, Write tools
- Checks: file_path against `_SOURCE_TO_DOCS` mapping
- Marks: related docs as "stale" in persistent state
- Dynamically resolves: framework doc paths from `__file__` location

### 2.3 Shared Library (`hooks/lib/`)

**state.py**
- `artifacts_dir()` → resolves `.claude/artifacts/` from `CLAUDE_PROJECT_DIR`
- `load_session_state()` / `save_session_state()` → `.session-state.json`
- `load_persistent_state()` / `save_persistent_state()` → `.persistent-state.json`
- `load_task_state()` / `save_task_state()` → `.tasks-state.json`
- `write_session_id(session_id)` → `~/.claude-session-id`
- Legacy migration: reads old 6-file format on first load, merges into 3-file format

**langfuse.py**
- `send_trace(name, metadata, session_id)` → Langfuse REST API
- `SKIP_TOOLS` set: tools that should not be traced (ToolSearch)
- Auth: reads `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` from env
- Non-blocking: catches all exceptions, logs warnings

**decisions.py**
- `should_delegate_to_gemini(files_read, cooldown)` → bool
- `get_model_tier(model_name)` → "opus" | "sonnet" | "haiku" | None
- `is_config_file(path)` → bool
- Budget profile definitions: `PROFILES = {low: {...}, medium: {...}, ...}`

---

## 3. MCP Server Specifications

### 3.1 orchestrator-mcp

**Entry:** `orchestrator_mcp.server:main` (FastMCP, stdio transport)

**Tools:**

| Tool | Signature | Description |
|------|-----------|-------------|
| `init_session` | `() → dict` | Validate services, consume memory queue, write breadcrumb |
| `validate_system` | `() → dict` | Health check all 4 services |
| `run_workflow` | `(type, description, files?, options?) → dict` | Launch stateful workflow |
| `workflow_status` | `(workflow_id) → dict` | Poll workflow progress |
| `list_workflows` | `(status_filter?) → list[dict]` | List workflows by status |
| `cancel_workflow` | `(workflow_id, reason?) → dict` | Cancel running workflow |
| `get_quota_state` | `() → dict` | Poll proxy for model availability |
| `get_quota_report` | `() → dict` | Velocity + limits + budget + risk |
| `optimize_prompts` | `(role, examples_count?) → dict` | DSPy prompt optimization |

**Dependencies:** proxy (ANTHROPIC_BASE_URL), Langfuse, SQLite

**Key Internal Modules:**
- `session.py` — init_session flow, breadcrumb management, memory queue
- `quota.py` — proxy health polling, quota state caching
- `artifacts.py` — markdown artifact generation (task_plan, impl_plan, review_result, status)
- `executor.py` — Gemini call execution with session_id header propagation
- `graph.py` — LangGraph checkpointer (SQLite) management
- `workflows/` — 5 workflow StateGraph implementations

### 3.2 gemini-delegate

**Entry:** `gemini_delegate.server:main` (FastMCP, stdio transport)

**Tools:**

| Tool | Signature | Description |
|------|-----------|-------------|
| `analyze_files` | `(file_paths, question) → str` | Read files + answer via Gemini |
| `review_diff` | `(diff_content) → str` | Code review via Gemini |
| `explain_architecture` | `(path?) → str` | Codebase overview via Gemini |
| `refresh_index` | `() → str` | Rebuild .gemini-index digest |
| `ask_gemini` | `(question, context?) → str` | General Gemini question |

**Dependencies:** proxy (ANTHROPIC_BASE_URL), .gemini-index file

**Key internals:**
- `llm.py` — Gemini call wrapper, sends X-Session-Id and X-Caller headers
- Session_id resolution: `CLAUDE_SESSION_ID` env → `~/.claude-session-id` file

### 3.3 mem0-mcp

**Entry:** `mem0_mcp.server:main` (FastMCP, stdio transport)

**Tools:**

| Tool | Signature | Description |
|------|-----------|-------------|
| `add_memory` | `(text) → dict` | Store fact with vector + graph extraction |
| `search_memories` | `(query) → dict` | Vector similarity search |
| `list_memories` | `() → dict` | List all stored memories |
| `delete_memory` | `(memory_id) → dict` | Delete by ID |
| `search_graph` | `(query) → dict` | Knowledge graph traversal |
| `get_entity` | `(entity_name) → dict` | Inspect graph node |

**Dependencies:** Qdrant (vectors), Ollama/bge-m3 (embeddings), Neo4j (graph, optional), proxy (LLM for extraction)

**Configuration:**
- `MEM0_APP_ID` — namespace isolation per project
- `MEM0_ENABLE_GRAPH` — enable/disable Neo4j graph store

### 3.4 langfuse-mcp

**Entry:** `langfuse_mcp.server:main` (FastMCP, stdio transport)

**Tools:**

| Tool | Signature | Description |
|------|-----------|-------------|
| `get_cost_report` | `(period?, group_by?) → str` | Aggregated cost/activity breakdown |
| `get_agent_performance` | `(agent_id, period?) → str` | Agent-specific metrics |
| `get_traces` | `(trace_id) → str` | Full trace with observations |
| `get_session_summary` | `(session_id?) → str` | Session overview from all 3 sources |

**Dependencies:** Langfuse REST API (LANGFUSE_HOST, auth keys)

**Key internals:**
- `_fetch_traces(limit, session_id)` — paginated fetcher (Langfuse caps at 100/page)
- `_fetch_observations(trace_id)` — per-trace observation detail
- `_filter_by_period(traces, period)` — ISO timestamp filtering

---

## 4. Workflow Engine

### 4.1 Common State Schema

All workflows share `WorkflowState` (TypedDict):

```python
workflow_id: str          # UUID
workflow_type: str        # "feature" | "review" | "refactor" | "sprint" | "spdd_feature"
description: str
files: list[str]
options: dict
status: str               # planning | executing | reviewing | paused | completed | failed
current_step: str
completed_steps: list[dict]
tasks: list[dict]
task_index: int
messages: list            # LangGraph message accumulator
next_action: dict
budget_profile: str
total_cost: float
cost_limit: float
needs_human_input: bool
error: str | None
```

### 4.2 Workflow Graphs

**Review** (3 nodes, linear):
```
[*] → gather_diff → analyze (Gemini Flash) → summarize → [*]
```

**Feature** (6 nodes, routing loop):
```
[*] → plan (Gemini Pro) → route → execute_gemini|execute_claude → review → route|complete → [*]
     route → pause (if budget exceeded)
```

**Refactor** (5 nodes):
```
[*] → analyze_scope → plan_changes → execute_change → verify → execute_change|complete → [*]
```

**Sprint** (4 nodes):
```
[*] → gather_context → analyze_backlog → decompose → prioritize → [*]
```

**SPDD Feature** (4 nodes, verification gates):
```
[*] → context_acquire → research → [fail?→END] → spec → [fail?→END] → synthesize → [*]
```

### 4.3 SPDD Context Acquisition

The `context_acquire` node loads (no LLM calls):
1. SPDD skill files (1-research.md, 2-spec.md, 3-implementation.md)
2. Project docs (CLAUDE.md, PSD.md, architecture_flow.md)
3. Domain skills from `options.domain_skills`
4. File contents from `files` (up to 10 files, <20KB each)

Produces: `context_bundle` dict in workflow state for downstream nodes.

---

## 5. Observability Pipeline

### 5.1 Three Trace Sources

| Source | Origin | Data | Session Linking |
|--------|--------|------|-----------------|
| posttooluse-hook | post-tool-trace.py | Tool name, agent, action, timing | `input_data.session_id` |
| proxy-middleware | langfuse-middleware.js | Model, tokens, cost, latency, stream | `X-Session-Id` header |
| otel-bridge | bridge.py | Claude API model, tokens, cost, duration | OTEL span attributes |

### 5.2 Proxy Middleware

Intercepts every `POST /v1/messages`:
1. Extracts `X-Session-Id` and `X-Caller` headers
2. Creates Langfuse trace with name `proxy:{model}`
3. Adds generation span with token counts from response
4. Adds score for latency
5. Flushes batch (flushAt=5, flushInterval=2000ms)

### 5.3 OTEL Bridge

Long-running process:
1. Tails `/data/otel-traces.jsonl` written by OTEL Collector
2. Parses Claude Code `api_request` events
3. Extracts: model, input_tokens, output_tokens, cost, duration
4. Sends to Langfuse `/api/public/ingestion` as trace + generation

### 5.4 Proxy Endpoints

| Endpoint | Method | Returns |
|----------|--------|---------|
| `/health` | GET | Account status, model rate limits, velocity data |
| `/velocity` | GET | Call rates: 5min, 1hr, 24hr by model family |
| `/v1/models` | GET | Available model list |
| `/account-limits` | GET | Detailed per-model quota table |

---

## 6. State Management

### 6.1 File Layout

All state in `.claude/artifacts/`:

```
.session-state.json      ← daily reset
.persistent-state.json   ← cross-day
.tasks-state.json        ← per-session tasks
.session-validated       ← breadcrumb (date string)
```

### 6.2 Session State Schema

```json
{
  "date": "2026-03-13",
  "session": { "validated": true, "validated_at": "...", "services": {}, "context_loaded": [] },
  "throttle": { "profile": "medium", "opus_calls": 0, "sonnet_calls": 0, "haiku_calls": 0, "gemini_calls": 0, "total_agent_calls": 0, "blocked_calls": 0 },
  "reads": { "files_read": [], "last_delegation_block": 0 },
  "pending_actions": { "last_reminder": 0 },
  "task_gate_dismissed": false
}
```

Reset trigger: `date` field != today → reset all counters, keep `_migrated` flag.

### 6.3 Persistent State Schema

```json
{
  "doc_staleness": { "modified_sources": {}, "stale_docs": {} },
  "pending_memory_save": []
}
```

### 6.4 Legacy Migration

On first load, if old files exist (`.throttle-state.json`, `.read-tracker.json`, etc.), `state.py` reads them, merges into the new 3-file format, and sets `_migrated: true`.

---

## 7. Deployment Architecture

### 7.1 Git Subtree Model

```
project-repo/
├── .claude/framework/          ← git subtree from claude_workspace
│   ├── hooks/                  ← synced
│   ├── docs/                   ← synced
│   ├── tools/                  ← synced
│   ├── skills/                 ← synced (generic)
│   ├── templates/              ← synced (used during setup only)
│   └── setup.sh                ← deployment script
├── .claude/docs/               ← project-specific (not in subtree)
├── .claude/skills/             ← project-specific
├── .claude/settings.local.json ← project-specific
├── .claude/artifacts/          ← generated, gitignored
├── CLAUDE.md                   ← project-specific
└── .mcp.json                   ← project-specific
```

### 7.2 Update Flow

```bash
# Pull framework updates (merge-based, handles conflicts)
git subtree pull --prefix=.claude/framework <mao-repo> main --squash

# Push framework improvements back to template
git subtree push --prefix=.claude/framework <mao-repo> main
```

### 7.3 Docker Services

```yaml
services:
  qdrant:        # :6333 — vector store
  neo4j:         # :7474/:7687 — graph store
  langfuse:      # :3000 — observability
  langfuse-db:   # postgres (internal)
  otel-collector: # :4317/:4318 — telemetry receiver
  otel-bridge:   # (internal) — OTEL→Langfuse translator
```

Proxy runs outside Docker via PM2 as `antigravity-v2` on port 1338.

---

## 8. Environment Variables

| Variable | Used By | Default | Purpose |
|----------|---------|---------|---------|
| `CLAUDE_PROJECT_DIR` | hooks, state.py | cwd | Project root path |
| `SESSION_BUDGET` | pre-tool-gate | "medium" | Budget profile |
| `ANTHROPIC_BASE_URL` | MCP servers | http://localhost:1338 | Proxy URL |
| `ANTHROPIC_API_KEY` | MCP servers | "dummy-key" | Proxy auth (passthrough) |
| `LANGFUSE_HOST` | langfuse-mcp, orchestrator | http://localhost:3000 | Langfuse URL |
| `LANGFUSE_PUBLIC_KEY` | hooks, langfuse-mcp | (required) | Langfuse auth |
| `LANGFUSE_SECRET_KEY` | hooks, langfuse-mcp | (required) | Langfuse auth |
| `MEM0_APP_ID` | mem0-mcp | (required) | Memory namespace |
| `MEM0_ENABLE_GRAPH` | mem0-mcp | "true" | Enable Neo4j graph |
| `CLAUDE_SESSION_ID` | gemini-delegate, executor | (auto-resolved) | Override session ID |
| `CLAUDE_CODE_ENABLE_TELEMETRY` | Claude Code | "1" | Enable OTEL export |
