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
        description: "Database maintenance (vacuum, analyze, reindex, stats, settings)",
        inputSchema: PgAdminToolSchema,
    },
    handler: (context) => (params) => pgAdminHandler(params, context),
};
