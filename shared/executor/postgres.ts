import pg from "pg";
import { QueryExecutor, QueryResult, QueryOptions } from "./interface.js";

/**
 * Executor bound to a single dedicated connection (for transactions).
 *
 * WHY A SEPARATE CLASS (not a mode flag on PostgresExecutor):
 * - Clear ownership: this class owns the PoolClient lifecycle
 * - Type safety: can't accidentally mix pool and session operations
 * - Simpler state: no "am I in a session?" checks throughout the code
 */
export class PostgresSessionExecutor implements QueryExecutor {
    constructor(private client: pg.PoolClient) { }

    async execute(sql: string, params?: unknown[], options?: QueryOptions): Promise<QueryResult> {
        // WHY SET statement_timeout (not pg library timeout):
        // - PostgreSQL enforces it server-side (reliable even for long-running queries)
        // - Works for all query types (pg library timeout doesn't)
        // - Session-local: doesn't affect other connections
        // Trade-off: adds 2 roundtrips per query when timeout is specified
        if (options?.timeout_ms) {
            await this.client.query(`SET statement_timeout = ${options.timeout_ms}`);
        }

        try {
            const result = await this.client.query(sql, params);
            return {
                rows: result.rows,
                rowCount: result.rowCount ?? undefined,
                fields: result.fields.map(f => ({ name: f.name, dataTypeID: f.dataTypeID }))
            };
        } finally {
            if (options?.timeout_ms) {
                // WHY .catch(() => {}): If main query failed and connection is dead,
                // reset will also fail. Throwing here would mask the original error.
                // The connection will be discarded anyway.
                await this.client.query("SET statement_timeout = 0").catch(() => { });
            }
        }
    }

    async disconnect(): Promise<void> {
        this.client.release();
    }

    async createSession(): Promise<QueryExecutor> {
        // WHY return this: Idempotent - if you're already in a session, you get the same session.
        // Enables uniform code paths without tracking "do I have a session yet?"
        return this;
    }
}

export class PostgresExecutor implements QueryExecutor {
    private pool: pg.Pool;

    constructor(config: pg.PoolConfig) {
        this.pool = new pg.Pool(config);
    }

    async execute(sql: string, params?: unknown[], options?: QueryOptions): Promise<QueryResult> {
        const client = await this.pool.connect();
        const session = new PostgresSessionExecutor(client);
        try {
            return await session.execute(sql, params, options);
        } finally {
            await session.disconnect();
        }
    }

    async disconnect(): Promise<void> {
        await this.pool.end();
    }

    async createSession(): Promise<QueryExecutor> {
        const client = await this.pool.connect();
        return new PostgresSessionExecutor(client);
    }
}
