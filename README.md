# MAO Framework

Multi-Agent Orchestration framework for Claude Code. Provides hooks, documentation, tools, and skills that coordinate multiple AI models through MCP servers with persistent memory, observability, and quota management.

This repo is designed to be pulled into projects via `git subtree`.

## Quick Start

### New project setup

```bash
cd my-project
git init  # if not already a git repo

# 1. Pull the framework
git subtree add --prefix=.claude/framework /path/to/this/repo main --squash

# 2. Run setup (copies templates, creates project dirs)
.claude/framework/setup.sh my_app "My App"

# 3. Configure
#    - Edit .mcp.json — fill in Langfuse keys, verify MCP server paths
#    - Edit CLAUDE.md — customize agent roles and dev rules
#    - Edit .claude/docs/my_app-guide.md — add domain entities
#    - Run: direnv allow
```

### Pull framework updates

```bash
git subtree pull --prefix=.claude/framework /path/to/this/repo main --squash
```

### Push framework improvements back

```bash
git subtree push --prefix=.claude/framework /path/to/this/repo main
```

## What's in the framework

| Directory | Contents |
|-----------|----------|
| `hooks/` | 2 consolidated hooks + shared lib (session gate, tracing, throttle, artifacts) |
| `docs/` | 11 framework guides + INDEX.md |
| `tools/` | `reset-mcps.sh` (MCP health check and reset) |
| `skills/` | Generic artifact skills (`/implementation-plan`, `/walkthrough`) |
| `templates/` | Project scaffolding (CLAUDE.md, .mcp.json, .envrc, settings, skill templates) |
| `setup.sh` | Deployment script for new projects |

## Project layout after setup

```
my-project/
├── CLAUDE.md                         ← from templates/, customized
├── .mcp.json                         ← from templates/, customized
├── .envrc                            ← from templates/, customized
├── .claude/
│   ├── framework/                    ← git subtree (this repo)
│   │   ├── hooks/
│   │   ├── docs/
│   │   ├── tools/
│   │   ├── skills/
│   │   ├── templates/
│   │   └── setup.sh
│   ├── docs/
│   │   └── my_app-guide.md           ← project-specific
│   ├── skills/
│   │   ├── my_app-patterns/          ← project-specific
│   │   └── my_app-workflows/         ← project-specific
│   ├── settings.local.json           ← from templates/, customized
│   └── artifacts/                    ← generated, gitignored
├── backend/
└── frontend/
```

## Prerequisites

The [AI Infrastructure](https://github.com/SpandrelInteractive/ai-infra) repo must be running:
- Docker services: Qdrant, Neo4j, Ollama, Langfuse, OTEL Collector/Bridge
- Antigravity proxy v2 on localhost:1338 (Docker Compose)
- MCP servers: orchestrator-mcp, gemini-delegate, mem0-mcp, langfuse-mcp

## Documentation

Framework guides live in `docs/`. Start with [`docs/INDEX.md`](docs/INDEX.md).

## Related

- **[AI Infrastructure](https://github.com/SpandrelInteractive/ai-infra)** — MCP servers, proxy, and Docker services
