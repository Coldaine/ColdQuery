import { z } from "zod";
import { ActionHandler } from "../../types.js";

export const WriteSchema = z.object({
    action: z.literal("write"),
    sql: z.string(),
    params: z.array(z.unknown()).optional(),
    options: z.object({
        timeout_ms: z.number().optional(),
    }).optional(),
});

/**
 * Write handler for INSERT/UPDATE/DELETE queries.
 *
 * NOTE: Implementation is identical to readHandler. See read.ts for detailed
 * explanation of why we maintain separate handlers despite identical code.
 * TL;DR: semantic separation for audit trails and future extensibility.
 */
export const writeHandler: ActionHandler<typeof WriteSchema> = {
    schema: WriteSchema,
    handler: async (params, context) => {
        return await context.executor.execute(params.sql, params.params, {
            timeout_ms: params.options?.timeout_ms,
        });
    },
};
