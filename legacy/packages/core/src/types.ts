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
        /** Suggests that this tool only reads data and has no side effects */
        readOnlyHint?: boolean;
        /** Suggests that this tool may destroy data or have significant side effects */
        destructiveHint?: boolean;
        /** A human-readable title for the tool, useful for UI display */
        title?: string;
        /** Suggests that calling this tool repeatedly with the same arguments has no additional effect */
        idempotentHint?: boolean;
        /** Suggests that the tool may interact with an "open world" of external entities */
        openWorldHint?: boolean;
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
