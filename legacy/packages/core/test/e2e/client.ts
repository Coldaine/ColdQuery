import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { spawn, ChildProcess } from "child_process";

export type TestTransportConfig =
    | { type: 'http'; url: string }
    | { type: 'stdio'; command: string; args: string[]; env: NodeJS.ProcessEnv };

export class McpTestClient {
    private client: Client;
    private transport: StreamableHTTPClientTransport | StdioClientTransport | null = null;
    private process: ChildProcess | null = null;

    constructor(private config: TestTransportConfig) {
        this.client = new Client(
            { name: "test-client", version: "1.0.0" },
            { capabilities: {} }
        );
    }

    async connect() {
        if (this.config.type === 'http') {
            // MCP 2025-11-25: Streamable HTTP transport
            // SDK auto-manages MCP-Session-Id header
            this.transport = new StreamableHTTPClientTransport(new URL(this.config.url));
        } else {
            this.process = spawn(this.config.command, this.config.args, {
                env: { ...process.env, ...this.config.env },
                stdio: ['pipe', 'pipe', 'inherit']
            });
            this.transport = new StdioClientTransport({
                in: this.process.stdout!,
                out: this.process.stdin!
            });
        }
        await this.client.connect(this.transport);
    }

    async disconnect() {
        // Capture and clear references atomically to prevent double-close
        const transport = this.transport;
        const proc = this.process;
        this.transport = null;
        this.process = null;

        if (transport) {
            await transport.close();
        }
        if (proc) {
            proc.kill();
        }
    }

    get mcp() {
        return this.client;
    }
}
