# Gemini Instructions for postgresql-mcp

## Project Overview

This is a PostgreSQL MCP (Model Context Protocol) server designed for agentic AI workflows. It provides database access tools that are safe, transactional, and LLM-friendly.

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

You must document in `/docs/toolDescriptions/pg_query.md`:
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

- `/packages/core/src/session.ts` - SessionManager (connection-per-session)
- `/packages/core/src/actions/` - Tool handlers
- `/packages/core/src/types.ts` - ActionContext, resolveExecutor
- `/docs/plans/implementation_plan_v4.md` - Current implementation plan

## Key Design Decisions

1. **Default-Deny Writes**: Write tools require `session_id` OR `autocommit: true`
2. **Schema-Based Write Detection**: Tool schema declares if operation is a write, not SQL parsing
3. **30-Minute TTL**: Sessions expire after 30 min of inactivity
4. **Destructive Cleanup**: Connections destroyed on session close, not returned to pool

## Testing

```bash
npm test           # Run all tests
npm run test:watch # Watch mode
```

## Before Committing

- [ ] Tool descriptions documented in `/docs/toolDescriptions/`
- [ ] Tests pass
- [ ] No console.log left in code
