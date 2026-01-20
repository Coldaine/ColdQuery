import { z } from "zod";
import { QueryExecutor } from "@pg-mcp/shared/executor/interface.js";
import { SessionManager } from "./session.js";

export const ToolActionSchema = z.object({
    action: z.string(),
});

export interface ActionContext {
    executor: QueryExecutor;
    sessionManager: SessionManager;
}

export interface ActionHandler<T extends z.ZodTypeAny, R = any> {
    schema: T;
    handler: (params: z.infer<T>, context: ActionContext) => Promise<R>;
}

export type ActionRegistry = Record<string, ActionHandler<any>>;

export interface ToolDefinition {
    name: string;
    config: {
        description: string;
        inputSchema: z.ZodTypeAny;
    };
    handler: (context: ActionContext) => (params: any) => Promise<any>;
}

/**
 * Helper to resolve the correct executor (global vs session-bound)
 */
export function resolveExecutor(context: ActionContext, sessionId?: string): QueryExecutor {
    if (!sessionId) {
        return context.executor;
    }
    const sessionExec = context.sessionManager.getSessionExecutor(sessionId);
    if (!sessionExec) {
        throw new Error(`Invalid or expired session ID: ${sessionId}`);
    }
    return sessionExec;
}
