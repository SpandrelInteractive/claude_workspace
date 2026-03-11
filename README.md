# Claude Workspace Template

A production-ready template for building **multi-agent AI orchestration systems** on top of Claude Code. It provides the infrastructure, agent roles, workflow engine, memory system, and cost optimization layer needed to run complex software engineering tasks across multiple AI models — while keeping costs under control.

## What This Is

Claude Code is powerful on its own, but large projects quickly run into three problems: **cost explosion** from defaulting to expensive models, **context fragmentation** across sessions, and **lack of structure** for multi-step tasks. This template solves all three.

It wraps Claude Code in an orchestration layer that:

- **Routes work to the cheapest capable model.** A tiered system tries free Gemini models first (Flash Lite → Flash → Pro), then escalates to paid Claude models (Haiku → Sonnet → Opus) only when necessary. Most routine work — file analysis, code review, indexing — never touches Claude at all.
- **Decomposes tasks into managed workflows.** Multi-step work (features, refactors, reviews) runs through a LangGraph state machine with checkpointing, budget enforcement, and human-in-the-loop approval at cost thresholds.
- **Remembers context across sessions.** A dual-store memory system (Qdrant for vector similarity, Neo4j for relationship graphs) persists architectural decisions, domain knowledge, and patterns so you never re-explain your project.
- **Provides full observability.** Every tool call, token usage, and dollar spent is traced through Langfuse, giving you a dashboard view of where your AI budget goes.

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

When you ask for something like "add an Order entity with line items," the Orchestrator decomposes it into a workflow: design → implement domain model → add persistence → create API → write tests → review. Each step routes to the appropriate role and model. A $2.00 budget cap on the workflow prevents runaway costs, and the system pauses for approval if it would exceed the limit.

Five **MCP servers** handle the infrastructure:

| Server | Purpose |
|--------|---------|
| **orchestrator-mcp** | LangGraph workflow engine with SQLite checkpointing |
| **gemini-delegate** | Offloads bulk file reads, reviews, and analysis to free Gemini models |
| **mem0-mcp** | Persistent vector + graph memory (Qdrant / Neo4j / Ollama embeddings) |
| **langfuse-mcp** | Observability bridge for cost tracking and metrics |
| **sequential-thinking** | Reflective reasoning for complex design problems |

Rate limiting operates at four layers: per-model token caps, per-workflow budgets, session-level spend limits, and monthly quotas — all enforced automatically.

## What You Get

After setup, your Claude Code sessions gain:

- **Automatic cost optimization** — routine work offloaded to free models
- **Structured workflows** — features, refactors, and reviews follow repeatable state machines
- **Persistent memory** — decisions and patterns survive across sessions
- **Specialized agent roles** — the right model for each type of work
- **Full cost visibility** — Langfuse dashboard shows exactly where money goes
- **Project-specific skills** — teachable patterns and conventions for your domain
- **Safe isolation** — implementation work runs in git worktrees to protect your main branch

## Prerequisites

Part 1 infrastructure must be running:
- Docker services: Qdrant, Neo4j, Ollama, Langfuse, Langfuse-DB
- antigravity-claude-proxy on localhost:1337
- MCP servers installed: orchestrator-mcp, gemini-delegate, mem0-mcp, langfuse-mcp
- Generic skills in `~/.claude/skills/`
- Hooks in `~/.claude/hooks/`

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
   find . -type f -name '*.md' -o -name '*.json' -o -name '.envrc' | \
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
├── .mcp.json                          # MCP server configuration
├── .envrc                             # direnv environment
├── .gitignore                         # Standard ignores + .gemini-index
├── .claude/
│   ├── settings.local.json            # MCP permissions
│   ├── docs/
│   │   ├── usage-guide.md             # Generic framework guide
│   │   ├── project-guide.md.template  # Template for project-specific guide
│   │   ├── project-setup-guide.md     # Full setup walkthrough
│   │   ├── architecture-overview.md   # System diagrams
│   │   ├── agent-roles.md             # Role definitions
│   │   ├── mcp-servers.md             # Server reference
│   │   ├── workflows.md               # Workflow state machines
│   │   ├── observability.md           # Langfuse + hooks
│   │   ├── skills-guide.md            # Skills ecosystem
│   │   └── rate-limiting.md           # Budget strategy
│   └── skills/
│       ├── README.md                  # Skills setup instructions
│       ├── project-patterns.SKILL.md.template
│       └── project-workflows.SKILL.md.template
```

## Documentation

Detailed guides live in `.claude/docs/`:

| Guide | Contents |
|-------|----------|
| `usage-guide.md` | Full framework reference: MCP servers, agent roles, routing, cost optimization |
| `architecture-overview.md` | System diagrams and component interactions |
| `agent-roles.md` | Role definitions, model mappings, and escalation paths |
| `mcp-servers.md` | MCP server internals and configuration |
| `workflows.md` | LangGraph workflow state machines and budget enforcement |
| `observability.md` | Langfuse tracing, hooks, and cost dashboards |
| `skills-guide.md` | Skills ecosystem: discovery, creation, and composition |
| `rate-limiting.md` | 4-layer budget caps and rate limit strategy |
| `project-setup-guide.md` | End-to-end setup walkthrough |

## Cleanup After Setup

Once you've replaced all placeholders and created your skills, you can delete:
- `README.md` (this file)
- `.claude/skills/README.md`
- `.claude/skills/*.template`
- `.claude/docs/project-guide.md.template`
