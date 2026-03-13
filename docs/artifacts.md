# Artifact System

## Overview

Artifacts are structured markdown deliverables that agents generate at key workflow phases to communicate progress, plans, and results. Inspired by Google Antigravity's artifact system, they solve the "trust gap" by replacing raw tool call logs with human-readable, reviewable documents.

## Artifact Types

| Artifact | File | When Generated | Source |
|----------|------|----------------|--------|
| Task List | `tasks.md` | On Task* tool calls | PostToolUse hook |
| Task Plan | `task_plan.md` | After workflow planning phase | orchestrator-mcp `plan` node |
| Implementation Plan | `implementation_plan.md` | After refactor planning or `/implementation-plan` | orchestrator-mcp or skill |
| Review Result | `review_result.md` | After review workflow completes | orchestrator-mcp `summarize` node |
| Workflow Status | `workflow_status.md` | On every workflow state change | orchestrator-mcp + PostToolUse hook |
| Walkthrough | `walkthrough.md` | User invokes `/walkthrough` | Skill |

## Architecture

### Two-Layer Generation

Artifacts are generated from two complementary layers:

1. **Orchestrator-mcp (in-process):** Workflow nodes call `artifacts.py` renderers directly during execution. This is the primary path — artifacts are generated as structured data flows through the workflow.

2. **PostToolUse hooks (Claude Code side):** Hooks trigger on MCP tool responses and write artifacts from the response data. This handles cases where the orchestrator can't write files (permissions, env vars) and provides a fallback.

### File Layout

```
.claude/artifacts/
├── tasks.md              # Live task list (auto-updated by hook)
├── task_plan.md           # Current task decomposition
├── implementation_plan.md # Current implementation plan
├── review_result.md       # Latest review result
├── workflow_status.md     # Current workflow progress
├── walkthrough.md         # Post-work summary (via skill)
└── archive/               # Timestamped previous versions
    ├── task_plan_20260311T153000.md
    └── implementation_plan_20260311T160000.md
```

### Lifecycle

1. **Generation:** Artifact is created by a workflow node or skill
2. **Archival:** If a previous version exists, it's moved to `archive/` with a timestamp suffix
3. **Review:** User can read the artifact and leave feedback below the `<!-- Leave feedback -->` marker
4. **Incorporation:** On next generation, feedback is read and incorporated (implementation-plan skill)
5. **Auto-open:** New artifacts are opened in VSCodium automatically

## Hooks

### update-task-artifact.py
- **Triggers on:** `Task*` tool calls
- **Writes:** `tasks.md`
- **Behavior:** Maintains JSON state in `.tasks-state.json`, renders markdown with status icons

### update-workflow-artifact.py
- **Triggers on:** `mcp__orchestrator__run_workflow`, `mcp__orchestrator__workflow_status`
- **Writes:** `workflow_status.md`
- **Behavior:** Parses workflow response JSON, renders status with completed steps

## Renderers (orchestrator-mcp/artifacts.py)

| Function | Output | Input |
|----------|--------|-------|
| `render_task_plan()` | Task decomposition table | `TaskDecomposition` schema |
| `render_implementation_plan()` | File change table + approach | `ImplementationPlan` schema |
| `render_review_result()` | Findings grouped by severity | `ReviewResult` schema |
| `render_workflow_status()` | Compact progress view | `WorkflowState` dict |

## Skills

### /implementation-plan
Manually generate an implementation plan artifact outside of workflow context. Reads codebase, drafts plan, writes to `.claude/artifacts/implementation_plan.md`.

### /walkthrough
Generate a post-work summary. Reads git diff, task artifact, and workflow status to produce `.claude/artifacts/walkthrough.md`.

## Feedback System

All artifacts include a feedback marker at the bottom:

```markdown
---

<!-- Leave feedback below this line — the agent will incorporate it -->
```

Users can add comments below this marker. The `/implementation-plan` skill checks for existing feedback before regenerating. This mirrors Antigravity's Google Docs-style annotation system.

## Configuration

Hooks are registered in `.claude/settings.local.json` under `hooks.PostToolUse`. The orchestrator-mcp resolves the artifact directory via the `CLAUDE_PROJECT_DIR` environment variable.
