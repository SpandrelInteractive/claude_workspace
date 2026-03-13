# Walkthrough

Generate a post-work summary artifact after completing a task or set of changes.

**Trigger**: User invokes `/walkthrough` or asks for a summary of completed work.

## Instructions

When this skill is invoked, generate a structured walkthrough and write it to `.claude/artifacts/walkthrough.md`.

### Steps

1. **Gather context**:
   - Run `git diff main...HEAD --stat` to see all changed files since the branch diverged (or `git diff HEAD~5...HEAD --stat` on main)
   - Run `git log --oneline -10` to see recent commits
   - Read the task artifact at `.claude/artifacts/tasks.md` if it exists
   - Check orchestrator workflow status via `mcp__orchestrator__list_workflows` if available

2. **Analyze changes**:
   - For each changed file, briefly describe what changed and why
   - Group related changes into logical sections
   - Identify any architectural decisions made

3. **Write the walkthrough** to `.claude/artifacts/walkthrough.md` using this format:

```markdown
# Walkthrough — {date}

> {one-line summary of what was accomplished}

## Changes

### {Section Name}
| File | Change | Why |
|------|--------|-----|
| `path/to/file.py` | Added X | To support Y |

### {Section Name}
...

## Decisions
- {Any architectural or design decisions made, with rationale}

## Verification
- [ ] {Step to verify change 1 works}
- [ ] {Step to verify change 2 works}

## Workflows
{If orchestrator workflows were run, summarize their status and outcomes}

## Next Steps
- {Any follow-up work identified during this session}
```

4. **Auto-open in editor**: After writing the file, run `codium --reuse-window .claude/artifacts/walkthrough.md` via Bash to open it in VSCodium.

### Multi-agent awareness

- If subagents were spawned, include a section noting which agents contributed and what they did
- Check task artifact for agent attribution (`agent:XXXX` tags)
- Include orchestrator workflow outcomes if any ran during the session

### Guidelines

- Keep it concise — focus on the "what" and "why", not the "how"
- Link to specific files with line numbers where relevant
- The verification checklist should be actionable steps the user can follow
- Don't include trivial changes (formatting, imports) unless they're the main point
