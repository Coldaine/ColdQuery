# Agent Instructions for ColdQuery

Instructions for AI agents (Claude, Gemini, etc.) working on this codebase.

## Project Overview

ColdQuery is a PostgreSQL MCP (Model Context Protocol) server designed for agentic AI workflows. It provides database access tools that are safe, transactional, and LLM-friendly.

## Critical: Tool Description Documentation

**Every tool description in this codebase must be deeply documented and justified.**

When you add or modify any `.describe()` field in Zod schemas:

1. **Document it** in `/docs/toolDescriptions/<tool_name>.md`
2. **Justify the wording** - Why these specific words?
3. **Consider alternatives** - What other phrasings were considered?
4. **Predict LLM behavior** - How will different LLMs interpret this?

Tool descriptions are not comments - they are the primary interface for LLM agents. A poorly worded description causes misuse, silent failures, and security issues.

### Example of Required Documentation

If you write:
```typescript
session_id: z.string().optional()
    .describe("Transaction session ID from pg_tx 'begin'. Required for transactional writes.")
```

You should document in `/docs/toolDescriptions/pg_query.md`:
```markdown
#### `session_id`
- **Current description:** "Transaction session ID from pg_tx 'begin'. Required for transactional writes."
- **Justification:**
  - "from pg_tx 'begin'" tells the LLM exactly where to get this value
  - "Required for transactional writes" creates the link to the default-deny policy
- **Alternatives considered:**
  - "Optional session ID" - Too vague, LLMs ignored it
  - "Session ID for transaction context" - Didn't specify source
- **LLM behavior observed:** Claude correctly passes session_id after seeing 'begin' response
```

## Architecture Quick Reference

Key files to understand:

| File | Purpose |
|------|---------|
| `packages/core/src/server.ts` | Server initialization, tool registration |
| `packages/core/src/session.ts` | SessionManager (connection-per-session) |
| `packages/core/src/tools/` | Tool definitions with schemas |
| `packages/core/src/actions/` | Tool handlers (business logic) |
| `packages/core/src/types.ts` | ActionContext, resolveExecutor |
| `shared/executor/` | Database connection and execution |

For detailed architecture, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Key Design Decisions

1. **Default-Deny Writes**: Write tools require `session_id` OR `autocommit: true`
2. **Schema-Based Write Detection**: Tool schema declares if operation is a write, not SQL parsing
3. **30-Minute TTL**: Sessions expire after 30 min of inactivity
4. **Destructive Cleanup**: Connections destroyed on session close, not returned to pool
5. **Curried Handlers**: `handler: (context) => (params) => result` for testability

## Documentation Standards

### Tool Description Files

Every tool must have a description file in `docs/toolDescriptions/`:

- `pg_query.md` - Query execution and data manipulation
- `pg_schema.md` - Schema introspection and DDL
- `pg_admin.md` - Maintenance and administration
- `pg_tx.md` - Transaction lifecycle management
- `pg_monitor.md` - Database observability

### When Adding New Features

1. Write tests first (TDD)
2. Implement the feature
3. Document in appropriate location
4. Update TOOL_REFERENCE.md if schema changes
5. Update CHANGELOG.md

## Testing

```bash
npm test           # Run all tests
npm run test:ci    # Run with database lifecycle
npm run test:watch # Watch mode (via npx vitest watch)
```

## Before Committing

Checklist:
- [ ] Tool descriptions documented in `/docs/toolDescriptions/`
- [ ] Tests pass (`npm test`)
- [ ] Type checking passes (`npm run typecheck`)
- [ ] No console.log left in code (use Logger instead)
- [ ] CHANGELOG.md updated if user-facing changes

## Code Style

- TypeScript strict mode (all checks enabled)
- No `any` types without justification
- Parameterized queries only (no string concatenation for SQL)
- Comments explain "why", not "what"
- stderr for logging (stdout is MCP protocol)

## Security Reminders

- Never trust user input - validate with Zod schemas
- Use `sanitizeIdentifier()` for DDL operations
- Enforce Default-Deny for all write operations
- Log operations for audit trail

## Useful Commands

| Command | Purpose |
|---------|---------|
| `npm run build` | Compile TypeScript |
| `npm run dev` | Watch mode compilation |
| `npm test` | Run tests |
| `npm run typecheck` | Type checking only |
| `npm run lint` | ESLint |
| `npm run check` | lint + typecheck |
| `docker compose up -d` | Start test database |

## Getting Help

- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) - Full development guide
- [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) - Common issues
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - System design
