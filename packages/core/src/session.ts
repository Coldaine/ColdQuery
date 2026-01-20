import { QueryExecutor } from "@pg-mcp/shared/executor/interface.js";
import { randomUUID } from "crypto";

interface Session {
    id: string;
    executor: QueryExecutor;
    lastActive: number;
    timeoutTimer: NodeJS.Timeout;
}

export class SessionManager {
    private sessions = new Map<string, Session>();
    private readonly TTL_MS = 5 * 60 * 1000; // 5 minutes default TTL

    constructor(private readonly globalExecutor: QueryExecutor) {}

    async createSession(): Promise<string> {
        const id = randomUUID();
        const sessionExecutor = await this.globalExecutor.createSession();
        
        const session: Session = {
            id,
            executor: sessionExecutor,
            lastActive: Date.now(),
            timeoutTimer: this.startTimer(id),
        };

        this.sessions.set(id, session);
        return id;
    }

    getSessionExecutor(id: string): QueryExecutor | undefined {
        const session = this.sessions.get(id);
        if (!session) return undefined;

        // Reset TTL
        session.lastActive = Date.now();
        clearTimeout(session.timeoutTimer);
        session.timeoutTimer = this.startTimer(id);

        return session.executor;
    }

    async closeSession(id: string): Promise<void> {
        const session = this.sessions.get(id);
        if (session) {
            clearTimeout(session.timeoutTimer);
            try {
                // Rollback is implicit if we just disconnect without commit, 
                // but good practice might be to try rollback if still active.
                // However, executor.disconnect() usually releases the client 
                // which triggers a rollback in PG if in transaction.
                await session.executor.disconnect();
            } catch (error) {
                console.error(`Error closing session ${id}:`, error);
            }
            this.sessions.delete(id);
        }
    }

    private startTimer(id: string): NodeJS.Timeout {
        return setTimeout(() => {
            console.error(`Session ${id} timed out. Closing.`);
            this.closeSession(id);
        }, this.TTL_MS);
    }
}
