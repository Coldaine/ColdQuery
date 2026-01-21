import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { PostgresExecutor } from "@pg-mcp/shared/executor/postgres.js";
import { Logger } from "./logger.js";
import { SessionManager } from "./session.js";
import { pgQueryTool } from "./tools/pg-query.js";
import { pgSchemaTool } from "./tools/pg-schema.js";
import { pgAdminTool } from "./tools/pg-admin.js";
import { pgMonitorTool } from "./tools/pg-monitor.js";
import { pgTxTool } from "./tools/pg-tx.js";
import { setupHttpTransport } from "./transports/http.js";
import { wrapResponse } from "./middleware/session-echo.js";

// Global singleton helper to allow tool handlers to access DB
const executor = new PostgresExecutor({
    host: process.env['PGHOST'] || "localhost",
    port: parseInt(process.env['PGPORT'] || "5432"),
    user: process.env['PGUSER'] || "postgres",
    password: process.env['PGPASSWORD'] || "",
    database: process.env['PGDATABASE'] || "postgres",
});

const sessionManager = new SessionManager(executor);
const context = { executor, sessionManager };

/**
 * Server Lifecycle Management
 * 
 * WHY SHARED CONTEXT:
 * - The 'executor' (DB pool) and 'sessionManager' are shared across all 
 *   clients to maximize connection reuse and maintain global session limits.
 *
 * WHY FACTORY (createMcpServer):
 * - To support multi-client HTTP/SSE, we must provide each client with its 
 *   own McpServer instance to handle the protocol handshake and state.
 */

/**
 * Tool Registration Pattern
 *
 * WHY CURRIED HANDLERS: handler: (context) => (params) => result
 * - Tool definitions are static (defined at import time)
 * - Context (executor) is only available at runtime
 * - Currying delays context binding until registration, enabling:
 *   - Testing with mock context
 *   - Defining tools in separate files without circular imports
 *
 * WHY EXPLICIT ARRAY (not auto-discovery):
 * - All tools visible in one place for easy auditing
 * - Build fails if a tool import is broken (vs runtime error with auto-discovery)
 * - No filesystem scanning magic
 *
 * WHY UNIFORM JSON RESPONSE WRAPPING:
 * - MCP requires { content: [...] } format
 * - Centralizing here means handlers return plain objects
 * - Handlers stay testable without MCP dependencies
 */
const tools = [
    pgQueryTool,
    pgSchemaTool,
    pgAdminTool,
    pgMonitorTool,
    pgTxTool
];

export function createMcpServer() {
    const server = new McpServer({
        name: "coldquery",
        version: "0.2.0",
    });

    for (const tool of tools) {
        Logger.info(`registering tool: ${tool.name}`);

        const { description, inputSchema, readOnlyHint, destructiveHint } = tool.config;

        const annotations: { readOnlyHint?: boolean; destructiveHint?: boolean } = {};
        if (readOnlyHint !== undefined) annotations.readOnlyHint = readOnlyHint;
        if (destructiveHint !== undefined) annotations.destructiveHint = destructiveHint;

        server.registerTool(
            tool.name,
            {
                description,
                inputSchema,
                ...(Object.keys(annotations).length > 0 ? { annotations } : {}),
            },
            async (params) => {
                const rawResult = await tool.handler(context)(params);
                const result = wrapResponse(rawResult, params, tool.name, sessionManager);
                return {
                    content: [{ type: "text" as const, text: JSON.stringify(result, null, 2) }],
                };
            }
        );
    }
    return server;
}

async function main() {
    const transportType = process.argv.includes("--transport")
        ? process.argv[process.argv.indexOf("--transport") + 1]
        : "stdio";

    if (transportType === "sse" || transportType === "http") {
        const port = parseInt(process.env['PORT'] || "3000");
        await setupHttpTransport(port);
    } else {
        const server = createMcpServer();
        const transport = new StdioServerTransport();
        await server.connect(transport);
        Logger.info("ColdQuery running on stdio");
    }
}

main().catch(console.error);
