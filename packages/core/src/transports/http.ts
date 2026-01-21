import { SSEServerTransport } from "@modelcontextprotocol/sdk/server/sse.js";
import express, { Request, Response } from "express";
import { Logger } from "../logger.js";
import { createMcpServer } from "../server.js";

/**
 * Session Management for Multi-Client Access
 *
 * WHY SSE TRANSPORT (instead of generic HTTP):
 * - The standard MCP HTTP transport uses a complex initialization handshake that is 
 *   flaky on high-latency or multiple-client networks (like Tailscale/Pi).
 * - SSEServerTransport provides a stable, one-way event stream for server-to-client
 *   push, while use standard POST for client-to-server.
 *
 * WHY FACTORY PATTERN (createMcpServer per connection):
 * - The @modelcontextprotocol/sdk McpServer maintains internal state per transport.
 * - By creating a new McpServer instance per SSE session, we ensure:
 *   - Perfect session isolation (clients don't see each other's state)
 *   - Clean registration log for every new connection
 *   - Reliable 'initialization' handshake for every client
 *   - Automatic cleanup when the SSE connection drops
 */
const sessions = new Map<string, { transport: SSEServerTransport; server: any }>();

export async function setupHttpTransport(port: number) {
    const app = express();
    app.use(express.json());

    // GET /mcp: Establish SSE connection
    app.get("/mcp", async (req: Request, res: Response) => {
        Logger.info(`New SSE connection request from ${req.ip}`);
        
        // Create new transport for this session
        // endpoint is /mcp because client will POST to /mcp?sessionId=...
        const transport = new SSEServerTransport("/mcp", res);
        const server = createMcpServer();

        // Store session
        sessions.set(transport['sessionId'], { transport, server });
        Logger.info(`Session created: ${transport['sessionId']}`, { active_sessions: sessions.size });

        // Clean up on close
        transport.onclose = () => {
             sessions.delete(transport['sessionId']);
             Logger.info(`Session closed: ${transport['sessionId']}`, { active_sessions: sessions.size });
        };

        await server.connect(transport);
    });

    // POST /mcp: Handle JSON-RPC messages
    app.post("/mcp", async (req: Request, res: Response) => {
        const sessionId = req.query['sessionId'] as string;
        if (!sessionId) {
            return res.status(400).send("Missing sessionId query parameter");
        }

        const session = sessions.get(sessionId);
        if (!session) {
            return res.status(404).send("Session not found");
        }

        return await session.transport.handlePostMessage(req, res, req.body);
    });

    // Health check endpoint (outside MCP protocol)
    app.get("/health", (_req: Request, res: Response) => {
        res.json({
            status: "ok",
            sessions: sessions.size,
            timestamp: new Date().toISOString()
        });
    });

    const host = process.env['HOST'] || "0.0.0.0";
    app.listen(port, host, () => {
        Logger.info(`ColdQuery HTTP Server running on http://${host}:${port}`);
        Logger.info(`MCP endpoint: http://${host}:${port}/mcp`);
        Logger.info(`Health check: http://${host}:${port}/health`);
    });
}
