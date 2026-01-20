import { describe, it, expect, beforeAll } from "vitest";
import { PostgresExecutor } from "../../../../shared/executor/postgres.js";
import { pgQueryHandler } from "../../src/tools/pg-query.js";
import { pgSchemaHandler } from "../../src/tools/pg-schema.js";
import { pgTxHandler } from "../../src/tools/pg-tx.js";
import { SessionManager } from "../../src/session.js";

describe("Session TTL Tests", { timeout: 10000 }, () => {
    let executor: PostgresExecutor;
    let context: any;

    beforeAll(async () => {
        executor = new PostgresExecutor({
            host: "127.0.0.1",
            port: 5433,
            user: "mcp",
            password: "mcp",
            database: "mcp_test",
        });
        // 2 second TTL for testing
        const sessionManager = new SessionManager(executor, { ttlMs: 2000 });
        context = { executor, sessionManager };
    });

    it("should auto-rollback and close session on TTL expiration", async () => {
        await pgSchemaHandler({
            action: "create",
            target: "table",
            name: "ttl_test",
            definition: "id int",
            autocommit: true
        }, context);

        const beginRes = await pgTxHandler({ action: "begin" }, context);
        const sessionId = beginRes.session_id;

        // Write something in transaction
        await pgQueryHandler({
            action: "write",
            sql: "INSERT INTO ttl_test VALUES (1)",
            session_id: sessionId
        }, context);

        // Verify it's there in session
        const readInner = await pgQueryHandler({
            action: "read",
            sql: "SELECT count(*) FROM ttl_test",
            session_id: sessionId
        }, context);
        expect(readInner.rows[0].count).toBe("1");

        // Wait for TTL (2s)
        await new Promise(resolve => setTimeout(resolve, 3000));

        // Session should be gone
        await expect(pgQueryHandler({
            action: "read",
            sql: "SELECT 1",
            session_id: sessionId
        }, context)).rejects.toThrow("Invalid or expired session ID");

        // Data should have been rolled back
        const readGlobal = await executor.execute("SELECT count(*) FROM ttl_test");
        expect(readGlobal.rows[0].count).toBe("0");

        // Cleanup
        await executor.execute("DROP TABLE ttl_test");
    });
});
