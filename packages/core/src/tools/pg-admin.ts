import { z } from "zod";
import { ActionRegistry, ActionContext, ToolDefinition } from "../types.js";
import { maintenanceHandler } from "../actions/admin/maintenance.js";
import { statsHandler } from "../actions/admin/stats.js";
import { settingsHandler } from "../actions/admin/settings.js";

const adminRegistry: ActionRegistry = {
    vacuum: maintenanceHandler,
    analyze: maintenanceHandler,
    reindex: maintenanceHandler,
    stats: statsHandler,
    settings: settingsHandler,
};

export const PgAdminToolSchema = z.discriminatedUnion("action", [
    maintenanceHandler.schema,
    statsHandler.schema,
    settingsHandler.schema,
]);

export async function pgAdminHandler(params: any, context: ActionContext) {
    const handler = adminRegistry[params.action];
    if (!handler) {
        throw new Error(`Unknown action: ${params.action}`);
    }
    return await handler.handler(params, context);
}

export const pgAdminTool: ToolDefinition = {
    name: "pg_admin",
    config: {
        description: `Database maintenance and administration operations.

Actions:
  • vacuum: Reclaim storage and update statistics (can lock tables, use with care)
  • analyze: Update query planner statistics (safe, recommended after bulk changes)
  • reindex: Rebuild indexes (locks table during operation)
  • stats: View table activity statistics from pg_stat_user_tables (read-only)
  • settings: List/get/set PostgreSQL configuration parameters

Note: vacuum, analyze, reindex are maintenance operations that may affect performance.
The 'settings.set' action requires session_id OR autocommit:true.

Examples:
  {"action": "stats"}
  {"action": "stats", "target": "users"}
  {"action": "vacuum", "target": "users"}
  {"action": "settings", "subaction": "get", "target": "work_mem"}`,
        inputSchema: PgAdminToolSchema,
        destructiveHint: true, // Maintenance operations can lock tables and affect performance
    },
    handler: (context) => (params) => pgAdminHandler(params, context),
};
