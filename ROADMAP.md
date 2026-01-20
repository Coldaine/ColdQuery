# PostgreSQL MCP Roadmap

Future extensions planned for this MCP server.

---

## pg_vector — Vector Similarity Search

**Status:** Planned
**Priority:** High
**Complexity:** Medium

### What It Is

[pgvector](https://github.com/pgvector/pgvector) is a PostgreSQL extension for vector similarity search. It's widely used for AI/ML applications that need to store and query embeddings.

### Why Add It

AI assistants working with this MCP server will often need to:
- Store embeddings from text, images, or other data
- Perform similarity searches (find similar documents, semantic search)
- Build RAG (Retrieval-Augmented Generation) pipelines

### Proposed Tools

```
pg_vector
├── create_index    — Create vector index (ivfflat, hnsw)
├── search          — k-nearest neighbor search
├── upsert          — Insert/update vectors with metadata
└── distance        — Calculate distance between vectors
```

### Dependencies

- pgvector extension must be installed on the PostgreSQL server
- Should gracefully handle servers without pgvector installed

---

## pg_code — Sandboxed Code Execution

**Status:** Concept
**Priority:** Medium
**Complexity:** High

### What It Is

A feature that allows AI agents to write and execute code (Python, JavaScript, SQL scripts) in a sandboxed environment. This is NOT a PostgreSQL extension — it's a capability for this MCP server.

### Why Add It

Some tasks can't be done in pure SQL:
- Complex data transformations requiring procedural logic
- Statistical analysis or ML operations on query results
- Multi-step ETL pipelines
- Generating reports or visualizations

Rather than the AI describing what to do, it could write code and execute it safely.

### How It Would Work

```
┌─────────────┐     ┌──────────────────┐     ┌────────────┐
│  AI Agent   │────▶│  pg_code tool    │────▶│  Sandbox   │
│             │     │  (this server)   │     │  (Docker)  │
└─────────────┘     └──────────────────┘     └────────────┘
                            │                       │
                            ▼                       ▼
                    Validates request        Executes code
                    Manages timeout          Returns results
                    Captures output          Cleans up
```

### Proposed Tools

```
pg_code
├── run_python      — Execute Python code in sandbox
├── run_sql_script  — Execute multi-statement SQL scripts
└── run_javascript  — Execute JavaScript (optional)
```

### Security Considerations

This is the hardest part. The sandbox must:

1. **Isolate execution** — Code runs in a container, not on the host
2. **Limit resources** — CPU, memory, execution time caps
3. **Restrict network** — No outbound connections (or allowlist only)
4. **Restrict filesystem** — No access to host filesystem
5. **Audit logging** — Record what was executed and by whom

### Prior Art

- [Code Sandbox MCP](https://www.philschmid.de/code-sandbox-mcp) — Uses Docker + llm-sandbox
- [E2B](https://e2b.dev/) — Cloud sandboxed code execution
- AWS Lambda / Cloud Functions — Serverless isolated execution

### Open Questions

1. **Where does the sandbox run?**
   - Same host as MCP server (Docker)?
   - Remote service (E2B, Lambda)?

2. **What libraries are pre-installed?**
   - Minimal (just stdlib)?
   - Data science stack (pandas, numpy)?

3. **How does code access query results?**
   - Pass data as JSON input?
   - Give sandbox its own DB connection?

4. **What's the trust model?**
   - Only allow code from trusted AI models?
   - Review/approve before execution?

### Implementation Approach

**Phase 1:** SQL script execution (multi-statement, no sandbox needed)
**Phase 2:** Python execution in Docker container
**Phase 3:** Resource limits, timeout handling, cleanup
**Phase 4:** Optional cloud sandbox integration (E2B, etc.)

---

## Completed Phases

For reference, here's what's already implemented:

### Phase 1: Foundation ✅
- Monorepo structure with npm workspaces
- Shared package for cross-cutting concerns
- QueryExecutor interface with pool/session support
- Identifier sanitization for SQL injection prevention

### Phase 2: Core Tools ✅
- **pg_query** — read, write, explain
- **pg_schema** — list, describe, create, alter, drop
- **pg_admin** — vacuum, analyze, reindex, stats, settings
- **pg_monitor** — health, connections, locks, size, activity
- **pg_tx** — begin, commit, rollback, savepoint, release
