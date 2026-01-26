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

export const PgAdminToolSchema = z.object({
    action: z.enum(["vacuum", "analyze", "reindex", "stats", "settings"]).describe("Action to perform"),
    target: z.string().optional().describe("Target table name (for maintenance/stats) or setting name/category (for settings)"),
    options: z.object({
        full: z.boolean().optional().describe("Use VACUUM FULL (completely rewrites table, requires exclusive lock)"),
        verbose: z.boolean().optional().describe("Output detailed progress information"),
        analyze: z.boolean().optional().describe("Run ANALYZE after VACUUM to update statistics"),
    }).optional().describe("Maintenance operation options (vacuum/analyze)"),
    subaction: z.enum(["list", "get", "set"]).optional().describe("Settings sub-action: list (browse), get (specific), set (modify) - (only for 'settings' action)"),
    value: z.string().optional().describe("New value for the setting (required for 'settings' set subaction)"),
    session_id: z.string().optional().describe("Session ID for transactional settings"),
    autocommit: z.boolean().optional().describe("Set to true to execute 'settings set' immediately"),
});

export async function pgAdminHandler(params: any, context: ActionContext) {
    const handler = adminRegistry[params.action];
    if (!handler) {
        throw new Error(`Unknown action: ${params.action}`);
    }
    // We pass the params through; zod validation happened at the tool level.
    // The individual handlers might re-validate or just use the properties.
    // Since we merged the schemas, the properties are present but might be undefined if not used.
    // This is fine as the handlers inspect what they need.
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
