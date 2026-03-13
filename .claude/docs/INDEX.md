# Multi-Agent Orchestration (MAO) Framework

A Claude Code extension framework that coordinates multiple AI models through MCP servers, consolidated hooks, and LangGraph workflows. It turns Claude Code from a single-model CLI into a multi-agent system with persistent memory, observability, quota management, and structured artifact generation.

## How It Works

```
User → Claude Code (Opus) → MCP Servers → AI Models (Claude + Gemini)
                ↓                              ↓
          Skills + Hooks              Proxy (antigravity v2)
                ↓                              ↓
          Artifacts                     Langfuse Traces
```

**Claude Code** is the outer orchestrator. It delegates to **5 MCP servers** for specialized capabilities, enforces budgets through **2 consolidated hooks**, persists knowledge in **mem0** (vector + graph), and generates **structured artifacts** at workflow phase transitions. All LLM calls route through an **instrumented proxy** that provides Langfuse tracing, multi-account failover, and velocity-based quota management.

The framework is split into two layers:
- **Generic infrastructure** (reusable across projects) — MCP servers, hooks, skills, proxy, observability
- **Project customization** — domain skills, review checklists, workflow types, entity conventions

## Architecture

| Component | Purpose |
|-----------|---------|
| 5 MCP servers | Workflow engine, Gemini offloading, persistent memory, observability analytics, sequential reasoning |
| 2 hooks | Pre: session gate, budget, model selection, delegation. Post: tracing, throttle, artifacts, memory, docs |
| 3 state files | Session (daily reset), persistent (cross-day), tasks (per-session) |
| 3 trace sources | PostToolUse hook, proxy middleware, OTEL bridge — all session-linked in Langfuse |
| Proxy v2 | Antigravity fork on port 1338 with Langfuse middleware, velocity tracking, multi-account failover |
| Skills | Markdown behavioral guidance loaded into agent context — generic + project-specific |
| Artifacts | Structured deliverables (plans, reviews, walkthroughs) generated at workflow phase transitions |

## Documentation

### Getting Started

| Guide | Description |
|-------|-------------|
| [Usage Guide](usage-guide.md) | Practical reference: routing cheat sheet, MCP tool usage, agent roles, common workflows, troubleshooting |
| [Project Setup Guide](project-setup-guide.md) | Step-by-step instructions to instantiate the framework for a new project |

### Architecture

| Guide | Description |
|-------|-------------|
| [Architecture Overview](architecture-overview.md) | System diagrams, data flows, model selection flowchart, component interactions, design decisions |
| [MCP Servers](mcp-servers.md) | Server inventory, dependency diagram, tool reference, and configuration for all 5 servers |
| [Observability](observability.md) | 3 trace sources, 2 consolidated hooks, state files, proxy tracing, OTEL bridge, Langfuse setup |
| [Workflows](workflows.md) | LangGraph state machines: feature, review, refactor, sprint — state schemas and step definitions |

### Deep Dives

| Guide | Description |
|-------|-------------|
| [Agent Roles](agent-roles.md) | 6 role definitions (Orchestrator → Fast-Coder), model assignments, budget tiers, escalation paths |
| [Rate Limiting](rate-limiting.md) | 4-layer quota architecture: proxy failover, orchestrator polling, cron monitoring, per-workflow budgets |
| [Skills Guide](skills-guide.md) | Skill ecosystem: generic vs project skills, composition patterns, creation guide |
| [Artifacts](artifacts.md) | Artifact lifecycle: types, generation triggers, archival, feedback markers, file layout |

### Project-Specific

| Guide | Description |
|-------|-------------|
| [RFP Gatherer Guide](rfp_gatherer-guide.md) | Domain entities, scraper patterns, scoring engine, API conventions, review checklist for RFP Gatherer |

## Infrastructure

| Service | Endpoint | Managed By |
|---------|----------|------------|
| Proxy v2 | `localhost:1338` | PM2 (`antigravity-v2`) |
| Langfuse | `localhost:3000` | Docker Compose |
| Qdrant | `localhost:6333` | Docker Compose |
| Ollama | `localhost:11434` | System service |
| OTEL Collector | `localhost:4317/4318` | Docker Compose |
| OTEL Bridge | (internal) | Docker Compose |

## CLI Tools

| Tool | Usage |
|------|-------|
| `reset-mcps.sh --check` | Check MCP server health without killing |
| `reset-mcps.sh [server]` | Kill MCP server (tools lost until Claude Code restart) |
| `init_session` | Validate infrastructure, write session breadcrumb, unlock tools |

## Model Selection

```
FREE:  Gemini 2.5 Flash Lite → Gemini 3 Flash → Gemini 3.1 Pro
PAID:  Haiku 4.5 ($) → Sonnet 4.6 ($$) → Opus 4.6 ($$$)

Rule: cheapest model that can do the job. Gemini first, Claude when required.
```
