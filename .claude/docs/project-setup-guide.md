# Project Setup Guide

## Overview

This guide explains how to instantiate Part 2 (project customization) for any project using the Part 1 generic framework.

## Prerequisites

Before setting up a project, ensure Part 1 is operational:

- [ ] Docker services running: Qdrant, Neo4j, Ollama, Langfuse, Langfuse-DB
- [ ] antigravity-proxy v2 running on localhost:1338 (managed by PM2)
- [ ] MCP servers installed: orchestrator-mcp, gemini-delegate, mem0-mcp, langfuse-mcp
- [ ] Generic skills installed in `~/.claude/skills/`
- [ ] Hooks installed in `~/.claude/hooks/`
- [ ] sequential-thinking MCP available via npx

## Step-by-Step Setup

### 1. Initialize Project Directory

```bash
# Create Claude Code project structure
mkdir -p <project>/.claude/skills/<project>-patterns
mkdir -p <project>/.claude/skills/<project>-workflows
mkdir -p <project>/.claude/skills/implementation-plan
mkdir -p <project>/.claude/skills/walkthrough
mkdir -p <project>/.claude/docs
mkdir -p <project>/.claude/hooks
mkdir -p <project>/.claude/artifacts
```

### 2. Configure MCP Servers

Create `<project>/.mcp.json`:

```json
{
  "mcpServers": {
    "mem0": {
      "command": "uv",
      "args": ["run", "--directory", "/home/tohigu/projects/ai-infra/mem0-mcp", "mem0-mcp"],
      "env": {
        "MEM0_APP_ID": "<project-id>",
        "ANTHROPIC_BASE_URL": "http://localhost:1338",
        "ANTHROPIC_API_KEY": "dummy-key",
        "MEM0_ENABLE_GRAPH": "true"
      }
    },
    "gemini": {
      "command": "uv",
      "args": ["run", "--directory", "/home/tohigu/projects/ai-infra/gemini-delegate", "gemini-delegate"],
      "env": {
        "PROJECT_ROOT": "<project-absolute-path>",
        "ANTHROPIC_BASE_URL": "http://localhost:1338",
        "ANTHROPIC_API_KEY": "dummy-key",
        "GEMINI_PRO_MODEL": "gemini-3-flash",
        "GEMINI_FLASH_MODEL": "gemini-2.5-flash-lite"
      }
    },
    "orchestrator": {
      "command": "uv",
      "args": ["run", "--directory", "/home/tohigu/projects/ai-infra/orchestrator-mcp", "orchestrator-mcp"],
      "env": {
        "ANTHROPIC_BASE_URL": "http://localhost:1338",
        "ANTHROPIC_API_KEY": "dummy-key",
        "LANGFUSE_HOST": "http://localhost:3000",
        "LANGFUSE_PUBLIC_KEY": "<key>",
        "LANGFUSE_SECRET_KEY": "<key>"
      }
    },
    "langfuse": {
      "command": "uv",
      "args": ["run", "--directory", "/home/tohigu/projects/ai-infra/langfuse-mcp", "langfuse-mcp"],
      "env": {
        "LANGFUSE_HOST": "http://localhost:3000",
        "LANGFUSE_PUBLIC_KEY": "<key>",
        "LANGFUSE_SECRET_KEY": "<key>"
      }
    },
    "sequential-thinking": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"]
    }
  }
}
```

### 3. Configure Environment

Create `<project>/.envrc`:
```bash
export MEM0_APP_ID="<project-id>"
```

Run `direnv allow`.

### 4. Create Project Skills

#### <project>-patterns/SKILL.md

Copy from `~/.claude/templates/project-skills/SKILL.md.template` and customize:

```yaml
---
name: <project>-patterns
description: Domain patterns, entity reference, and coding conventions for <project>
---
# <Project> Development Patterns

## Entities
[Define domain entities, their relationships, and validation rules]

## Architecture Conventions
[DDD layers, naming conventions, folder structure]

## API Patterns
[Endpoint conventions, request/response templates]

## Testing Conventions
[Test structure, fixtures, mocking patterns]
```

#### <project>-workflows/SKILL.md

Copy from `~/.claude/templates/project-workflows/workflows.md.template`:

```yaml
---
name: <project>-workflows
description: Project-specific workflow definitions for <project>
---
# <Project> Workflows

## Custom Workflow Types
[Define project-specific workflow types]

## Entity Conventions
[How new entities are created in this project]
```

### 5. Update CLAUDE.md

Add the orchestration section to your project's CLAUDE.md. Copy the generic section from `~/.claude/templates/CLAUDE-orchestration.md.template` and add project-specific customizations:

```markdown
## Agent Orchestration Protocol
[Generic section from template]

## Project Agent Roles
### Implementer additions
- Skills: `<project>-patterns`
- Conventions: [project-specific standards]

### Reviewer additions
- Checklist: [project-specific review criteria]

### Architect additions
- Skills: `<project>-patterns`
- Reference: [paths to ADRs, PRD, TDD]
```

### 6. Install Hooks and Skills

Copy the consolidated hooks and shared library from the workspace template:

