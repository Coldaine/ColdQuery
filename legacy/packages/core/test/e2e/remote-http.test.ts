import { describe, it, expect, beforeAll, afterAll, beforeEach, afterEach } from "vitest";
import { McpTestClient } from "./client.js";
import crypto from "crypto";

const TARGET_URL = process.env.MCP_TEST_URL; // e.g., http://raspberryoracle:3000/mcp
const runTests = !!TARGET_URL;

/**
 * E2E Acceptance Tests for ColdQuery
 *
 * Test Isolation Strategy (Hybrid):
 * - Persistent schema: `acceptance_test` (created once, dropped on cleanup)
 * - Ephemeral tables: Each test gets unique table names via testId
 * - Defense in depth: afterEach cleans up test tables, afterAll nukes schema
 *
 * Transport: Streamable HTTP (MCP 2025-11-25 spec)
 * Session Model: Stateless transport, stateful application (pg_tx for transactions)
 */
describe.skipIf(!runTests)("E2E: Acceptance Tests", () => {
    const SCHEMA = "acceptance_test";
    let client: McpTestClient;
    let testId: string;

    // Helper to call tools with consistent error handling
    async function callTool(name: string, args: Record<string, unknown>) {
        const result = await client.mcp.callTool({ name, arguments: args });
        return JSON.parse((result.content[0] as { text: string }).text);
    }

    beforeAll(async () => {
        console.log(`Connecting to remote MCP server at ${TARGET_URL}`);
        client = new McpTestClient({ type: "http", url: TARGET_URL! });
        await client.connect();

        // Ensure clean schema - drop if exists, then create
        await callTool("pg_query", {
            action: "write",
            sql: `DROP SCHEMA IF EXISTS ${SCHEMA} CASCADE`,
            autocommit: true,
        });
        await callTool("pg_query", {
            action: "write",
            sql: `CREATE SCHEMA ${SCHEMA}`,
            autocommit: true,
        });
        console.log(`Schema '${SCHEMA}' created`);
    });

    beforeEach(() => {
        testId = crypto.randomBytes(4).toString("hex");
    });

    afterEach(async () => {
        // Defense in depth: clean up test-specific tables
        const tableName = `${SCHEMA}.test_${testId}`;
        try {
            await callTool("pg_query", {
                action: "write",
                sql: `DROP TABLE IF EXISTS ${tableName}`,
                autocommit: true,
            });
        } catch (e) {
            // Expected if table wasn't created; log others for debugging
            console.debug(`Cleanup: table '${tableName}' drop failed (may not exist):`, e);
        }
    });

    afterAll(async () => {
        // Nuclear cleanup: drop entire schema
        if (client) {
            try {
                await callTool("pg_query", {
                    action: "write",
                    sql: `DROP SCHEMA IF EXISTS ${SCHEMA} CASCADE`,
                    autocommit: true,
                });
                console.log(`Schema '${SCHEMA}' dropped`);
            } catch (e) {
                console.error("Failed to drop schema:", e);
            } finally {
                await client.disconnect();
            }
        }
    });

    // =========================================================================
    // Health
    // =========================================================================
    describe("Health", () => {
        it("should report healthy status", async () => {
            const result = await callTool("pg_monitor", { action: "health" });
            expect(result.status).toBe("healthy");
        });
    });

    // =========================================================================
    // Schema Management
    // =========================================================================
    describe("Schema Management", () => {
        it("should list schemas", async () => {
            const result = await callTool("pg_schema", {
                action: "list",
                target: "schema",
            });
            expect(result.rows).toBeDefined();
            expect(Array.isArray(result.rows)).toBe(true);
            // acceptance_test schema should exist
            const schemaNames = result.rows.map((r: { name: string }) => r.name);
            expect(schemaNames).toContain(SCHEMA);
        });

        it("should create and list tables", async () => {
            const tableName = `test_${testId}`;

            // Create table
            await callTool("pg_query", {
                action: "write",
                sql: `CREATE TABLE ${SCHEMA}.${tableName} (id SERIAL PRIMARY KEY, name TEXT NOT NULL)`,
                autocommit: true,
            });

            // List tables in schema
            const result = await callTool("pg_schema", {
                action: "list",
                target: "table",
                schema: SCHEMA,
            });

            const tableNames = result.rows.map((r: { name: string }) => r.name);
            expect(tableNames).toContain(tableName);
        });

        it("should describe table columns", async () => {
            const tableName = `test_${testId}`;

            // Create table with various column types
            await callTool("pg_query", {
                action: "write",
                sql: `CREATE TABLE ${SCHEMA}.${tableName} (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW()
                )`,
                autocommit: true,
            });

            // Describe table
            const result = await callTool("pg_schema", {
                action: "describe",
                target: "table",
                name: tableName,
                schema: SCHEMA,
            });

            expect(result.columns).toBeDefined();
            expect(result.columns.length).toBe(3);

            const columnNames = result.columns.map((c: { name: string }) => c.name);
            expect(columnNames).toContain("id");
            expect(columnNames).toContain("name");
            expect(columnNames).toContain("created_at");
        });
    });

    // =========================================================================
    // CRUD Operations
    // =========================================================================
    describe("CRUD Operations", () => {
        it("should insert, read, update, and delete", async () => {
            const tableName = `test_${testId}`;

            // Setup: Create table
            await callTool("pg_query", {
                action: "write",
                sql: `CREATE TABLE ${SCHEMA}.${tableName} (id SERIAL PRIMARY KEY, value TEXT)`,
                autocommit: true,
            });

            // CREATE: Insert data
            await callTool("pg_query", {
                action: "write",
                sql: `INSERT INTO ${SCHEMA}.${tableName} (value) VALUES ($1)`,
                params: ["initial value"],
                autocommit: true,
            });

            // READ: Verify insert
            let result = await callTool("pg_query", {
                action: "read",
                sql: `SELECT * FROM ${SCHEMA}.${tableName}`,
            });
            expect(result.rows).toHaveLength(1);
            expect(result.rows[0].value).toBe("initial value");
            const insertedId = result.rows[0].id;

            // UPDATE: Modify data
            await callTool("pg_query", {
                action: "write",
                sql: `UPDATE ${SCHEMA}.${tableName} SET value = $1 WHERE id = $2`,
                params: ["updated value", insertedId],
                autocommit: true,
            });

            // READ: Verify update
            result = await callTool("pg_query", {
                action: "read",
                sql: `SELECT * FROM ${SCHEMA}.${tableName} WHERE id = $1`,
                params: [insertedId],
            });
            expect(result.rows[0].value).toBe("updated value");

            // DELETE: Remove data
            await callTool("pg_query", {
                action: "write",
                sql: `DELETE FROM ${SCHEMA}.${tableName} WHERE id = $1`,
                params: [insertedId],
                autocommit: true,
            });

            // READ: Verify delete
            result = await callTool("pg_query", {
                action: "read",
                sql: `SELECT * FROM ${SCHEMA}.${tableName}`,
            });
            expect(result.rows).toHaveLength(0);
        });
    });

    // =========================================================================
    // Transactions
    // =========================================================================
    describe("Transactions", () => {
        it("should rollback uncommitted changes", async () => {
            const tableName = `test_${testId}`;

            // Setup: Create table
            await callTool("pg_query", {
                action: "write",
                sql: `CREATE TABLE ${SCHEMA}.${tableName} (id SERIAL PRIMARY KEY, value TEXT)`,
                autocommit: true,
            });

            // Begin transaction
            const txResult = await callTool("pg_tx", { action: "begin" });
            expect(txResult.session_id).toBeDefined();
            const sessionId = txResult.session_id;

            // Insert within transaction
            await callTool("pg_query", {
                action: "write",
                sql: `INSERT INTO ${SCHEMA}.${tableName} (value) VALUES ($1)`,
                params: ["should disappear"],
                session_id: sessionId,
            });

            // Verify data visible within transaction
            let result = await callTool("pg_query", {
                action: "read",
                sql: `SELECT * FROM ${SCHEMA}.${tableName}`,
                session_id: sessionId,
            });
            expect(result.rows).toHaveLength(1);

            // Rollback
            await callTool("pg_tx", {
                action: "rollback",
                session_id: sessionId,
            });

            // Verify data is gone (read without session sees committed state)
            result = await callTool("pg_query", {
                action: "read",
                sql: `SELECT * FROM ${SCHEMA}.${tableName}`,
            });
            expect(result.rows).toHaveLength(0);
        });

        it("should commit and persist changes", async () => {
            const tableName = `test_${testId}`;

            // Setup: Create table
            await callTool("pg_query", {
                action: "write",
                sql: `CREATE TABLE ${SCHEMA}.${tableName} (id SERIAL PRIMARY KEY, value TEXT)`,
                autocommit: true,
            });

            // Begin transaction
            const txResult = await callTool("pg_tx", { action: "begin" });
            const sessionId = txResult.session_id;

            // Insert within transaction
            await callTool("pg_query", {
                action: "write",
                sql: `INSERT INTO ${SCHEMA}.${tableName} (value) VALUES ($1)`,
                params: ["should persist"],
                session_id: sessionId,
            });

            // Commit
            await callTool("pg_tx", {
                action: "commit",
                session_id: sessionId,
            });

            // Verify data persisted (read without session)
            const result = await callTool("pg_query", {
                action: "read",
                sql: `SELECT * FROM ${SCHEMA}.${tableName}`,
            });
            expect(result.rows).toHaveLength(1);
            expect(result.rows[0].value).toBe("should persist");
        });
    });

    // =========================================================================
    // Error Handling
    // =========================================================================
    describe("Error Handling", () => {
        it("should return error for invalid SQL syntax", async () => {
            const result = await client.mcp.callTool({
                name: "pg_query",
                arguments: {
                    action: "read",
                    sql: "SELEKT * FORM invalid_syntax",
                },
            });

            // MCP tools return isError: true for errors
            expect(result.isError).toBe(true);
            const errorText = (result.content[0] as { text: string }).text;
            expect(errorText).toMatch(/syntax error/i);
        });

        it("should return error for non-existent table", async () => {
            const result = await client.mcp.callTool({
                name: "pg_query",
                arguments: {
                    action: "read",
                    sql: `SELECT * FROM ${SCHEMA}.nonexistent_table_${testId}`,
                },
            });

            expect(result.isError).toBe(true);
            const errorText = (result.content[0] as { text: string }).text;
            expect(errorText).toMatch(/does not exist/i);
        });

        it("should require session_id or autocommit for writes", async () => {
            const tableName = `test_${testId}`;

            // Setup: Create table
            await callTool("pg_query", {
                action: "write",
                sql: `CREATE TABLE ${SCHEMA}.${tableName} (id SERIAL PRIMARY KEY)`,
                autocommit: true,
            });

            // Try to write without session_id or autocommit - should fail
            const result = await client.mcp.callTool({
                name: "pg_query",
                arguments: {
                    action: "write",
                    sql: `INSERT INTO ${SCHEMA}.${tableName} DEFAULT VALUES`,
                    // Missing both session_id and autocommit
                },
            });

            expect(result.isError).toBe(true);
            const errorText = (result.content[0] as { text: string }).text;
            expect(errorText).toMatch(/Safety Check Failed/i);
        });
    });
});
