/**
 * Deployment Tests - Remote PostgreSQL
 *
 * These tests verify the MCP server works against a real remote PostgreSQL instance.
 * 
 * IMPROVEMENTS:
 * 1. Black Box Testing: Spawns the actual server process via `harness.ts`.
 * 2. Hermetic: Creates a unique schema for each run, seeds it, and destroys it.
 * 3. Secure: No hardcoded credentials.
 */

import { describe, it, expect, beforeAll, afterAll } from "vitest";
import { PostgresExecutor } from "../../../../shared/executor/postgres.js";
import { deploymentConfig, isDeploymentTestEnabled } from "./config.js";
import { McpServerTestHarness } from "./harness.js";
import crypto from "crypto";

// Skip everything if deployment tests are not enabled
const runTests = isDeploymentTestEnabled();

// Only access config when tests are enabled to avoid throwing on missing env vars
const describeName = runTests ? `Deployment: ${deploymentConfig.name}` : "Deployment Tests (skipped)";

describe.skipIf(!runTests)(describeName, () => {
    let adminExecutor: PostgresExecutor;
    let harness: McpServerTestHarness;
    
    // Unique schema for this test run to ensure isolation
    const TEST_SCHEMA = `mcp_test_run_${crypto.randomBytes(4).toString("hex")}`;

    beforeAll(async () => {
        // 1. Connect as Admin to setup the test environment
        adminExecutor = new PostgresExecutor({
            host: deploymentConfig.host,
            port: deploymentConfig.port,
            user: deploymentConfig.user,
            password: deploymentConfig.password,
            database: deploymentConfig.database,
        });

        // Verify connectivity
        await adminExecutor.execute("SELECT 1");
        console.log(`Connected to ${deploymentConfig.host} for setup.`);

        // 2. Create Isolated Schema
        await adminExecutor.execute(`CREATE SCHEMA ${TEST_SCHEMA}`);
        
        // 3. Seed Data (Hermetic setup)
        // We create our own tables so we don't rely on existing DB state
        await adminExecutor.execute(`
            CREATE TABLE ${TEST_SCHEMA}.products (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                price DECIMAL(10,2)
            );
            INSERT INTO ${TEST_SCHEMA}.products (name, price) VALUES 
                ('Widget A', 10.50),
                ('Widget B', 25.00);
        `);

        // 4. Start the MCP Server (Black Box)
        // We configure it to use the same DB, but we'll force the search_path 
        // via the connection string or just rely on fully qualified names if needed.
        // Better: We rely on the server using the user/pass we give it.
        // NOTE: Postgres user must have access to the new schema.
        
        harness = new McpServerTestHarness({
            PGHOST: deploymentConfig.host,
            PGPORT: deploymentConfig.port.toString(),
            PGUSER: deploymentConfig.user,
            PGPASSWORD: deploymentConfig.password,
            PGDATABASE: deploymentConfig.database,
            // Key trick: Set search_path to our test schema by default for this session
            // This allows 'SELECT * FROM products' to work without prefix
            PGOPTIONS: `-c search_path=${TEST_SCHEMA},public` 
        });

        await harness.start();
    });

    afterAll(async () => {
        if (harness) await harness.stop();
        
        if (adminExecutor) {
            try {
                // Cleanup: Drop the entire schema
                await adminExecutor.execute(`DROP SCHEMA IF EXISTS ${TEST_SCHEMA} CASCADE`);
            } finally {
                await adminExecutor.disconnect();
            }
        }
    });

    describe("pg_query tool", () => {
        it("should read data from the isolated test schema", async () => {
            const result = await harness.mcpClient.callTool({
                name: "pg_query",
                arguments: {
                    action: "read",
                    sql: "SELECT * FROM products ORDER BY id"
                }
            });

            const content = JSON.parse((result.content[0] as any).text);
            expect(content.rows).toHaveLength(2);
            expect(content.rows[0].name).toBe("Widget A");
        });

        it("should write data and verify it persists", async () => {
            // Write
            await harness.mcpClient.callTool({
                name: "pg_query",
                arguments: {
                    action: "write",
                    sql: "INSERT INTO products (name, price) VALUES ($1, $2)",
                    params: ["Widget C", 99.99],
                    autocommit: true
                }
            });

            // Read back
            const result = await harness.mcpClient.callTool({
                name: "pg_query",
                arguments: {
                    action: "read",
                    sql: "SELECT * FROM products WHERE name = 'Widget C'"
                }
            });

            const content = JSON.parse((result.content[0] as any).text);
            expect(content.rows[0].price).toBe("99.99");
        });
    });

    describe("pg_schema tool", () => {
        it("should list tables in the test schema", async () => {
            const result = await harness.mcpClient.callTool({
                name: "pg_schema",
                arguments: {
                    action: "list",
                    target: "table",
                    schema: TEST_SCHEMA
                }
            });

            const content = JSON.parse((result.content[0] as any).text);
            const tableNames = content.rows.map((t: any) => t.name);
            expect(tableNames).toContain("products");
        });
    });

    describe("pg_monitor tool", () => {
        it("should report database health", async () => {
            const result = await harness.mcpClient.callTool({
                name: "pg_monitor",
                arguments: {
                    action: "health"
                }
            });

            const content = JSON.parse((result.content[0] as any).text);
            expect(content.status).toBe("healthy");
        });
    });
});
