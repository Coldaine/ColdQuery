import { z } from "zod";
import { ActionHandler, resolveExecutor } from "../../types.js";

export const ExplainSchema = z.object({
    action: z.literal("explain"),
    sql: z.string(),
    params: z.array(z.unknown()).optional(),
    session_id: z.string().optional().describe("Session ID returned by pg_tx 'begin'. Required if checking plan for uncommitted changes."),
    options: z.object({
        explain_analyze: z.boolean().optional(),
        explain_format: z.enum(["text", "json"]).optional(),
        timeout_ms: z.number().optional(),
    }).optional(),
});

/**
 * EXPLAIN handler for query plan analysis.
 * 
 * WHY SESSION SUPPORT IN EXPLAIN:
 * EXPLAIN ANALYZE actually executes the query to measure performance. 
 * If the query depends on data modified within an uncommitted transaction,
 * it MUST be executed within the same session to see those changes.
 */
export const explainHandler: ActionHandler<typeof ExplainSchema> = {
    schema: ExplainSchema,
    handler: async (params, context) => {
        // Resolve either the global pooled executor or a dedicated session connection
        const executor = resolveExecutor(context, params.session_id);
        
        let explainSql = "EXPLAIN ";
        if (params.options?.explain_analyze || params.options?.explain_format) {
            const options = [];
            if (params.options.explain_analyze) options.push("ANALYZE");
            if (params.options.explain_format) options.push(`FORMAT ${params.options.explain_format.toUpperCase()}`);
            explainSql += `(${options.join(", ")}) `;
        }
        explainSql += params.sql;

        const queryOptions: any = {};
        if (params.options?.timeout_ms !== undefined) {
            queryOptions.timeout_ms = params.options.timeout_ms;
        }

        return await executor.execute(explainSql, params.params, queryOptions);
    },
};
