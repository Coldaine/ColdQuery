import { z } from "zod";
import { ActionHandler } from "../../types.js";

export const TransactionSchema = z.object({
    action: z.literal("transaction"),
    operations: z.array(z.object({
        sql: z.string().describe("SQL statement to execute"),
        params: z.array(z.unknown()).optional().describe("Query parameters"),
    })).min(1).describe("Array of SQL statements to execute atomically in a single transaction"),
});

/**
 * Batch Transaction Handler.
 * Executes multiple statements atomically without persistent session management.
 */
export const transactionHandler: ActionHandler<typeof TransactionSchema> = {
    schema: TransactionSchema,
    handler: async (params, context) => {
        // We use a dedicated session connection just for this batch, then close it.
        // This ensures atomicity and isolation.
        let sessionId: string | undefined;
        try {
            sessionId = await context.sessionManager.createSession();
            const executor = context.sessionManager.getSessionExecutor(sessionId)!;

            await executor.execute("BEGIN");
            const results = [];
            
            let i = 0;
            for (const op of params.operations) {
                try {
                    const res = await executor.execute(op.sql, op.params);
                    results.push(res);
                    i++;
                } catch (error: any) {
                    await executor.execute("ROLLBACK");
                    throw new Error(`Transaction failed at operation ${i}: ${error.message}`);
                }
            }

            await executor.execute("COMMIT");
            return {
                status: "committed",
                results
            };
        } finally {
            // Always close the temporary session if it was created
            if (sessionId) {
                await context.sessionManager.closeSession(sessionId);
            }
        }
    },
};
