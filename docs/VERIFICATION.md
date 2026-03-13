# MAO Framework — Verification Routine

**Purpose:** Comprehensive user-centered testing of every MAO framework capability.
**When to run:** After framework updates, infrastructure changes, or new project deployment.
**Duration:** ~30 minutes for full suite, ~10 minutes for smoke test (V-1 through V-3).

---

## Prerequisites

Before starting, ensure infrastructure is running:

```bash
# Docker services
docker compose -f /path/to/ai-infra/docker-compose.yml up -d

# Proxy
pm2 status antigravity-v2  # should show "online"

# Ollama
curl -s http://localhost:11434/api/tags | head -5  # should respond
```

---

## V-1: Infrastructure Health (SMOKE)

**Tests:** FR-1.1 (service validation), proxy, Docker services

```bash
# V-1.1: Proxy responds
curl -s http://localhost:1338/health | python3 -c "import sys,json; d=json.load(sys.stdin); print('PASS' if d['status']=='ok' else 'FAIL')"

# V-1.2: Proxy velocity endpoint works
curl -s http://localhost:1338/velocity | python3 -c "import sys,json; d=json.load(sys.stdin); print('PASS' if '5min' in d else 'FAIL')"

# V-1.3: Qdrant responds
curl -s http://localhost:6333/collections | python3 -c "import sys,json; json.load(sys.stdin); print('PASS')"

# V-1.4: Langfuse responds
curl -s http://localhost:3000 -o /dev/null -w "%{http_code}" | grep -q '200\|301\|302' && echo PASS || echo FAIL

# V-1.5: Ollama responds
curl -s http://localhost:11434/api/tags | python3 -c "import sys,json; json.load(sys.stdin); print('PASS')"

# V-1.6: OTEL collector running
docker ps --format '{{.Names}}' | grep -q otel-collector && echo PASS || echo FAIL

# V-1.7: OTEL bridge running
docker ps --format '{{.Names}}' | grep -q otel-bridge && echo PASS || echo FAIL

# V-1.8: PM2 proxy healthy
pm2 show antigravity-v2 --no-color 2>&1 | grep -q 'online' && echo PASS || echo FAIL
```

**Expected:** All 8 PASS

---

## V-2: Session Management (SMOKE)

**Tests:** FR-1.1, FR-1.2, FR-1.3

Start a fresh Claude Code session, then:

### V-2.1: Session gate blocks before init
```
> Run any tool (e.g., search_memories)
```
**Expected:** Blocked with message containing "init_session"

### V-2.2: init_session succeeds
```
> Call init_session
```
**Expected:** Returns `{status: "ready"}` with all 4 services showing `status: "ok"`

### V-2.3: Session breadcrumb written
```bash
cat .claude/artifacts/.session-validated
```
**Expected:** Contains today's date and `"validated": true`

### V-2.4: Session ID written
```bash
cat ~/.claude-session-id
```
**Expected:** Contains a UUID (e.g., `136e3643-cd95-4bff-8c1f-f08db7eeb585`)

### V-2.5: Tools unblocked after init
```
> Call search_memories("test")
```
**Expected:** Returns results (or empty list), NOT a session gate block

### V-2.6: Memory queue consumed
If a prior session left pending memory saves:
**Expected:** init_session response includes `memory_queue.consumed > 0` with entries

---

## V-3: Observability — Three Sources (SMOKE)

**Tests:** FR-5.1, FR-5.2, FR-5.3, FR-5.4

### V-3.1: Hook traces appear in Langfuse
```
> Call any tool (e.g., ask_gemini("Say hello"))
> Then call get_session_summary()
```
**Expected:** Session summary shows `posttooluse-hook` source with trace count > 0

### V-3.2: Proxy traces appear in Langfuse
After V-3.1 (which called ask_gemini through the proxy):
**Expected:** Session summary shows `proxy-middleware` source with trace count > 0