```bash
# Hooks — 2 consolidated hooks + shared library
cp claude_workspace/.claude/hooks/pre-tool-gate.py <project>/.claude/hooks/
cp claude_workspace/.claude/hooks/post-tool-trace.py <project>/.claude/hooks/
cp -r claude_workspace/.claude/hooks/lib/ <project>/.claude/hooks/lib/
chmod +x <project>/.claude/hooks/*.py

# Skills — user-invokable artifact generators
cp claude_workspace/.claude/skills/implementation-plan/SKILL.md <project>/.claude/skills/implementation-plan/
cp claude_workspace/.claude/skills/walkthrough/SKILL.md <project>/.claude/skills/walkthrough/
```

The hooks handle all automation:
- **pre-tool-gate.py** — Session gate, budget enforcement, model selection, Gemini delegation
- **post-tool-trace.py** — Langfuse tracing, throttle tracking, task/workflow artifacts, memory queue, doc staleness

Auto-generated artifacts:
- `tasks.md` — Live task list (on `Task*` tool calls)
- `workflow_status.md` — Workflow progress (on `run_workflow`/`workflow_status` calls)

The orchestrator-mcp also generates artifacts directly at workflow phase transitions:
- `task_plan.md` — After planning phase
- `implementation_plan.md` — After refactor planning
- `review_result.md` — After review completes

### 7. Update Settings

Create `<project>/.claude/settings.local.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": ".*",
        "hooks": [{ "type": "command", "command": "python3 .claude/hooks/pre-tool-gate.py", "timeout": 2000 }]
      }
    ],
    "PostToolUse": [
      {
        "matcher": ".*",
        "hooks": [{ "type": "command", "command": "python3 .claude/hooks/post-tool-trace.py", "timeout": 5000 }]
      }
    ]
  },
  "permissions": {
    "allow": [
      "mcp__mem0__search_memories",
      "mcp__mem0__add_memory",
      "mcp__mem0__list_memories",
      "mcp__mem0__delete_memory",
      "mcp__mem0__search_graph",
      "mcp__mem0__get_entity",
      "mcp__gemini__analyze_files",
      "mcp__gemini__review_diff",
      "mcp__gemini__explain_architecture",
      "mcp__gemini__refresh_index",
      "mcp__gemini__ask_gemini",
      "mcp__orchestrator__validate_system",
      "mcp__orchestrator__init_session",
      "mcp__orchestrator__run_workflow",
      "mcp__orchestrator__workflow_status",
      "mcp__orchestrator__list_workflows",
      "mcp__orchestrator__cancel_workflow",
      "mcp__orchestrator__get_quota_state",
      "mcp__orchestrator__get_quota_report",
      "mcp__orchestrator__optimize_prompts",
      "mcp__langfuse__get_cost_report",
      "mcp__langfuse__get_agent_performance",
      "mcp__langfuse__get_traces",
      "mcp__langfuse__get_session_summary"
    ]
  },
  "enableAllProjectMcpServers": true,
  "enabledMcpjsonServers": ["mem0", "gemini", "orchestrator", "langfuse", "sequential-thinking"]
}
```

### 8. Build Initial Index

```bash
# Start Claude Code in the project
claude

# First session: build index and seed memory
> refresh_index  # via gemini-delegate
> # Add key project facts to mem0
```

### 9. Seed Knowledge Graph (Optional)

If the project has well-defined entity relationships:
```
> add_memory("Entity Contract has relationship 'contains' with RemittanceDetail")
> add_memory("Entity Company has relationship 'submits' with Remittance")
```

These will be stored in both vector (Qdrant) and graph (Neo4j) stores.

### 10. Verify Setup

Checklist:
- [ ] `search_memories("project architecture")` returns results
- [ ] `analyze_files` works with project files
- [ ] `explain_architecture` returns project overview
- [ ] `run_workflow("review", "test review")` creates a workflow and generates `workflow_status.md`
- [ ] `.claude/artifacts/` directory has generated files
- [ ] `get_quota_state` returns model availability
- [ ] Langfuse UI shows traces at localhost:3000

## Example: union_dev Instantiation (Deferred)

When union_dev docs are finalized:

1. **Entities:** Contract, Remittance, RemittanceDetail, Company, Member, User
2. **Architecture:** ASP.NET Core 10, C#, DDD (Core/CoreApp/CoreData), Razor Pages, EF Core
3. **Skills:** C# patterns, Minimal API + CQRS, Azure conventions
4. **Workflows:** new-entity, new-razor-page, new-api-endpoint, remittance-processing
5. **Knowledge graph:** Entity relationships seeded from TDD
6. **Review checklist:** DDD layer violations, EF Core anti-patterns, Azure security

## Maintenance

### Regular Tasks
- Update project skills when conventions change
- Refresh index after major code changes
- Review mem0 memories for staleness (monthly)
- Check Langfuse cost reports and adjust routing

### Troubleshooting
- **MCP server not connecting:** Check `uv run` path and env vars in .mcp.json
- **mem0 search returns nothing:** Verify MEM0_APP_ID matches in .envrc and .mcp.json
- **Gemini calls failing:** Check proxy status at localhost:1338/health
- **Langfuse empty:** Verify API keys, check hook is registered in settings
