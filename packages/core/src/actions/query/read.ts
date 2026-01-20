import { z } from "zod";
import { ActionHandler, resolveExecutor } from "../../types.js";

export const ReadSchema = z.object({
    action: z.literal("read"),
    sql: z.string(),
    params: z.array(z.unknown()).optional(),
    session_id: z.string().optional().describe("Session ID returned by pg_tx 'begin'. Use to read uncommitted data within a transaction."),
    options: z.object({
        timeout_ms: z.number().optional(),
    }).optional(),
});

export const readHandler: ActionHandler<typeof ReadSchema> = {
    schema: ReadSchema,
    handler: async (params, context) => {
        const executor = resolveExecutor(context, params.session_id);
        const options: any = {};
        if (params.options?.timeout_ms !== undefined) {
            options.timeout_ms = params.options.timeout_ms;
        }
        return await executor.execute(params.sql, params.params, options);
    },
};
