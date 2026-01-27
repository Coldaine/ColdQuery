import { z } from "zod";
import { ActionRegistry, ActionContext, ToolDefinition } from "../types.js";
import { readHandler } from "../actions/query/read.js";
import { writeHandler } from "../actions/query/write.js";
import { explainHandler } from "../actions/query/explain.js";
import { transactionHandler } from "../actions/query/transaction.js";

const queryRegistry: ActionRegistry = {
    read: readHandler,
    write: writeHandler,
    explain: explainHandler,
    transaction: transactionHandler,
};

export const PgQuerySchema = z.object({
    action: z.enum(["read", "write", "explain", "transaction"]).describe("Action to perform: read (SELECT), write (INSERT/UPDATE/DELETE), explain (query plan), transaction (batch)"),
    sql: z.string().optional().describe("SQL query to execute (required for read, write, explain)"),
    params: z.array(z.any()).optional().describe("Query parameters ($1, $2, etc.) for parameterized queries"),
    analyze: z.boolean().optional().describe("Run EXPLAIN ANALYZE (only for 'explain' action)"),
    operations: z.array(z.object({
        sql: z.string(),
        params: z.array(z.any()).optional()
    })).optional().describe("List of operations for transaction batch (only for 'transaction' action)"),
    session_id: z.string().optional().describe("Session ID for transactional context"),
    autocommit: z.boolean().optional().describe("Set to true to allow write/transaction operations without an explicit session"),
});

export async function pgQueryHandler(params: any, context: ActionContext) {
    const handler = queryRegistry[params.action];
    if (!handler) {
        throw new Error(`Unknown action: ${params.action}`);
    }
    return await handler.handler(params, context);
}

export const pgQueryTool: ToolDefinition = {
    name: "pg_query",
    config: {
        description: `Execute SQL queries for data manipulation (DML) and raw read/write operations.

Actions:
  • read: Execute SELECT queries (safe, read-only)
  • write: Execute INSERT/UPDATE/DELETE (requires session_id OR autocommit:true)
  • explain: Analyze query execution plans (supports EXPLAIN ANALYZE)
  • transaction: Execute multiple statements atomically (stateless batch)

Safety: Write operations use Default-Deny policy to prevent accidental data corruption.
Without session_id or autocommit:true, writes will fail with a safety error.

Examples:
  {"action": "read", "sql": "SELECT * FROM users LIMIT 10"}
  {"action": "write", "sql": "UPDATE users SET active = true", "autocommit": true}
  {"action": "transaction", "operations": [{"sql": "..."}]}`,
        inputSchema: PgQuerySchema,
        destructiveHint: true, // Contains write/transaction actions that can modify data
    },
    handler: (context) => (params) => pgQueryHandler(params, context),
};
