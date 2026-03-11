# Skills Ecosystem Guide

## Overview

Skills are markdown files (SKILL.md) that teach Claude Code domain knowledge, workflows, and decision-making patterns. They use progressive disclosure — Claude loads them based on triggers and context.

## Skill Locations

| Location | Scope | Purpose |
|----------|-------|---------|
| `~/.claude/skills/` | Global (all projects) | Generic orchestration, routing, cost awareness |
| `<project>/.claude/skills/` | Project-specific | Domain patterns, project workflows |

## Generic Skills (Part 1)

### agent-orchestrator
**Path:** `~/.claude/skills/agent-orchestrator/SKILL.md`

Teaches Claude how to decompose tasks, select agent roles, and manage workflows.

**Key knowledge areas:**
- Task classification: implement / review / design / debug / test / document
- When to use each model tier with cost reasoning
- How to call orchestrator-mcp tools (`run_workflow`, `workflow_status`)
- How to interpret workflow results and execute Claude subagent instructions
- Budget awareness: check `get_quota_state` before expensive operations
- When to use worktree isolation (feature work, risky changes)
- When to engage sequential-thinking for design problems
- How to use Langfuse cost reports to optimize routing decisions

**Triggers:** Task decomposition, multi-step work, model selection questions

### skill-awareness
**Path:** `~/.claude/skills/skill-awareness/SKILL.md`

Teaches Claude about the skills ecosystem itself.

**Key knowledge areas:**
- How skills work (SKILL.md format, progressive disclosure, triggers)
- How to discover available skills in both global and project directories
- Community skill catalogs (anthropics/skills, awesome-claude-skills)
- How to compose multiple skills for complex tasks
- When to suggest creating new project-specific skills
- How to use skill-creator to build new skills

**Triggers:** "what skills exist", complex task requiring multiple capabilities

### tool-router
**Path:** `~/.claude/skills/tool-router/SKILL.md`

Decision tree for optimal tool usage across all MCP tools.

**Key knowledge areas:**
- Gemini delegation rules (file count thresholds, diff size thresholds)
- Model selection matrix (cheapest capable first)
- mem0 protocol: search before asking, store decisions, use graph for relationships
- Sequential thinking protocol: when to engage for design/architecture
- When to use `analyze_files` vs `Read` vs `Agent(Explore)`
- CronCreate patterns: quota monitoring, index refresh, session-start recreation
- Task management patterns: `TaskCreate` for multi-step work
- Langfuse logging protocol: what to trace, when to check costs

**Triggers:** Any tool selection decision, model choice

### quota-guard
**Path:** `~/.claude/skills/quota-guard/SKILL.md`

Always-active cost awareness skill.

**Key knowledge areas:**
- Model cost ranking with rationale
- Protocol: check `get_quota_state` before expensive operations
- Budget escalation: cheapest capable model → escalate on failure only
- Rate limit recovery patterns
- Daily/weekly cost targets
- Gemini-first strategy: "if Gemini can do it, Gemini does it"

**Triggers:** Always active (referenced from CLAUDE.md)

## Community Skills to Install

| Source | Skill | Purpose | Install Command |
|--------|-------|---------|-----------------|
| anthropics/skills | document-skills (xlsx, docx, pdf, pptx) | Office document handling | `claude skill install anthropics/skills/document-skills` |
| anthropics/skills | mcp-builder | Creating new MCP servers | `claude skill install anthropics/skills/mcp-builder` |
| anthropics/skills | webapp-testing | Web application testing | `claude skill install anthropics/skills/webapp-testing` |
| anthropics/skills | skill-creator | Building new skills | Already installed |
| obra/superpowers | TDD | Test-driven development | `claude skill install obra/superpowers/TDD` |
| obra/superpowers | debugging | Systematic debugging | `claude skill install obra/superpowers/debugging` |
| obra/superpowers | planning | Task planning | `claude skill install obra/superpowers/planning` |
| obra/superpowers | execute-plan | Plan execution | `claude skill install obra/superpowers/execute-plan` |

## Creating Project-Specific Skills (Part 2)

### Directory Structure
```
<project>/.claude/skills/
  <project>-patterns/
    SKILL.md               # Main skill file (entry point)
    entities.md            # Domain entity reference
    api-patterns.md        # API/service templates
    testing-patterns.md    # Test conventions
  <project>-workflows/
    SKILL.md               # Workflow skill entry point
    workflows.md           # Custom workflow definitions
```

### SKILL.md Format

```yaml
---
name: <skill-name>
description: <one-line description>
---
# <Skill Title>

## Overview
<What this skill teaches>

## <Knowledge Section 1>
<Content>

## <Knowledge Section 2>
<Content>
```

**Guidelines:**
- Keep SKILL.md under 500 lines — use linked files for details
- Include concrete examples, not just rules
- Use decision trees for routing logic
- Reference specific file paths in the project
- Update when project conventions change

## Skill Composition Patterns

### Sequential Composition
For tasks that need multiple skills in order:
1. `tool-router` → decide which tools/models
2. `agent-orchestrator` → decompose and delegate
3. `<project>-patterns` → apply domain conventions

### Parallel Composition
For tasks where multiple skills inform simultaneously:
- `quota-guard` (always active) + `tool-router` (per decision) + `agent-orchestrator` (task management)

### Escalation Pattern
When a skill's guidance is insufficient:
1. Try `<project>-patterns` for domain-specific answer
2. Escalate to `skill-awareness` to find other relevant skills
3. Escalate to `agent-orchestrator` to delegate to appropriate agent role
