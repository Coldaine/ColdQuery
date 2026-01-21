import { z } from "zod";
import { ActionRegistry, ActionContext, ToolDefinition } from "../types.js";
import { healthHandler } from "../actions/monitor/health.js";
import { observabilityHandler } from "../actions/monitor/observability.js";

const monitorRegistry: ActionRegistry = {
    health: healthHandler,
    connections: observabilityHandler,
    locks: observabilityHandler,
    size: observabilityHandler,
    activity: observabilityHandler,
};

export const PgMonitorToolSchema = z.discriminatedUnion("action", [
    healthHandler.schema,
    observabilityHandler.schema,
]);

export async function pgMonitorHandler(params: any, context: ActionContext) {
    const handler = monitorRegistry[params.action];
    if (!handler) {
        throw new Error(`Unknown action: ${params.action}`);
    }
    return await handler.handler(params, context);
}

export const pgMonitorTool: ToolDefinition = {
    name: "pg_monitor",
    config: {
        description: `Database observability and health monitoring (read-only).

Actions:
  • health: Quick database health check (version, connection status, server time)
  • activity: View currently running queries (excludes idle by default)
  • connections: Connection counts grouped by database and state
  • locks: Active lock information for debugging contention
  • size: Table sizes (top 20) or specific database size

This tool is purely read-only and safe to call at any time.
Useful for debugging performance issues, monitoring activity, and capacity planning.

Examples:
  {"action": "health"}
  {"action": "activity"}
  {"action": "size"}
  {"action": "size", "options": {"database": "mydb"}}`,
        inputSchema: PgMonitorToolSchema,
        readOnlyHint: true, // All actions are read-only observability queries
    },
    handler: (context) => (params) => pgMonitorHandler(params, context),
};
