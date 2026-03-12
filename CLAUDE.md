# {{PROJECT_NAME}} — Claude Code Instructions

## Documentation

Detailed guides live in `.claude/docs/`. Read them before asking the user for context.

| Guide | Contents |
|-------|----------|
| `usage-guide.md` | Generic framework: MCP servers, agent roles, routing, cost optimization, troubleshooting |
| `{{PROJECT_ID}}-guide.md` | Project-specific: domain entities, architecture rules, workflows, review checklist |
| `project-setup-guide.md` | How to set up a new project instance from scratch |
| `architecture-overview.md` | System diagrams and component interactions |
| `agent-roles.md` | Role definitions and escalation paths |
| `mcp-servers.md` | MCP server internals and configuration |
| `workflows.md` | LangGraph workflow state machines |
| `observability.md` | Langfuse tracing and hooks |
| `skills-guide.md` | Skills ecosystem and creation |
| `rate-limiting.md` | Budget caps and rate limit strategy |
| `artifacts.md` | Artifact system: types, lifecycle, hooks, renderers |

## CLI Tools

Scripts in `.claude/tools/` are available for use via Bash.

| Tool | Usage |
|------|-------|
| `reset-mcps.sh` | Kill MCP server processes so Claude Code auto-restarts them. Run `.claude/tools/reset-mcps.sh` to reset all, or `.claude/tools/reset-mcps.sh mem0 gemini` for specific servers. Use when an MCP server is unresponsive or returning errors. |

## Memory Protocol

- **PROHIBITED**: Never use the `Write` tool to modify `.claude/projects/*/MEMORY.md`.
- **MANDATORY**: Use the `mem0` MCP server for all persistent data.
- **STORAGE**: All project facts, architecture decisions, and business logic must be saved via `add_memory`.
- **RECALL**: Always check `search_memories` before asking the user for project-specific context.
- **NAMESPACE**: `MEM0_APP_ID={{PROJECT_ID}}` (managed via direnv).
- **LLM**: Fact extraction is routed through the local proxy to `gemini-2.5-flash-lite`.

## Gemini Delegation Rules

Route work to the `gemini` MCP tools to save Claude quota. These rules are **mandatory**.

```
Need to read files?
  ├─ 1-2 files → Read tool
  └─ 3+ files → analyze_files
Need to review changes?
  ├─ <50 lines → inline
  └─ 50+ lines → review_diff
Need project orientation?
  └─ explain_architecture
Need to reason without tools?
  └─ ask_gemini
After major code changes?
  └─ refresh_index
```

## Agent Orchestration Protocol

### Role Activation
- You are the **Orchestrator** role by default
- Delegate to other roles via Agent tool or orchestrator-mcp workflows
- Always check quota before spawning expensive subagents: `get_quota_state`

### Model Selection (Claude primary, Gemini for large context)
**Claude (primary — runs via Claude Code Agent tool):**
1. Haiku 4.5 — classify, index, document, quick fixes, boilerplate
2. Sonnet 4.6 — implement, test, refactor, review, research
3. Opus 4.6 — design, debug, architecture sign-off, ambiguous problems

**Gemini (large-context fallback only — runs via proxy):**
4. Gemini 2.5 Flash Lite — bulk indexing, memory extraction, classification
5. Gemini 3 Flash — bulk file reads, large code analysis
6. Gemini 3.1 Pro — long-context analysis when Claude context is insufficient

### Observability
- All workflow executions are traced in Langfuse (http://localhost:3000)
- Check `get_cost_report` periodically to optimize routing
- PostToolUse hook logs MCP calls automatically

### Memory Protocol
- search_memories BEFORE asking user for project context
- store workflow outcomes, architectural decisions, patterns in mem0
- Use graph queries (search_graph, get_entity) for relational questions
- Consolidate/prune memories periodically via cron

### Artifact Protocol
- Workflows auto-generate artifacts at phase transitions (see `artifacts.md`)
- Use `/implementation-plan` before complex implementations
- Use `/walkthrough` after completing significant work
- Artifacts live in `.claude/artifacts/` — previous versions auto-archived
- Check for user feedback below `<!-- Leave feedback -->` markers before regenerating

### Workflow Protocol
- Multi-step tasks → `run_workflow` from orchestrator-mcp
- Single-step delegation → Agent tool with model param
- Design problems → engage sequential-thinking MCP first
- Recreate CronCreate jobs at session start (3-day expiry)

## Project Agent Roles

<!-- Customize these for your project -->

### Implementer additions
- Skills: `{{PROJECT_ID}}-patterns`
- Conventions: <!-- e.g., DDD layers, CQRS, specific framework patterns -->
- Stack: <!-- e.g., ASP.NET Core 10, C#, EF Core -->

### Reviewer additions
- Checklist: <!-- e.g., layer violations, ORM anti-patterns, security issues -->
- Skills: `{{PROJECT_ID}}-patterns`

### Architect additions
- Skills: `{{PROJECT_ID}}-patterns`
- Reference: `docs/PRD.md`, `docs/TDD.md`, `docs/ADRs/`
- Workflows: `{{PROJECT_ID}}-workflows`

## Development Rules

<!-- Populate with project-specific coding standards when available. Until then, point to docs: -->

Development rules and coding standards will be finalized with input from the client. Until then, follow:

- **Architecture**: `docs/TDD.md` and `docs/ADRs/` for technical decisions
- **Requirements**: `docs/PRD.md` for business rules and feature scope
- **Gaps**: `docs/gap-assessment.md` for known unknowns and open questions
- **Conventions**: `.claude/docs/{{PROJECT_ID}}-guide.md` for current patterns and constraints
