import { QueryExecutor } from "@pg-mcp/shared/executor/interface.js";
import { randomUUID } from "crypto";
import { Logger } from "./logger.js";

interface Session {
    id: string;
    executor: QueryExecutor;
    lastActive: number;
    timeoutTimer: NodeJS.Timeout;
}

export class SessionManager {
    private sessions = new Map<string, Session>();
    // 30 minutes default TTL - balanced for agentic workflows
    private TTL_MS = 30 * 60 * 1000; 
    private MAX_SESSIONS = 10;

    constructor(private readonly globalExecutor: QueryExecutor, config?: { maxSessions?: number; ttlMs?: number }) {
        if (config?.maxSessions) this.MAX_SESSIONS = config.maxSessions;
        if (config?.ttlMs) this.TTL_MS = config.ttlMs;
    }

    /**
     * Creates a new session with a dedicated database connection.
     * Returns the unique session ID.
     */
    async createSession(): Promise<string> {
        if (this.sessions.size >= this.MAX_SESSIONS) {
            throw new Error(`Maximum session limit (${this.MAX_SESSIONS}) reached. Please close an existing session before creating a new one.`);
        }

        const id = randomUUID();
        const sessionExecutor = await this.globalExecutor.createSession();

        const session: Session = {
            id,
            executor: sessionExecutor,
            lastActive: Date.now(),
            timeoutTimer: null as unknown as NodeJS.Timeout,
        };

        // Atomic check and set: ensure we didn't exceed limit while awaiting connection
        if (this.sessions.size >= this.MAX_SESSIONS) {
            await sessionExecutor.disconnect(true);
            throw new Error(`Maximum session limit (${this.MAX_SESSIONS}) reached. Please close an existing session before creating a new one.`);
        }

        this.sessions.set(id, session);
        session.timeoutTimer = this.startTimer(id);
        return id;
    }

    /**
     * Retrieves the executor for a given session ID.
     * Resets the TTL timer on access.
     */
    getSessionExecutor(id: string): QueryExecutor | undefined {
        const session = this.sessions.get(id);
        if (!session) return undefined;

        // Reset TTL
        session.lastActive = Date.now();
        clearTimeout(session.timeoutTimer);
        session.timeoutTimer = this.startTimer(id);

        return session.executor;
    }

    /**
     * Closes a session, releasing the connection and ensuring cleanup.
     * If a transaction was open, the connection release will trigger an automatic rollback.
     */
    async closeSession(id: string): Promise<void> {
        const session = this.sessions.get(id);
        if (session) {
            clearTimeout(session.timeoutTimer);
            try {
                // Pass true to destroy the connection, ensuring no session state leaks
                await session.executor.disconnect(true);
            } catch (error: any) {
                Logger.error(`[SessionManager] Error closing session ${id}`, { error: error.message });
            }
            this.sessions.delete(id);
        }
    }

    /**
     * Returns a list of active sessions with metadata.
     */
    listSessions() {
        const now = Date.now();
        return Array.from(this.sessions.values()).map(s => {
            // Correct logic: We want age since creation or last active? Plan says 'age', implied since start or last usage.
            // Let's assume 'age' means how long since it was LAST ACTIVE for now to track idleness, 
            // OR if we tracked 'startedAt' we could show total age. 
            // The plan showed "age: 2m 30s", "expires_in: 27m 30s". 
            // This implies age = time since last activity (idle time) or total lifespan.
            // Let's use 'idle_time' for clarity as that's what matters for TTL.
            // Wait, previous code didn't track startedAt. I'll just use idle time.
            
            const idleTimeMs = now - s.lastActive;
            const expiresAt = s.lastActive + this.TTL_MS;
            
            return {
                id: s.id,
                idle_time: `${Math.round(idleTimeMs / 1000)}s`,
                expires_in: `${Math.round((expiresAt - now) / 60000)}m`,
            };
        });
    }

    private startTimer(id: string): NodeJS.Timeout {
        return setTimeout(() => {
            Logger.warn(`[SessionManager] Session ${id} timed out. Auto-closing to prevent leaks.`);
            this.closeSession(id);
        }, this.TTL_MS);
    }
}