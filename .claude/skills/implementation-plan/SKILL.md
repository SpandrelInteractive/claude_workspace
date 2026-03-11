# Implementation Plan

Generate a structured implementation plan artifact before writing code.

**Trigger**: User invokes `/implementation-plan` or asks to plan an implementation.

## Instructions

When this skill is invoked, generate a structured implementation plan and write it to `.claude/artifacts/implementation_plan.md`.

### Steps

1. **Understand the goal**:
   - Read the user's description of what needs to be implemented
   - If files are mentioned, read them to understand current state
   - Search mem0 for relevant prior decisions: `mcp__mem0__search_memories`

2. **Analyze the codebase**:
   - Use `mcp__gemini__analyze_files` if 3+ files need reading
   - Identify all files that need to change
   - Map dependencies between changes

3. **Draft the plan**:
   - Determine the high-level approach
   - List all file changes (create/modify/delete) with descriptions
   - Define a test strategy
   - Identify risks

4. **Write the artifact** to `.claude/artifacts/implementation_plan.md` using this format:

```markdown
# Implementation Plan

> **Created:** {date}
> **Goal:** {one-line summary}

## Approach

{2-3 sentences describing the high-level strategy}

## File Changes

| Action | File | Description |
|--------|------|-------------|
| + create | `path/to/new.py` | New module for X |
| ~ modify | `path/to/existing.py` | Add Y to support Z |
| - delete | `path/to/old.py` | No longer needed after X |

## Test Strategy

{How to verify the changes work — specific commands, test files, manual checks}

## Risks

- {Risk 1 and mitigation}
- {Risk 2 and mitigation}

## Dependencies

{Order of operations — what must be done first}

---

<!-- Leave feedback below this line — the agent will incorporate it -->
```

5. **Archive previous plan**: If `.claude/artifacts/implementation_plan.md` already exists, move it to `.claude/artifacts/archive/` with a timestamp suffix before writing the new one.

6. **Auto-open in editor**: After writing, run `codium --reuse-window .claude/artifacts/implementation_plan.md` via Bash.

### Feedback integration

Before generating the plan, check if an existing `implementation_plan.md` has feedback comments below the `<!-- Leave feedback -->` marker. If it does, incorporate that feedback into the new plan.

### Guidelines

- Keep the plan actionable — every file change should be specific enough to execute
- Include line numbers or function names where relevant
- The test strategy should have concrete commands (e.g., `pytest tests/test_foo.py -v`)
- Risks should include mitigations, not just problems
- Don't over-plan — if the task is simple (1-2 files), keep the plan concise
