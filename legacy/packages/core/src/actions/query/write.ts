import { z } from "zod";
import { ActionHandler, resolveExecutor } from "../../types.js";

export const WriteSchema = z.object({
    action: z.literal("write").describe("Write action - execute INSERT/UPDATE/DELETE statements"),
    sql: z.string().describe("SQL DML statement (INSERT, UPDATE, DELETE)"),
    params: z.array(z.unknown()).optional().describe("Parameterized query values (use $1, $2, etc. in SQL)"),
    session_id: z.string().optional().describe("Session ID returned by pg_tx 'begin'. REQUIRED for transactional writes."),
    autocommit: z.boolean().optional().describe("Set to true to execute a single-statement write immediately without a transaction. REQUIRED if session_id is not provided."),
    options: z.object({
        timeout_ms: z.number().optional().describe("Query timeout in milliseconds"),
    }).optional().describe("Query execution options"),
});

export const writeHandler: ActionHandler<typeof WriteSchema> = {
    schema: WriteSchema,
    handler: async (params, context) => {
        // Default-Deny Policy: Prevent accidental non-transactional writes
        if (!params.session_id && !params.autocommit) {
            throw new Error(
                "Safety Check Failed: Write operations require either a valid 'session_id' (for transactions) or 'autocommit: true' (for immediate execution). " +
                "This prevents accidental data corruption if the session ID is forgotten."
            );
        }

        const executor = resolveExecutor(context, params.session_id);
        const options: any = {};
        if (params.options?.timeout_ms !== undefined) {
            options.timeout_ms = params.options.timeout_ms;
        }
        return await executor.execute(params.sql, params.params, options);
    },
};
