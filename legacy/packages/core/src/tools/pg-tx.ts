import { ActionRegistry, ToolDefinition, ActionContext } from "../types.js";
import { txHandler } from "../actions/tx/tx.js";

const txRegistry: ActionRegistry = {
    begin: txHandler,
    commit: txHandler,
    rollback: txHandler,
    savepoint: txHandler,
    release: txHandler,
    list: txHandler,
};

export const PgTxToolSchema = txHandler.schema;

export async function pgTxHandler(params: any, context: ActionContext) {
    const handler = txRegistry[params.action];
    if (!handler) {
        throw new Error(`Unknown action: ${params.action}`);
    }
    return await handler.handler(params, context);
}

export const pgTxTool: ToolDefinition = {
    name: "pg_tx",
    config: {
        description: `Transaction lifecycle management for multi-step database operations.

Actions:
  • begin: Start a new transaction, returns session_id for subsequent calls
  • commit: Commit all changes in the transaction (releases session)
  • rollback: Discard all changes in the transaction (releases session)
  • savepoint: Create a named savepoint within the transaction
  • release: Release (remove) a savepoint
  • list: Show all active sessions (useful for discovery/debugging)

Workflow:
  1. Call begin → receive session_id
  2. Use session_id in pg_query/pg_schema calls
  3. Call commit or rollback with session_id

Session Lifecycle:
  • TTL: Sessions auto-rollback after 30 minutes of inactivity
  • Limit: Maximum 10 concurrent sessions (prevents resource exhaustion)
  • Cleanup: Connections are destroyed on close (no state leakage)

Examples:
  {"action": "list"}
  {"action": "begin"}
  {"action": "begin", "options": {"isolation_level": "serializable"}}
  {"action": "commit", "session_id": "<id>"}`,
        inputSchema: PgTxToolSchema,
        destructiveHint: true, // Transaction control affects data state
    },
    handler: (context) => (params) => pgTxHandler(params, context),
};
