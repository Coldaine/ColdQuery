import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { Transport } from "@modelcontextprotocol/sdk/shared/transport.js";
import express, { Request, Response } from "express";
import { randomUUID } from "crypto";
import { Logger } from "../logger.js";

/**
 * Session Management for Multi-Client Access
 *
 * The MCP server runs as a gateway on the Pi, handling connections from multiple
 * coding environments (Claude Code, Cursor, VS Code, etc.) simultaneously.
 *
 * Each client gets its own MCP session:
 * - Session ID assigned at initialization
 * - Subsequent requests routed to the correct transport instance
 * - Clean disconnect handling
 *
 * See /docs/architecture.md for deployment model.
 */
const sessions = new Map<string, StreamableHTTPServerTransport>();

/**
 * Parse allowed origins from environment variable.
 * Example: MCP_ALLOWED_ORIGINS="https://pi.tailnet.ts.net,http://localhost:3000"
 */
function getAllowedOrigins(): string[] | undefined {
    const origins = process.env['MCP_ALLOWED_ORIGINS'];
    if (!origins) return undefined;
    return origins.split(',').map(s => s.trim()).filter(Boolean);
}

export async function setupHttpTransport(server: McpServer, port: number) {
    const app = express();
    app.use(express.json());

    const allowedOrigins = getAllowedOrigins();

    // MCP 2025-11-25 Spec: Streamable HTTP Transport
    // Single endpoint handles POST (client requests), GET (SSE stream), DELETE (session termination)
    app.all("/mcp", async (req: Request, res: Response) => {
        const sessionId = req.get("Mcp-Session-Id");

        // Route to existing session
        if (sessionId) {
            const transport = sessions.get(sessionId);
            if (!transport) {
                // Session not found - client must re-initialize
                return res.status(404).json({
                    jsonrpc: "2.0",
                    error: { code: -32001, message: `Session not found: ${sessionId}` },
                    id: null
                });
            }
            return transport.handleRequest(req, res, req.body);
        }

        // New session (initialization request - no session ID)
        const transport = new StreamableHTTPServerTransport({
            sessionIdGenerator: () => randomUUID(),
            onsessioninitialized: (id: string) => {
                sessions.set(id, transport);
                Logger.info(`Session created: ${id}`, { active_sessions: sessions.size });
            },
            // Note: allowedOrigins is deprecated in SDK but still functional
            // For production, consider external middleware
            ...(allowedOrigins && {
                enableDnsRebindingProtection: true,
                allowedOrigins,
            }),
        });

        // Clean up session on close
        transport.onclose = () => {
            if (transport.sessionId) {
                sessions.delete(transport.sessionId);
                Logger.info(`Session closed: ${transport.sessionId}`, { active_sessions: sessions.size });
            }
        };

        // Cast needed: StreamableHTTPServerTransport implements Transport but SDK types don't reflect this
        await server.connect(transport as Transport);
        return transport.handleRequest(req, res, req.body);
    });

    // Health check endpoint (outside MCP protocol)
    app.get("/health", (_req: Request, res: Response) => {
        res.json({
            status: "ok",
            sessions: sessions.size,
            timestamp: new Date().toISOString()
        });
    });

    app.listen(port, "127.0.0.1", () => {
        Logger.info(`ColdQuery HTTP Server running on http://127.0.0.1:${port}`);
        Logger.info(`MCP endpoint: http://127.0.0.1:${port}/mcp`);
        Logger.info(`Health check: http://127.0.0.1:${port}/health`);
        if (allowedOrigins) {
            Logger.info(`Allowed origins: ${allowedOrigins.join(", ")}`);
        } else {
            Logger.warn("No MCP_ALLOWED_ORIGINS set - origin validation disabled");
        }
    });
}
