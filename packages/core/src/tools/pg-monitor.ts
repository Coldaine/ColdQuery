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
        description: "Database observability (connections, locks, size, activity, health)",
        inputSchema: PgMonitorToolSchema,
    },
    handler: (context) => (params) => pgMonitorHandler(params, context),
};
