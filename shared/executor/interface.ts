export interface QueryResult {
    rows: any[];
    rowCount?: number;
    fields?: { name: string; dataTypeID: number }[];
}

export interface QueryOptions {
    timeout_ms?: number;
}

/**
 * Abstraction over database connections that enables testability and proper transaction handling.
 *
 * WHY THIS INTERFACE EXISTS:
 * - Provides a clean, async/await interface for SQL execution
 * - Decouples business logic from the pg library
 * - Supports both simple queries and transactional sessions
 * - Hides footgun methods like PoolClient.release() that cause connection leaks if misused
 * - Provides a uniform API whether you're using pooled or session-dedicated connections
 *
 * WHY createSession() RETURNS QueryExecutor (not a different type):
 * - Enables uniform code paths: callers don't need to track whether they have a pool or session
 * - A session calling createSession() returns itself (idempotent) - no accidental nesting
 */
export interface QueryExecutor {
    execute(sql: string, params?: unknown[], options?: QueryOptions): Promise<QueryResult>;
    disconnect(destroy?: boolean): Promise<void>;

    /**
     * Returns an executor bound to a single dedicated connection.
     *
     * WHY THIS IS NEEDED:
     * PostgreSQL transactions require all statements on the same connection.
     * Connection pools return different connections per query, breaking transactions.
     * Call createSession() before BEGIN, use that session for all tx operations.
     */
    createSession(): Promise<QueryExecutor>;
}
