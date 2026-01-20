import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { PostgresExecutor } from "@pg-mcp/shared/executor/postgres.js";
import { Logger } from "./logger.js";
import { pgQueryTool } from "./tools/pg-query.js";
import { pgSchemaTool } from "./tools/pg-schema.js";
import { pgAdminTool } from "./tools/pg-admin.js";
import { pgMonitorTool } from "./tools/pg-monitor.js";
import { pgTxTool } from "./tools/pg-tx.js";
import { setupHttpTransport } from "./transports/http.js";

const server = new McpServer({
    name: "pg-mcp-core",
    version: "1.0.0",
});

const executor = new PostgresExecutor({
    host: process.env.PGHOST || "localhost",
    port: parseInt(process.env.PGPORT || "5432"),
    user: process.env.PGUSER || "postgres",
    password: process.env.PGPASSWORD || "postgres",
    database: process.env.PGDATABASE || "postgres",
});

const context = { executor };

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

for (const tool of tools) {
    Logger.info(`registering tool: ${tool.name}`);
    server.registerTool(
        tool.name,
        tool.config,
        async (params) => {
            const result = await tool.handler(context)(params);
            return {
                content: [{ type: "text" as const, text: JSON.stringify(result, null, 2) }],
            };
        }
    );
}

async function main() {
    const transportType = process.argv.includes("--transport")
        ? process.argv[process.argv.indexOf("--transport") + 1]
        : "stdio";

    if (transportType === "sse" || transportType === "http") {
        const port = parseInt(process.env.PORT || "3000");
        await setupHttpTransport(server, port);
    } else {
        const transport = new StdioServerTransport();
        await server.connect(transport);
        Logger.info("PostgreSQL MCP Server running on stdio");
    }
}

main().catch(console.error);