### V-3.3: OTEL traces appear in Langfuse
```bash
docker logs ai-infra-otel-bridge-1 --tail 3
```
**Expected:** Shows "Forwarded N events" (may be 0 if no Claude API calls yet — that's OK, just verify the bridge is watching)

### V-3.4: All sources share session_id
```
> Call get_session_summary()
```
**Expected:** Single session_id groups traces from multiple sources

### V-3.5: Cost report returns real data
```
> Call get_cost_report("1h")
```
**Expected:** Returns `total_traces > 0`, breakdown by source

### V-3.6: Quota report returns velocity data
```
> Call get_quota_report()
```
**Expected:** Returns velocity (5min/1hr/24hr), model_limits, session_budget, risk level

---

## V-4: Model Routing & Budget Enforcement

**Tests:** FR-2.1, FR-2.2, FR-2.3, FR-2.4

### V-4.1: Gemini delegation suggestion
```
> Read 5 different .py source files (not config files)
> Read a 6th .py file
```
**Expected:** On the 5th+ read, a suggestion appears to use `analyze_files` instead

### V-4.2: Model gate blocks expensive models on cheap tasks
```
> Use Agent tool with model: opus, subagent_type: Explore
```
**Expected:** Blocked with suggestion to use a cheaper model

### V-4.3: Throttle gate enforces budget (requires SESSION_BUDGET=low)
Set `SESSION_BUDGET=low` in .envrc, restart Claude Code:
```
> Spawn 2 Opus Agent calls
```
**Expected:** First call succeeds, second is blocked (low profile: max 1 opus)

### V-4.4: Throttle counters increment
```bash
cat .claude/artifacts/.session-state.json | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['throttle'])"
```
**Expected:** Counters reflect the Agent calls made in this session

### V-4.5: Blocked calls counted
After V-4.3:
**Expected:** `blocked_calls > 0` in throttle state

---

## V-5: Persistent Memory

**Tests:** FR-3.1, FR-3.2, FR-3.3

### V-5.1: Store and retrieve memory
```
> add_memory("MAO verification test: timestamp XXXX")
> search_memories("MAO verification test")
```
**Expected:** The stored memory appears in search results with high score

### V-5.2: Graph relationships created
```
> add_memory("Entity User has relationship manages with Entity Project")
> search_graph("User")
```
**Expected:** Returns graph edges showing User→manages→Project

### V-5.3: Memory namespace isolation
```
> list_memories()
```
**Expected:** Only memories for the current MEM0_APP_ID are shown, not from other projects

### V-5.4: Delete memory
```
> Note the memory_id from V-5.1
> delete_memory("<id>")
> search_memories("MAO verification test")
```
**Expected:** Deleted memory no longer appears in results

---

## V-6: Workflow Engine

**Tests:** FR-4.1, FR-4.2, FR-4.3, FR-4.4

### V-6.1: Review workflow executes
```
> run_workflow("review", "Review the last commit", options={"diff": "git diff HEAD~1"})
```
**Expected:** Returns workflow_id with status "completed", generates review artifact

### V-6.2: Workflow status polling
```
> workflow_status("<id from V-6.1>")
```
**Expected:** Returns completed status with steps, cost, and timing

### V-6.3: List workflows
```
> list_workflows("completed")
```
**Expected:** Shows the review workflow from V-6.1

### V-6.4: SPDD workflow — context acquisition
```
> run_workflow("spdd_feature", "Add a health check endpoint", files=["backend/src/main.py"])
```
**Expected:** Workflow loads SPDD skills and project docs in context_acquire phase

### V-6.5: SPDD workflow — verification gates
If research or spec phase fails (e.g., no relevant code found):
**Expected:** Workflow status shows `failed` and did not attempt subsequent phases

### V-6.6: Workflow artifacts generated
```bash
ls -la .claude/artifacts/
```
**Expected:** Contains `task_plan.md`, `workflow_status.md`, and possibly `implementation_plan.md`

### V-6.7: Cancel workflow
```
> run_workflow("feature", "Long task")  # start a workflow
> cancel_workflow("<id>", "Testing cancellation")
```
**Expected:** Returns cancelled status with reason

---

## V-7: Artifact System

**Tests:** FR-6.1, FR-6.2, FR-6.3

### V-7.1: Task artifact auto-updates
```
> TaskCreate("Test task for verification")
```
**Expected:** `.claude/artifacts/tasks.md` updated with the new task

### V-7.2: Artifact archival
```
> TaskCreate("Second test task")
```
**Expected:** `.claude/artifacts/archive/` contains a timestamped copy of the previous tasks.md

### V-7.3: Implementation plan skill
```
> /implementation-plan
```
**Expected:** `.claude/artifacts/implementation_plan.md` generated with structured sections and `<!-- Leave feedback -->` marker

### V-7.4: Walkthrough skill
```
> /walkthrough
```
**Expected:** `.claude/artifacts/walkthrough.md` generated summarizing work done

---

## V-8: Gemini Delegation

**Tests:** FR-2.1, gemini-delegate tools

### V-8.1: analyze_files works
```
> analyze_files(["backend/src/main.py", "backend/src/api.py", "backend/src/state.py"], "How does the API start up?")
```
**Expected:** Returns coherent answer based on file contents

### V-8.2: ask_gemini works
```
> ask_gemini("What is 2+2?")
```
**Expected:** Returns "4" (or equivalent)

### V-8.3: explain_architecture works
```
> explain_architecture()
```
**Expected:** Returns project overview from .gemini-index

### V-8.4: refresh_index works
```
> refresh_index()
```
**Expected:** Rebuilds .gemini-index, returns success message

### V-8.5: review_diff works
```
> review_diff("diff --git a/foo.py...\n-old\n+new")
```
**Expected:** Returns structured review feedback

### V-8.6: Proxy trace correlation
After any Gemini call:
```bash
curl -s http://localhost:1338/health | python3 -c "import sys,json; d=json.load(sys.stdin); v=d['velocity']['1hr']; print('PASS' if v['gemini']>0 else 'FAIL')"
```
**Expected:** PASS — proxy recorded the Gemini call

---

## V-9: Doc Staleness Tracking

**Tests:** FR-8.2

### V-9.1: Editing source triggers staleness
```
> Edit backend/src/scoring_engine.py (any small change)
```
**Expected:** Persistent state's `doc_staleness.stale_docs` includes `docs/PSD.md`

### V-9.2: Pending actions surfaces stale docs
Wait 10 minutes (or reset `pending_actions.last_reminder` to 0):
```
> Call any tool
```
**Expected:** A non-blocking reminder about stale docs appears

---

## V-10: Project Deployment

**Tests:** FR-7.1, FR-7.2

### V-10.1: Setup script deploys templates
```bash
mkdir /tmp/test-project && cd /tmp/test-project && git init
git subtree add --prefix=.claude/framework /path/to/claude_workspace main --squash
.claude/framework/setup.sh test_app "Test App"
```
**Expected:**
- `CLAUDE.md` exists with "Test App" in title
- `.mcp.json` exists with "test_app" in MEM0_APP_ID
- `.envrc` exists with "test_app"
- `.claude/settings.local.json` exists with framework hook paths
- `.claude/docs/test_app-guide.md` exists
- `.claude/skills/test_app-patterns/SKILL.md` exists
- `.claude/skills/test_app-workflows/SKILL.md` exists

### V-10.2: Setup is idempotent
```bash
.claude/framework/setup.sh test_app "Test App"
```
**Expected:** All files show "SKIP (already exists)"

### V-10.3: Subtree pull updates framework
Make a change in claude_workspace, commit, then:
```bash
cd /tmp/test-project
git subtree pull --prefix=.claude/framework /path/to/claude_workspace main --squash
```
**Expected:** Framework files updated, project files unchanged

### V-10.4: Cleanup
```bash
rm -rf /tmp/test-project
```

---

## V-11: Edge Cases & Resilience

### V-11.1: Missing state files
```bash
rm .claude/artifacts/.session-state.json
```
Then call any tool.
**Expected:** State file recreated with defaults, no crash

### V-11.2: Proxy down
```bash
pm2 stop antigravity-v2
```
Then call `init_session`.
**Expected:** Returns `{status: "blocked"}` with proxy listed in blockers and fix command

```bash
pm2 start antigravity-v2  # restore
```

### V-11.3: Langfuse down
```bash
docker stop ai-infra-langfuse-1
```
Then call a tool.
**Expected:** Tool executes normally. Trace fails silently (hook timeout, non-blocking).

```bash
docker start ai-infra-langfuse-1  # restore
```

### V-11.4: Qdrant down
```bash
docker stop ai-infra-qdrant-1
```
Then call `search_memories("test")`.
**Expected:** Returns error message, does not crash MCP server.

```bash
docker start ai-infra-qdrant-1  # restore
```

### V-11.5: Invalid JSON in state file
```bash
echo "CORRUPT" > .claude/artifacts/.session-state.json
```
Then call any tool.
**Expected:** State file reset to defaults, session continues.

### V-11.6: Hook timeout
The pre-tool-gate has a 2s timeout. If it takes longer:
**Expected:** Claude Code proceeds (hook errors are non-blocking warnings)

---

## V-12: MCP Server Health

### V-12.1: Check all servers running
```bash
.claude/framework/tools/reset-mcps.sh --check
```
**Expected:** All 5 servers show "RUNNING"

### V-12.2: Reset does not auto-reconnect
```bash
# DO NOT RUN unless you want to lose MCP tools for this session
# This is a destructive test — only run if you plan to restart Claude Code
.claude/framework/tools/reset-mcps.sh langfuse
```
**Expected:** Warning message about tool loss. Langfuse tools unavailable until restart.

---

## Quick Smoke Test Checklist

Run V-1 through V-3 for a quick health check:

- [ ] V-1: All 8 infrastructure checks pass
- [ ] V-2.2: init_session returns ready
- [ ] V-2.4: Session ID written
- [ ] V-3.1: Hook traces in Langfuse
- [ ] V-3.2: Proxy traces in Langfuse
- [ ] V-3.5: Cost report returns data
- [ ] V-3.6: Quota report returns velocity

If all pass, the framework is operational.

---

## Full Verification Summary Table

| Test | Category | Covers | Time |
|------|----------|--------|------|
| V-1 | Infrastructure | 8 checks | 1 min |
| V-2 | Session | 6 checks | 2 min |
| V-3 | Observability | 6 checks | 3 min |
| V-4 | Budget/Routing | 5 checks | 5 min |
| V-5 | Memory | 4 checks | 3 min |
| V-6 | Workflows | 7 checks | 5 min |
| V-7 | Artifacts | 4 checks | 3 min |
| V-8 | Gemini | 6 checks | 3 min |
| V-9 | Doc Staleness | 2 checks | 2 min |
| V-10 | Deployment | 4 checks | 3 min |
| V-11 | Edge Cases | 6 checks | 5 min |
| V-12 | MCP Health | 2 checks | 1 min |
| **Total** | | **60 checks** | **~36 min** |
