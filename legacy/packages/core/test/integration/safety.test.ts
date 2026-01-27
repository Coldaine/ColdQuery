import { describe, it, expect, beforeAll } from "vitest";
import { PostgresExecutor } from "../../../../shared/executor/postgres.js";
import { pgQueryHandler } from "../../src/tools/pg-query.js";
import { pgSchemaHandler } from "../../src/tools/pg-schema.js";
import { pgTxHandler } from "../../src/tools/pg-tx.js";
import { SessionManager } from "../../src/session.js";

describe("Safety & Reliability Tests", { timeout: 15000 }, () => {
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
        // Set a small limit for testing enforcement
        const sessionManager = new SessionManager(executor, { maxSessions: 2 });
        context = { executor, sessionManager };
    });

    it("should fail write without autocommit or session_id", async () => {
        const params = {
            action: "write" as const,
            sql: "INSERT INTO test_products (name, price) VALUES ('Guard Test', 10)",
        };

        await expect(pgQueryHandler(params, context)).rejects.toThrow("Safety Check Failed");
    });

    it("should enforce maxSessions limit", async () => {
        const s1 = await pgTxHandler({ action: "begin" }, context);
        const s2 = await pgTxHandler({ action: "begin" }, context);
        
        // Third session should fail (limit is 2)
        await expect(pgTxHandler({ action: "begin" }, context)).rejects.toThrow("Maximum session limit (2) reached");

        // Cleanup
        await pgTxHandler({ action: "rollback", session_id: s1.session_id }, context);
        await pgTxHandler({ action: "rollback", session_id: s2.session_id }, context);
    });

    it("should maintain transaction isolation between sessions", async () => {
        // Cleanup leftover table if it exists
        await executor.execute("DROP TABLE IF EXISTS isolation_test");

        // Create a table for isolation test
        await pgSchemaHandler({
            action: "create",
            target: "table",
            name: "isolation_test",
            definition: "id int",
            autocommit: true
        }, context);

        const s1 = await pgTxHandler({ action: "begin" }, context);
        const s2 = await pgTxHandler({ action: "begin" }, context);

        // Session 1 writes data
        await pgQueryHandler({
            action: "write",
            sql: "INSERT INTO isolation_test VALUES (100)",
            session_id: s1.session_id
        }, context);

        // Session 2 should NOT see it (Read Committed)
        const readS2 = await pgQueryHandler({
            action: "read",
            sql: "SELECT count(*) FROM isolation_test",
            session_id: s2.session_id
        }, context);
        expect(readS2.rows[0].count).toBe("0");

        // Global executor should NOT see it
        const readGlobal = await executor.execute("SELECT count(*) FROM isolation_test");
        expect(readGlobal.rows[0].count).toBe("0");

        // Commit S1
        await pgTxHandler({ action: "commit", session_id: s1.session_id }, context);

        // Now S2 should see it (if it starts a new transaction or is in read committed)
        // Wait, session 2 is in an open transaction. In Read Committed, it will see it on next statement.
        const readS2After = await pgQueryHandler({
            action: "read",
            sql: "SELECT count(*) FROM isolation_test",
            session_id: s2.session_id
        }, context);
        expect(readS2After.rows[0].count).toBe("1");

        // Cleanup
        await pgTxHandler({ action: "rollback", session_id: s2.session_id }, context);
        await pgSchemaHandler({ action: "drop", target: "table", name: "isolation_test", autocommit: true }, context);
    });

    it("should return connection pool to baseline after 5 sessions", { timeout: 60000 }, async () => {
        // Create a dedicated manager for this test to avoid the class-level limit of 2
        const largeSessionManager = new SessionManager(executor, { maxSessions: 100 });
        const localContext = { ...context, sessionManager: largeSessionManager };

        // Get initial connection count
        const initialRes = await executor.execute("SELECT count(*) FROM pg_stat_activity WHERE datname = 'mcp_test'");
        const initialCount = parseInt(initialRes.rows[0].count);

        const sessionIds: string[] = [];
        // Create 5 sessions
        for (let i = 0; i < 5; i++) {
            const res = await pgTxHandler({ action: "begin" }, localContext);
            sessionIds.push(res.session_id);
        }

        // Close 5 sessions
        for (const id of sessionIds) {
            await pgTxHandler({ action: "rollback", session_id: id }, localContext);
        }

        // Get final connection count
        const finalRes = await executor.execute("SELECT count(*) FROM pg_stat_activity WHERE datname = 'mcp_test'");
        const finalCount = parseInt(finalRes.rows[0].count);

        // Allow for some minor fluctuation but should be back to baseline pool
        expect(finalCount).toBeLessThanOrEqual(initialCount + 2); 
    });
});
