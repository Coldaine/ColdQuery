import { z } from "zod";
import { ActionHandler } from "../../types.js";

export const ReadSchema = z.object({
    action: z.literal("read"),
    sql: z.string(),
    params: z.array(z.unknown()).optional(),
    options: z.object({
        timeout_ms: z.number().optional(),
    }).optional(),
});

/**
 * Read handler for SELECT queries.
 *
 * WHY SEPARATE READ AND WRITE HANDLERS (even though implementations are identical):
 * 1. Semantic intent - The AI explicitly declares whether it's reading or mutating
 * 2. Audit trail - Logs can distinguish reads from writes without parsing SQL
 * 3. Future extensibility:
 *    - Route reads to replicas, writes to primary
 *    - Different permission checks (allow reads but not writes)
 *    - Different rate limits or quotas
 *
 * WHY WE DON'T ENFORCE READ-ONLY AT THIS LAYER:
 * - PostgreSQL functions can have side effects even in SELECT
 * - CTEs with mutations (WITH ... INSERT/UPDATE) exist
 * - The database itself is the source of truth for permissions
 * - Parsing SQL to detect writes is error-prone and incomplete
 */
export const readHandler: ActionHandler<typeof ReadSchema> = {
    schema: ReadSchema,
    handler: async (params, context) => {
        return await context.executor.execute(params.sql, params.params, {
            timeout_ms: params.options?.timeout_ms,
        });
    },
};
