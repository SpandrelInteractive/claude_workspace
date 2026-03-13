# {{PROJECT_NAME}} — Claude Code Instructions

## Documentation

Framework guides live in `.claude/framework/docs/`. Project-specific guide lives in `.claude/docs/`.

- **Framework index:** [`.claude/framework/docs/INDEX.md`](.claude/framework/docs/INDEX.md)
- **Project guide:** `.claude/docs/{{PROJECT_ID}}-guide.md`

## CLI Tools

Scripts in `.claude/framework/tools/` are available for use via Bash.

| Tool | Usage |
|------|-------|
| `reset-mcps.sh` | Kill MCP server processes. **Killing removes tools for the rest of the session** — Claude Code does NOT auto-reconnect. Use `--check` to inspect health without killing. |

To pull framework updates: `git subtree pull --prefix=.claude/framework <mao-repo-path> main --squash`

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
- Three tracing sources feed Langfuse (http://localhost:3000):
  1. `post-tool-trace.py` hook — traces all Claude Code tool calls
  2. Proxy middleware (port 1338) — traces all Gemini API calls with token counts
  3. OTEL bridge — captures Claude API calls via OpenTelemetry
- All traces share `session_id` for cross-source correlation
- Check `get_quota_report` for velocity-based quota status

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
- **Conventions**: `.claude/docs/{{PROJECT_ID}}-guide.md` for current patterns and constraints
