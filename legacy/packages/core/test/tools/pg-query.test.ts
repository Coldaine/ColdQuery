import { describe, it, expect, beforeAll } from "vitest";
import { PostgresExecutor } from "../../../../shared/executor/postgres.js";
import { pgQueryHandler } from "../../src/tools/pg-query.js";
import { SessionManager } from "../../src/session.js";

describe("pg_query tool (live)", () => {
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
        const sessionManager = new SessionManager(executor);
        context = { executor, sessionManager };
    });

    it("should execute read action correctly", async () => {
        const params = {
            action: "read" as const,
            sql: "SELECT 1 as val",
        };

        const result = await pgQueryHandler(params, context);

        expect(result.rows[0].val).toBe(1);
    });

    it("should execute write action correctly", async () => {
        // Cleanup and setup
        await executor.execute("DROP TABLE IF EXISTS test_query_write");
        await executor.execute("CREATE TABLE test_query_write (name text)");

        const params = {
            action: "write" as const,
            sql: "INSERT INTO test_query_write (name) VALUES ($1)",
            params: ["Alice"],
            autocommit: true,
        };

        const result = await pgQueryHandler(params, context);

        expect(result.rowCount).toBe(1);

        const verify = await executor.execute("SELECT name FROM test_query_write");
        expect(verify.rows[0].name).toBe("Alice");
    });

    it("should execute explain action correctly", async () => {
        const params = {
            action: "explain" as const,
            sql: "SELECT 1",
            options: { explain_analyze: true }
        };

        const result = await pgQueryHandler(params as any, context);

        expect(JSON.stringify(result)).toContain("QUERY PLAN");
    });

    it("should execute batch transaction correctly", async () => {
        await executor.execute("DROP TABLE IF EXISTS test_batch_tx");
        await executor.execute("CREATE TABLE test_batch_tx (id int)");

        const params = {
            action: "transaction" as const,
            operations: [
                { sql: "INSERT INTO test_batch_tx VALUES (1)" },
                { sql: "INSERT INTO test_batch_tx VALUES (2)" }
            ]
        };

        const result = await pgQueryHandler(params, context);

        expect(result.status).toBe("committed");
        expect(result.results.length).toBe(2);

        const verify = await executor.execute("SELECT count(*) FROM test_batch_tx");
        expect(verify.rows[0].count).toBe("2");
    });

    it("should rollback batch transaction on failure", async () => {
        await executor.execute("DROP TABLE IF EXISTS test_batch_fail");
        await executor.execute("CREATE TABLE test_batch_fail (id int UNIQUE)");

        const params = {
            action: "transaction" as const,
            operations: [
                { sql: "INSERT INTO test_batch_fail VALUES (1)" },
                { sql: "INSERT INTO test_batch_fail VALUES (1)" } // Will fail UNIQUE constraint
            ]
        };

        await expect(pgQueryHandler(params, context)).rejects.toThrow("Transaction failed at operation 1");

        const verify = await executor.execute("SELECT count(*) FROM test_batch_fail");
        expect(verify.rows[0].count).toBe("0"); // Should be rolled back
    });
});
