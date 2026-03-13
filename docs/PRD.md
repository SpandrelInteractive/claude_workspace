# MAO Framework — Product Requirements Document

**Version:** 2.0
**Date:** 2026-03-13
**Status:** Implemented (all milestones complete)

---

## 1. Product Overview

The Multi-Agent Orchestration (MAO) framework extends Claude Code into a managed multi-agent system. It coordinates multiple AI models (Claude and Gemini), enforces cost budgets, maintains persistent memory across sessions, and provides full observability through Langfuse dashboards.

### 1.1 Problem Statement

Claude Code users working on large projects face three problems:
1. **Cost explosion** — defaulting to expensive models for all work
2. **Context fragmentation** — decisions and patterns lost between sessions
3. **Lack of structure** — no repeatable process for multi-step tasks

### 1.2 Solution

A framework layer on top of Claude Code that:
- Routes work to the cheapest capable model automatically
- Persists knowledge across sessions via vector + graph memory
- Decomposes complex tasks into managed, checkpointed workflows
- Traces every operation for cost visibility and debugging

### 1.3 Users

- **Primary:** Software engineers using Claude Code for daily development
- **Secondary:** Team leads reviewing AI-assisted work output

---

## 2. Functional Requirements

### FR-1: Session Management

**FR-1.1 Session Initialization**
- The system MUST validate all infrastructure services (proxy, Qdrant, Ollama, Langfuse) before allowing work
- If any service is down, the system MUST return specific fix commands and block all tool use
- The system MUST write a daily breadcrumb file upon successful validation
- The system MUST consume any pending memory queue entries from prior sessions
- **Acceptance:** `init_session()` returns `{status: "ready"}` with all services healthy, or `{status: "blocked", blockers: [...]}` with fix commands

**FR-1.2 Session Gate**
- All tool calls MUST be blocked until `init_session` succeeds for the current day
- Only `init_session`, `validate_system`, and `ToolSearch` are whitelisted before validation
- **Acceptance:** Calling any non-whitelisted tool before init_session returns a blocking message

**FR-1.3 Session Identity**
- Each session MUST have a unique `session_id` written to `~/.claude-session-id`
- All trace sources MUST use this session_id for cross-source correlation
- **Acceptance:** After init_session, `~/.claude-session-id` contains the current session UUID

### FR-2: Model Routing & Cost Optimization

**FR-2.1 Gemini-First Strategy**
- Free Gemini models MUST be preferred for all tasks they can handle
- Claude models MUST only be used when Gemini is insufficient
- **Acceptance:** Bulk file reads (3+) trigger a suggestion to use `analyze_files` instead of `Read`

**FR-2.2 Model Selection Gate**
- When spawning Agent subagents, the system MUST enforce cheapest-capable model selection
- Opus MUST be blocked for Explore/Plan/claude-code-guide subagent types
- Sonnet MUST be blocked for Explore subagent type
- **Acceptance:** Attempting `Agent(model: opus, subagent_type: Explore)` is blocked with a suggestion to use a cheaper model

**FR-2.3 Gemini Delegation Gate**
- After reading 4+ unique source files in a session, the system MUST suggest using `analyze_files`
- The gate MUST have a 5-minute cooldown between suggestions
- Config files (.json, .yaml, .md, etc.) MUST be excluded from the file count
- **Acceptance:** After reading 5 .py files, the next Read triggers a delegation suggestion

**FR-2.4 Budget Profiles**
- The system MUST support 4 budget profiles: low, medium (default), high, unlimited
- Each profile MUST define maximum Agent calls by model tier

| Profile | Max Opus | Max Sonnet | Max Total Agent |
|---------|----------|------------|-----------------|
| low | 1 | 5 | 15 |
| medium | 3 | 15 | 30 |
| high | 10 | 40 | 80 |
| unlimited | no limit | no limit | no limit |

- **Acceptance:** In "low" profile, the 2nd Opus Agent call is blocked

### FR-3: Persistent Memory

**FR-3.1 Vector Memory**
- The system MUST store facts, decisions, and patterns in a vector database (Qdrant)
- Similarity search MUST return relevant memories ranked by score
- **Acceptance:** `add_memory("Project uses FastAPI")` followed by `search_memories("web framework")` returns the stored fact

**FR-3.2 Knowledge Graph**
- The system MUST extract entity relationships from stored memories
- Graph queries MUST support traversal of entity relationships
- **Acceptance:** `add_memory("User model has many Orders")` creates searchable graph edges

**FR-3.3 Memory Queue**
- Workflow completions MUST queue outcomes for mem0 persistence
- `init_session` MUST consume the queue and return save instructions
- **Acceptance:** After a workflow completes and a new session starts, init_session returns the pending memory entries

### FR-4: Workflow Engine

**FR-4.1 Workflow Execution**
- The system MUST support 5 workflow types: feature, review, refactor, sprint, spdd_feature
- Each workflow MUST execute as a LangGraph state machine with checkpointed state
- Workflows MUST generate structured artifacts at phase transitions
- **Acceptance:** `run_workflow("review", "Review auth changes")` executes gather_diff → analyze → summarize and produces `review_result.md`

**FR-4.2 SPDD Workflow**
- The SPDD workflow MUST follow: context_acquire → research → spec → synthesize
- Context acquisition MUST load SPDD skills, project docs, and domain skills
- Verification gates MUST exist between research→spec and spec→synthesize
- If any phase fails, the workflow MUST route to END (not continue)
- **Acceptance:** A failed research phase produces a workflow with `status: "failed"` and does not attempt the spec phase

