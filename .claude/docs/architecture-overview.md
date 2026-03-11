# Architecture Overview

## System Context

The Multi-Agent Orchestration System coordinates multiple AI models and tools through Claude Code CLI as the outer orchestrator. It provides reusable infrastructure (Part 1) that any project can customize (Part 2).

```mermaid
graph TB
    subgraph "User Interface"
        CC[Claude Code CLI<br/>Opus 4.6 - Outer Orchestrator]
    end

    subgraph "Skills Layer"
        GS[Generic Skills<br/>~/.claude/skills/]
        PS[Project Skills<br/>.claude/skills/]
    end

    subgraph "Artifacts Layer"
        ART[.claude/artifacts/<br/>task_plan, impl_plan,<br/>review, walkthrough, status]
    end

    subgraph "MCP Servers"
        OM[orchestrator-mcp<br/>LangGraph + PydanticAI]
        GM[gemini-delegate<br/>Analysis Offloading]
        MM[mem0-mcp<br/>Persistent Memory]
        ST[sequential-thinking<br/>Reflective Reasoning]
        LM[langfuse-mcp<br/>Observability Bridge]
    end

    subgraph "External Services"
        PROXY[antigravity-claude-proxy<br/>localhost:1337]
        LF[Langfuse<br/>localhost:3000]
        QD[Qdrant<br/>localhost:6333]
        N4J[Neo4j<br/>localhost:7687]
        OL[Ollama<br/>localhost:11434]
    end

    subgraph "AI Models (via Proxy)"
        OP[Claude Opus 4.6]
        SN[Claude Sonnet 4.6]
        HK[Claude Haiku 4.5]
        G31[Gemini 3.1 Pro]
        G3F[Gemini 3 Flash]
        G25[Gemini 2.5 Flash Lite]
    end

    CC --> GS & PS
    CC --> ART
    OM -->|"generates"| ART
    CC --> OM & GM & MM & ST & LM
    CC -->|"Agent tool<br/>(subagents)"| SN & HK

    OM -->|"PydanticAI"| PROXY
    OM -->|"traces"| LF
    OM -->|"checkpoints"| SQLite[(SQLite)]
    GM -->|"analysis"| PROXY
    MM -->|"vectors"| QD
    MM -->|"graph"| N4J
    MM -->|"embeddings"| OL
    LM -->|"metrics"| LF

    PROXY --> OP & SN & HK & G31 & G3F & G25
```

## Data Flow

### Request Routing Flow

```mermaid
sequenceDiagram
    participant U as User
    participant CC as Claude Code (Opus)
    participant OR as Orchestrator MCP
    participant GM as Gemini Delegate
    participant SA as Subagent (Sonnet/Haiku)
    participant LF as Langfuse

    U->>CC: Task request
    CC->>CC: Classify task (skill: tool-router)

    alt Simple task (single model)
        CC->>SA: Agent tool (model selection)
        SA-->>CC: Result
    else Complex task (multi-step)
        CC->>OR: run_workflow(type, description)
        OR->>OR: Decompose → LangGraph
        loop Each workflow step
            alt Gemini-capable step
                OR->>GM: PydanticAI call (structured output)
                GM-->>OR: Validated result
            else Claude-required step
                OR-->>CC: Subagent instructions
                CC->>SA: Agent tool (execute step)
                SA-->>CC: Step result
                CC->>OR: workflow_status(id) + result
            end
            OR->>LF: Trace step (cost, tokens, latency)
        end
        OR-->>CC: Workflow complete
    end

    CC->>LF: Log final outcome
    CC-->>U: Result
```

### Memory Flow

```mermaid
graph LR
    subgraph "Write Path"
        A[Agent completes task] --> B{Decision/Pattern?}
        B -->|Yes| C[add_memory via mem0]
        C --> D[Qdrant vector store]
        C --> E[Neo4j graph store]
    end

    subgraph "Read Path"
        F[New task arrives] --> G[search_memories]
        G --> H[Qdrant similarity search]
        F --> I[search_graph / get_entity]
        I --> J[Neo4j relationship lookup]
        H & J --> K[Context-enriched prompt]
    end
```

### Observability Flow

```mermaid
graph TB
    subgraph "Collection"
        H1[PostToolUse Hook] -->|"auto-log MCP calls"| LF[Langfuse]
        H2[PreToolUse Hook] -->|"quota check"| QG[Quota Guard]
        OM[Orchestrator MCP] -->|"@observe decorator"| LF
        WF[Workflow steps] -->|"trace per node"| LF
    end

    subgraph "Analysis"
        LF --> CR[get_cost_report]
        LF --> AP[get_agent_performance]
        LF --> TR[get_traces]
    end

    subgraph "Optimization"
        CR --> RM[Route optimization<br/>Adjust model selection]
        AP --> PO[DSPy prompt optimization<br/>Phase 6]
    end
```

## Model Selection Flowchart

```mermaid
graph TD
    T[Task arrives] --> C{Classify task}

    C -->|"indexing, classification,<br/>memory extraction"| FL[Gemini 2.5 Flash Lite<br/>FREE]
    C -->|"review, analysis,<br/>brainstorming, 3+ files"| GF[Gemini 3 Flash<br/>FREE]
    C -->|"complex reasoning,<br/>architecture, long context"| GP[Gemini 3.1 Pro<br/>FREE]
    C -->|"quick fix, boilerplate,<br/>simple edit"| HK[Haiku 4.5<br/>LOW COST]
    C -->|"multi-file implementation,<br/>tests, refactoring"| SN[Sonnet 4.6<br/>MEDIUM COST]
    C -->|"final decisions,<br/>ambiguous debug, arch"| OP[Opus 4.6<br/>HIGH COST]

    GP -->|"can't resolve"| OP
    GF -->|"needs deeper reasoning"| GP
    HK -->|"too complex"| SN
    SN -->|"needs architecture"| OP
```

## Component Interactions

| Component | Depends On | Provides To |
|-----------|-----------|-------------|
| orchestrator-mcp | proxy, langfuse, sqlite | Claude Code (workflow management) |
| gemini-delegate | proxy, .gemini-index | Claude Code (analysis offloading) |
| mem0-mcp | qdrant, neo4j, ollama, proxy | All agents (persistent memory) |
| langfuse-mcp | langfuse server | Claude Code (observability) |
| sequential-thinking | (self-contained) | Architect, Orchestrator roles |
| Hooks | langfuse-mcp, orchestrator-mcp | Auto-logging, quota guardrails, artifact generation |
| Skills | (markdown files) | Claude Code (behavioral guidance) |
| Artifacts | orchestrator-mcp, hooks, skills | User (reviewable deliverables: plans, reviews, status) |

## Key Design Decisions

1. **Claude Code as outer orchestrator** — Not replaced; enhanced with skills, hooks, and MCP tools
2. **Gemini-first cost strategy** — Free models handle everything they can; Claude reserved for what requires it
3. **Hybrid execution** — Gemini calls happen inside orchestrator-mcp (PydanticAI); Claude calls return instructions for Agent tool
4. **SQLite checkpointing** — LangGraph state persists across interruptions; no external DB needed
5. **Structured outputs** — PydanticAI validates all agent responses against schemas; retries on failure
6. **4-layer rate limiting** — Proxy, orchestrator, cron, and per-workflow budget caps
7. **Artifact-driven transparency** — Workflows generate structured markdown deliverables at phase transitions; users review via inline feedback, not raw logs
