import { z } from "zod";
import { ActionHandler, resolveExecutor } from "../../types.js";
import { sanitizeIdentifier } from "@pg-mcp/shared/security/identifiers.js";

export const TxSchema = z.object({
    action: z.enum(["begin", "commit", "rollback", "savepoint", "release", "list"]).describe("Transaction action: begin (start), commit (save), rollback (discard), savepoint/release (nested checkpoints), list (active sessions)"),
    session_id: z.string().optional().describe("Transaction Session ID. REQUIRED for commit, rollback, savepoint, release. Use the ID returned by 'begin'."),
    name: z.string().optional().describe("Savepoint identifier name (required for savepoint and release actions)"),
    options: z.object({
        isolation_level: z.enum(["read_uncommitted", "read_committed", "repeatable_read", "serializable"]).optional().describe("Transaction isolation level (only used with 'begin' action). Default: read_committed"),
    }).optional().describe("Transaction options (only used with 'begin' action)"),
});

/**
 * Transaction Handler.
 * 
 * WHY STATEFUL SESSIONS:
 * In a pooled environment, BEGIN/COMMIT must happen on the SAME connection.
 * 'begin' promotes a pooled connection to a dedicated 'session' connection.
 * Subsequent calls using the session_id will use that same connection.
 * 
 * WHY CLOSE ON COMMIT/ROLLBACK:
 * Once a transaction is finished, the dedicated connection MUST be released
 * back to the pool to prevent resource exhaustion (leaks).
 */
export const txHandler: ActionHandler<typeof TxSchema> = {
    schema: TxSchema,
    handler: async (params, context) => {
        // Special handling for LIST: Returns active sessions
        if (params.action === "list") {
            return {
                status: "success",
                sessions: context.sessionManager.listSessions()
            };
        }

        // Special handling for BEGIN: It creates the session
        if (params.action === "begin") {
            const sessionId = await context.sessionManager.createSession();
            let transactionStarted = false;
            try {
                const executor = context.sessionManager.getSessionExecutor(sessionId)!;
                
                const isoLevel = params.options?.isolation_level
                    ? ` ISOLATION LEVEL ${params.options.isolation_level.replace("_", " ").toUpperCase()}`
                    : "";
                
                await executor.execute(`BEGIN${isoLevel}`);
                transactionStarted = true;
                return {
                    status: "success",
                    session_id: sessionId,
                    message: "Transaction started. Use session_id for all subsequent queries in this transaction."
                };
            } finally {
                // If we created a session but failed to start the transaction, clean up immediately.
                if (!transactionStarted) {
                    await context.sessionManager.closeSession(sessionId);
                }
            }
        }

        // All other actions require a session_id
        if (!params.session_id) {
            throw new Error(`Action '${params.action}' requires a valid session_id returned by 'begin'`);
        }

        const executor = resolveExecutor(context, params.session_id);
        let sql = "";

        switch (params.action) {
            case "commit":
                sql = "COMMIT";
                break;
            case "rollback":
                sql = "ROLLBACK";
                break;
            case "savepoint":
                if (!params.name) throw new Error("Savepoint name is required");
                sql = `SAVEPOINT ${sanitizeIdentifier(params.name)}`;
                break;
            case "release":
                if (!params.name) throw new Error("Savepoint name is required for release");
                sql = `RELEASE SAVEPOINT ${sanitizeIdentifier(params.name)}`;
                break;
        }

        try {
            const result = await executor.execute(sql);
            
            // Close session after commit/rollback to release connection back to pool
            if (params.action === "commit" || params.action === "rollback") {
                await context.sessionManager.closeSession(params.session_id);
            }

            return {
                ...result,
                status: "success"
            };
        } catch (error) {
            // We leave the session open on error (except for begin) so the user 
            // can attempt a ROLLBACK or fix the issue if it's a transient DB error.
            throw error;
        }
    },
};
