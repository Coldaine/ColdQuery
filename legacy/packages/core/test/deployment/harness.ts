import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";

/**
 * A test harness that spawns the actual MCP server process.
 * This ensures we are testing the "binary" (or at least the entry point) 
 * and not just internal library functions.
 */
export class McpServerTestHarness {
    private transport: StdioClientTransport | null = null;
    private client: Client | null = null;

    constructor(
        private env: Record<string, string>,
        private serverPath: string = "packages/core/src/server.ts"
    ) {}

    async start() {
        // StdioClientTransport handles spawning the process internally
        this.transport = new StdioClientTransport({
            command: "npx",
            args: ["tsx", this.serverPath],
            env: { ...process.env as Record<string, string>, ...this.env },
            stderr: "inherit", // Inherit stderr for logs
        });

        this.client = new Client(
            { name: "test-client", version: "1.0.0" },
            { capabilities: {} }
        );

        await this.client.connect(this.transport);
    }

    async stop() {
        if (this.client) {
            await this.client.close();
        }
        // Transport is closed automatically when client closes
    }

    get mcpClient() {
        if (!this.client) throw new Error("Server not started");
        return this.client;
    }
}
