# Claude Workspace Template

A production-ready template for building **multi-agent AI orchestration systems** on top of Claude Code. It provides the infrastructure, agent roles, workflow engine, memory system, and cost optimization layer needed to run complex software engineering tasks across multiple AI models — while keeping costs under control.

## What This Is

Claude Code is powerful on its own, but large projects quickly run into three problems: **cost explosion** from defaulting to expensive models, **context fragmentation** across sessions, and **lack of structure** for multi-step tasks. This template solves all three.

It wraps Claude Code in an orchestration layer that:

- **Routes work to the cheapest capable model.** A tiered system tries free Gemini models first (Flash Lite → Flash → Pro), then escalates to paid Claude models (Haiku → Sonnet → Opus) only when necessary. Most routine work — file analysis, code review, indexing — never touches Claude at all.
- **Decomposes tasks into managed workflows.** Multi-step work runs through LangGraph state machines with checkpointing, budget enforcement, and human-in-the-loop approval. The SPDD workflow provides structured research → spec → implementation pipelines with verification gates between phases.
- **Remembers context across sessions.** A dual-store memory system (Qdrant for vector similarity, Neo4j for relationship graphs) persists architectural decisions, domain knowledge, and patterns so you never re-explain your project.
- **Provides full observability.** Three trace sources (tool call hooks, proxy middleware, OTEL bridge) feed session-linked Langfuse dashboards showing exactly where your AI budget goes.

## How It Works

The system defines **eight specialized agent roles**, each mapped to specific model tiers:

| Role | Default Model | Responsibility |
|------|--------------|----------------|
| Orchestrator | Opus | Task decomposition, delegation, budget management |
| Architect | Gemini Pro → Opus | System design, entity modeling |
| Implementer | Sonnet | Multi-file code changes (runs in isolated worktrees) |
| Reviewer | Gemini Flash | Code review, checklist validation |
| Researcher | Gemini Pro | Codebase exploration, log analysis |
| Fast-Coder | Haiku | Quick fixes, boilerplate, simple edits |
| Indexer | Gemini Flash Lite | Codebase indexing via Repomix |
| Evaluator | Gemini Flash | Workflow cost analysis and optimization |

Two **consolidated hooks** enforce all policies automatically:

| Hook | Trigger | Handles |
|------|---------|---------|
| `pre-tool-gate.py` | PreToolUse `.*` | Session gate, budget enforcement, model selection, Gemini delegation suggestions |
| `post-tool-trace.py` | PostToolUse `.*` | Langfuse tracing, throttle tracking, task/workflow artifacts, memory queue, doc staleness |

A shared library at `.claude/hooks/lib/` (state.py, langfuse.py, decisions.py) keeps the hooks maintainable.

Five **MCP servers** handle the infrastructure:

| Server | Purpose |
|--------|---------|
| **orchestrator-mcp** | LangGraph workflow engine with SQLite checkpointing, quota reporting |
| **gemini-delegate** | Offloads bulk file reads, reviews, and analysis to free Gemini models |
| **mem0-mcp** | Persistent vector + graph memory (Qdrant / Neo4j / Ollama embeddings) |
| **langfuse-mcp** | Read-only observability analytics (no ingestion — hooks and proxy handle that) |
| **sequential-thinking** | Reflective reasoning for complex design problems |

## What You Get

After setup, your Claude Code sessions gain:

- **Automatic cost optimization** — routine work offloaded to free models
- **Structured workflows** — features, refactors, reviews, and SPDD pipelines follow repeatable state machines
- **Artifact-driven transparency** — plans, reviews, and status rendered as reviewable markdown files with inline feedback
- **Persistent memory** — decisions and patterns survive across sessions via mem0
- **Specialized agent roles** — the right model for each type of work
- **Full cost visibility** — 3 trace sources feed session-linked Langfuse dashboards
- **Velocity-based quota management** — call rate tracking with lockout risk assessment
- **Project-specific skills** — teachable patterns and conventions for your domain
- **Safe isolation** — implementation work runs in git worktrees to protect your main branch

## Prerequisites

