import pg from "pg";
import { QueryExecutor, QueryResult, QueryOptions } from "./interface.js";

export class PostgresSessionExecutor implements QueryExecutor {
    constructor(private client: pg.PoolClient) { }

    async execute(sql: string, params?: unknown[], options?: QueryOptions): Promise<QueryResult> {
        if (options?.timeout_ms) {
            await this.client.query(`SET statement_timeout = ${options.timeout_ms}`);
        }

        try {
            // Use object form to ensure prepared statement behavior
            // Postgres.js uses prepared statements when values are provided, but this is explicit.
            const result = await this.client.query({
                text: sql,
                values: params as any[],
            });
            
            const queryResult: QueryResult = {
                rows: result.rows,
                fields: result.fields.map(f => ({ name: f.name, dataTypeID: f.dataTypeID }))
            };
            
            if (result.rowCount !== null && result.rowCount !== undefined) {
                queryResult.rowCount = result.rowCount;
            }
            
            return queryResult;
        } finally {
            if (options?.timeout_ms) {
                await this.client.query("SET statement_timeout = 0").catch(() => { });
            }
        }
    }

    async disconnect(destroy = false): Promise<void> {
        // If destroy is true, the client is removed from the pool (preventing dirty state leak)
        // This is critical for session cleanup after transactions.
        this.client.release(destroy);
    }

    async createSession(): Promise<QueryExecutor> {
        return this; // Already in a session
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

    async disconnect(_destroy?: boolean): Promise<void> {
        // destroy param is irrelevant for pool shutdown
        await this.pool.end();
    }

    async createSession(): Promise<QueryExecutor> {
        const client = await this.pool.connect();
        return new PostgresSessionExecutor(client);
    }
}