**FR-4.3 Workflow Status**
- Users MUST be able to check workflow progress at any time
- Status MUST include: current step, completed steps with costs, total cost, next action
- **Acceptance:** `workflow_status(id)` returns the current state with cost breakdown

**FR-4.4 Budget Enforcement**
- Each workflow type MUST have a default cost limit
- Workflows MUST pause when cost exceeds the limit
- Users MUST be able to approve additional budget or cancel
- **Acceptance:** A feature workflow hitting $2.00 pauses with `needs_human_input: true`

### FR-5: Observability

**FR-5.1 Three-Source Tracing**
- Tool calls MUST be traced via PostToolUse hook → Langfuse
- Gemini API calls MUST be traced via proxy middleware → Langfuse
- Claude API calls MUST be traced via OTEL bridge → Langfuse
- All three sources MUST share the same session_id
- **Acceptance:** After a session with Gemini calls, `get_session_summary()` shows traces from all 3 sources under one session_id

**FR-5.2 Cost Reporting**
- `get_cost_report(period)` MUST return real aggregated data grouped by source, model, or agent
- Reports MUST cover configurable periods: 1h, 24h, 7d, 30d
- **Acceptance:** `get_cost_report("1h", group_by="source")` returns trace counts for posttooluse-hook and proxy-middleware

**FR-5.3 Session Summary**
- `get_session_summary()` MUST return a session-level overview combining all 3 trace sources
- MUST include: total traces, cost, source breakdown, top tools, model usage, timeline
- MUST auto-resolve session_id from `~/.claude-session-id` if not provided
- **Acceptance:** Called without arguments, returns summary for the current session

**FR-5.4 Quota Reporting**
- `get_quota_report()` MUST return velocity-based quota data
- MUST include: call velocity (5min/1hr/24hr), model rate limits, session budget usage, lockout risk
- Risk levels MUST be: LOW, MODERATE, ELEVATED, HIGH
- **Acceptance:** After several Gemini calls, velocity data shows non-zero counts and correct risk level

### FR-6: Artifact System

**FR-6.1 Automatic Artifact Generation**
- Task state changes MUST trigger `tasks.md` artifact update
- Workflow state changes MUST trigger `workflow_status.md` artifact update
- Workflow planning phases MUST generate `task_plan.md`
- Workflow implementation phases MUST generate `implementation_plan.md`
- **Acceptance:** Creating a task via TaskCreate updates `.claude/artifacts/tasks.md`

**FR-6.2 Artifact Archival**
- Previous artifact versions MUST be archived with timestamps before overwriting
- Archives MUST be stored in `.claude/artifacts/archive/`
- **Acceptance:** After generating a second implementation plan, `archive/` contains the first version

**FR-6.3 User-Invoked Artifacts**
- `/implementation-plan` skill MUST generate a structured plan artifact
- `/walkthrough` skill MUST generate a work summary artifact
- Both MUST include `<!-- Leave feedback -->` markers for user input
- **Acceptance:** Running `/implementation-plan` creates the artifact and opens it in the editor

### FR-7: Project Deployment

**FR-7.1 Initial Setup**
- `setup.sh <project_id>` MUST deploy all templates with placeholder replacement
- MUST create project-specific directories for docs, skills, and artifacts
- MUST skip files that already exist (safe to re-run)
- **Acceptance:** Running `setup.sh my_app` creates CLAUDE.md, .mcp.json, .envrc with `my_app` substituted

**FR-7.2 Framework Updates**
- `git subtree pull --prefix=.claude/framework` MUST update framework files without touching project-specific files
- Project docs, skills, settings permissions, and artifacts MUST be preserved
- **Acceptance:** After pulling, project-specific `rfp_gatherer-guide.md` is unchanged, but framework docs are updated

### FR-8: Throttle Tracking

**FR-8.1 Agent Call Counting**
- Every Agent tool call MUST increment the appropriate tier counter (opus, sonnet, haiku)
- Total agent calls MUST be tracked separately
- Blocked calls MUST be counted
- **Acceptance:** After 3 Sonnet Agent calls, session state shows `sonnet_calls: 3, total_agent_calls: 3`

**FR-8.2 Doc Staleness Tracking**
- Edits to source files MUST flag related docs as potentially stale
- Stale doc warnings MUST be surfaced as pending actions
- **Acceptance:** Editing `backend/src/scoring_engine.py` flags `docs/PSD.md` as stale

---

## 3. Non-Functional Requirements

### NFR-1: Performance
- Hook execution MUST complete within timeout (pre: 2s, post: 5s)
- `init_session` MUST complete within 10 seconds with all services healthy
- Langfuse trace ingestion MUST be fire-and-forget (non-blocking)

### NFR-2: Reliability
- Hook failures MUST NOT block tool execution (non-fatal warnings)
- Missing state files MUST be created with defaults (not crash)
- Network failures to Langfuse MUST be silently logged, not surfaced

### NFR-3: Security
- Langfuse API keys MUST NOT be committed to git
- `.env` files MUST be gitignored
- Memory data stays local (Qdrant on localhost, no cloud)

### NFR-4: Maintainability
- Framework updates via git subtree MUST NOT require manual file moves
- All hook paths MUST be location-agnostic (use `__file__` and `CLAUDE_PROJECT_DIR`)
- State file format changes MUST include migration logic

---

## 4. Out of Scope

- Cloud deployment of infrastructure services
- Multi-user concurrent access to the same project
- GUI for workflow management (Langfuse dashboard is the UI)
- Automated testing pipeline (this document defines what to test, not CI/CD)