The [AI Infrastructure](https://github.com/SpandrelInteractive/ai-infra) repo must be running:
- Docker services: Qdrant, Neo4j, Ollama, Langfuse, Langfuse-DB, OTEL Collector, OTEL Bridge
- Antigravity proxy v2 on localhost:1338 (managed by PM2)
- MCP servers installed: orchestrator-mcp, gemini-delegate, mem0-mcp, langfuse-mcp

## Quick Start

1. **Copy this folder** to your project root:
   ```bash
   cp -r claude_workspace /path/to/my-project
   ```

2. **Find and replace placeholders:**

   | Placeholder | Replace With | Example |
   |-------------|-------------|---------|
   | `{{PROJECT_NAME}}` | Human-readable project name | `My App` |
   | `{{PROJECT_ID}}` | Snake_case identifier (used as MEM0_APP_ID) | `my_app` |
   | `{{PROJECT_ROOT}}` | Absolute path to project | `/home/user/projects/my-app` |
   | `{{INFRA_PATH}}` | Path to ai-infra directory | `/home/user/projects/ai-infra` |
   | `{{LANGFUSE_PUBLIC_KEY}}` | From Langfuse UI → Settings → API Keys | `pk-lf-...` |
   | `{{LANGFUSE_SECRET_KEY}}` | From Langfuse UI → Settings → API Keys | `sk-lf-...` |

   ```bash
   # Example: replace all at once
   find . -type f \( -name '*.md' -o -name '*.json' -o -name '.envrc' \) | \
     xargs sed -i \
       -e 's|{{PROJECT_NAME}}|My App|g' \
       -e 's|{{PROJECT_ID}}|my_app|g' \
       -e 's|{{PROJECT_ROOT}}|/home/user/projects/my-app|g' \
       -e 's|{{INFRA_PATH}}|/home/user/projects/ai-infra|g' \
       -e 's|{{LANGFUSE_PUBLIC_KEY}}|pk-lf-...|g' \
       -e 's|{{LANGFUSE_SECRET_KEY}}|sk-lf-...|g'
   ```

3. **Create project skills:**
   ```bash
   mkdir -p .claude/skills/my_app-patterns .claude/skills/my_app-workflows
   cp .claude/skills/project-patterns.SKILL.md.template .claude/skills/my_app-patterns/SKILL.md
   cp .claude/skills/project-workflows.SKILL.md.template .claude/skills/my_app-workflows/SKILL.md
   # Edit both SKILL.md files with your project's domain knowledge
   ```

4. **Create project guide:**
   ```bash
   cp .claude/docs/project-guide.md.template .claude/docs/my_app-guide.md
   # Fill in domain entities, architecture rules, review checklist
   ```

5. **Activate environment:**
   ```bash
   direnv allow
   ```

6. **Create a Langfuse project** at http://localhost:3000 and paste the API keys into `.mcp.json`.

7. **Start Claude Code** and run:
   ```
   > refresh_index
   > add_memory("Project my_app: <brief description>")
   ```

## File Structure

```
├── CLAUDE.md                          # Main instructions (templatized)
├── .mcp.json                          # MCP server configuration (port 1338)
├── .envrc                             # direnv environment
├── .gitignore
├── .claude/
│   ├── settings.local.json            # 2 hook entries + MCP permissions
│   ├── artifacts/                     # Generated deliverables (plans, reviews, status)
│   ├── hooks/
│   │   ├── pre-tool-gate.py           # Consolidated PreToolUse (session, budget, model, delegation)
│   │   ├── post-tool-trace.py         # Consolidated PostToolUse (trace, throttle, artifacts, memory, docs)
│   │   └── lib/                       # Shared library (state.py, langfuse.py, decisions.py)
│   ├── docs/
│   │   ├── INDEX.md                   # Documentation index + framework overview
│   │   ├── usage-guide.md             # Practical framework reference
│   │   ├── architecture-overview.md   # System diagrams and data flows
│   │   ├── observability.md           # 3 trace sources, hooks, state files
│   │   ├── mcp-servers.md             # Server reference with tool docs
│   │   ├── workflows.md              # LangGraph state machines
│   │   ├── agent-roles.md             # Role definitions and escalation
│   │   ├── rate-limiting.md           # 4-layer quota strategy
│   │   ├── skills-guide.md            # Skills ecosystem
│   │   ├── artifacts.md               # Artifact lifecycle
│   │   ├── project-setup-guide.md     # End-to-end setup walkthrough
│   │   └── project-guide.md.template  # Template for project-specific guide
│   ├── tools/
│   │   ├── reset-mcps.sh             # MCP health check (--check) and reset
│   │   └── sync-mao.sh               # Sync framework updates from source project
│   └── skills/
│       ├── implementation-plan/SKILL.md
│       ├── walkthrough/SKILL.md
│       ├── README.md
│       ├── project-patterns.SKILL.md.template
│       └── project-workflows.SKILL.md.template
```

## Documentation

Detailed guides live in `.claude/docs/`. Start with [`INDEX.md`](.claude/docs/INDEX.md) for the full table of contents and framework overview.

| Guide | Contents |
|-------|----------|
| `INDEX.md` | Framework overview, architecture summary, documentation index |
| `usage-guide.md` | Routing cheat sheet, MCP tools, agent roles, common workflows, troubleshooting |
| `architecture-overview.md` | System diagrams, data flows, model selection flowchart |
| `observability.md` | 3 trace sources, 2 consolidated hooks, 3 state files, Langfuse setup |
| `mcp-servers.md` | All 5 servers with tool reference and configuration |
| `workflows.md` | LangGraph state machines and budget enforcement |
| `agent-roles.md` | 6 roles with model mappings and escalation paths |
| `rate-limiting.md` | 4-layer quota: proxy, orchestrator, cron, per-workflow |
| `skills-guide.md` | Skills ecosystem: discovery, creation, composition |
| `artifacts.md` | Artifact lifecycle: types, triggers, archival, feedback |
| `project-setup-guide.md` | End-to-end setup walkthrough |

## Cleanup After Setup

Once you've replaced all placeholders and created your skills, you can delete:
- `README.md` (this file)
- `.claude/skills/README.md`
- `.claude/skills/*.template`
- `.claude/docs/project-guide.md.template`

## Related

- **[AI Infrastructure](https://github.com/SpandrelInteractive/ai-infra)** — MCP servers, proxy, and Docker services that power this template.
