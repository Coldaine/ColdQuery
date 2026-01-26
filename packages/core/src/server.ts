import { FastMCP } from "fastmcp";
import { PostgresExecutor } from "@pg-mcp/shared/executor/postgres.js";
import { Logger } from "./logger.js";
import { SessionManager } from "./session.js";
import { pgQueryHandler, PgQuerySchema } from "./tools/pg-query.js";
import { pgSchemaHandler, PgSchemaToolSchema } from "./tools/pg-schema.js";
import { pgAdminHandler, PgAdminToolSchema } from "./tools/pg-admin.js";
import { pgMonitorHandler, PgMonitorToolSchema } from "./tools/pg-monitor.js";
import { pgTxHandler, PgTxToolSchema } from "./tools/pg-tx.js";
import type { ActionContext } from "./types.js";
import { wrapResponse } from "./middleware/session-echo.js";

/**
 * FastMCP Migration - Server Entry Point
 * 
 * WHY FASTMCP:
 * - Built-in session management (context.sessionId)
 * - Built-in HTTP streaming transport
 * - Handles multi-client isolation automatically
 * - Simpler tool registration with addTool()
 */

// Global singleton helper to allow tool handlers to access DB
const executor = new PostgresExecutor({
    host: process.env['PGHOST'] || "localhost",
    port: parseInt(process.env['PGPORT'] || "5432"),
    user: process.env['PGUSER'] || "postgres",
    password: process.env['PGPASSWORD'] || "",
    database: process.env['PGDATABASE'] || "postgres",
});

const sessionManager = new SessionManager(executor);
const actionContext: ActionContext = { executor, sessionManager };

const server = new FastMCP({
    name: "coldquery",
    version: "0.2.0",
    instructions: `ColdQuery is a PostgreSQL MCP server providing database management tools.

Available tools:
- pg_query: Execute SQL queries (read, write, explain, transaction)
- pg_schema: Manage database schemas (list, describe, create, alter, drop)
- pg_admin: Database administration (vacuum, analyze, reindex, stats, settings)
- pg_monitor: Monitoring and health (health, connections, locks, size, activity)
- pg_tx: Transaction control (begin, commit, rollback, savepoint, release, list)

Safety: Write operations require explicit session_id or autocommit:true.`,
});

// Register pg_query tool
server.addTool({
    name: "pg_query",
    description: `Execute SQL queries for data manipulation (DML) and raw read/write operations.

Actions:
  • read: Execute SELECT queries (safe, read-only)
  • write: Execute INSERT/UPDATE/DELETE (requires session_id OR autocommit:true)
  • explain: Analyze query execution plans (supports EXPLAIN ANALYZE)
  • transaction: Execute multiple statements atomically (stateless batch)

Safety: Write operations use Default-Deny policy to prevent accidental data corruption.
Without session_id or autocommit:true, writes will fail with a safety error.`,
    parameters: PgQuerySchema,
    annotations: {
        title: "Database Query Tool",
        destructiveHint: true,
        openWorldHint: true,
    },
    execute: async (params) => {
        const result = await pgQueryHandler(params, actionContext);
        const wrappedResult = wrapResponse(result, params, "pg_query", sessionManager);
        return JSON.stringify(wrappedResult, null, 2);
    },
});

// Register pg_schema tool
server.addTool({
    name: "pg_schema",
    description: `Manage database schema objects (tables, columns, types).

Actions:
  • list: List tables/views in a schema (with pagination)
  • describe: Get detailed schema for a table
  • create: Create tables/schemas with SQL DDL
  • alter: Modify existing tables (add columns, rename, etc.)
  • drop: Remove tables/schemas

Safety: create/alter/drop are destructive and require explicit confirmation.`,
    parameters: PgSchemaToolSchema,
    annotations: {
        title: "Database Schema Manager",
        destructiveHint: true,
        openWorldHint: true,
    },
    execute: async (params) => {
        const result = await pgSchemaHandler(params, actionContext);
        const wrappedResult = wrapResponse(result, params, "pg_schema", sessionManager);
        return JSON.stringify(wrappedResult, null, 2);
    },
});

// Register pg_admin tool  
server.addTool({
    name: "pg_admin",
    description: `Database administration and maintenance operations.

Actions:
  • vacuum: Reclaim storage and update statistics
  • analyze: Update table statistics for query planning
  • reindex: Rebuild indexes
  • stats: Get table statistics (row counts, sizes)
  • settings: View/modify PostgreSQL configuration`,
    parameters: PgAdminToolSchema,
    annotations: {
        title: "Database Administrator",
        destructiveHint: true,
        openWorldHint: true,
    },
    execute: async (params) => {
        const result = await pgAdminHandler(params, actionContext);
        const wrappedResult = wrapResponse(result, params, "pg_admin", sessionManager);
        return JSON.stringify(wrappedResult, null, 2);
    },
});

// Register pg_monitor tool
server.addTool({
    name: "pg_monitor",
    description: `Monitor database health and performance.

Actions:
  • health: Check database connectivity and basic stats
  • connections: Show active connections
  • locks: Show current locks
  • size: Show database/table sizes
  • activity: Show active queries`,
    parameters: PgMonitorToolSchema,
    annotations: {
        title: "Database Monitor",
        readOnlyHint: true,
        openWorldHint: true,
    },
    execute: async (params) => {
        const result = await pgMonitorHandler(params, actionContext);
        const wrappedResult = wrapResponse(result, params, "pg_monitor", sessionManager);
        return JSON.stringify(wrappedResult, null, 2);
    },
});

// Register pg_tx tool
server.addTool({
    name: "pg_tx",
    description: `Manage database transactions with session-based state.

Actions:
  • begin: Start a new transaction session
  • commit: Commit the current transaction
  • rollback: Rollback the current transaction
  • savepoint: Create a savepoint within a transaction
  • release: Release a savepoint
  • list: List active sessions`,
    parameters: PgTxToolSchema,
    annotations: {
        title: "Transaction Manager",
        openWorldHint: true,
    },
    execute: async (params) => {
        const result = await pgTxHandler(params, actionContext);
        const wrappedResult = wrapResponse(result, params, "pg_tx", sessionManager);
        return JSON.stringify(wrappedResult, null, 2);
    },
});

// Determine transport type
const transportType = process.argv.includes("--transport")
    ? process.argv[process.argv.indexOf("--transport") + 1]
    : "stdio";

if (transportType === "sse" || transportType === "http") {
    const port = parseInt(process.env['PORT'] || "3000");
    const host = process.env['HOST'] || "0.0.0.0";

    server.start({
        transportType: "httpStream",
        httpStream: {
            port,
            host,
        },
    });
    Logger.info(`ColdQuery HTTP Server running on http://${host}:${port}`);
} else {
    server.start({ transportType: "stdio" });
    Logger.info("ColdQuery running on stdio");
}
