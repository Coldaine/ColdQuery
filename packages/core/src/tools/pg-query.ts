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

export const PgQuerySchema = z.discriminatedUnion("action", [
    readHandler.schema,
    writeHandler.schema,
    explainHandler.schema,
    transactionHandler.schema,
]);

export async function pgQueryHandler(params: z.infer<typeof PgQuerySchema>, context: ActionContext) {
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
