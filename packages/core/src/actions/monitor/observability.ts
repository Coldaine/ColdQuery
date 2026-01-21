import { z } from "zod";
import { ActionHandler } from "../../types.js";
import { Logger } from "../../logger.js";

export const ObservabilitySchema = z.object({
    action: z.enum(["connections", "locks", "size", "activity"]).describe("Observability action: connections (by database/state), locks (active), size (tables/database), activity (running queries)"),
    options: z.object({
        database: z.string().optional().describe("Filter by database name (for size action to get specific database size)"),
        schema: z.string().optional().describe("Filter by schema name"),
        include_idle: z.boolean().optional().describe("Include idle connections in activity/connections results (default: false)"),
    }).optional().describe("Filtering options for observability queries"),
});

export const observabilityHandler: ActionHandler<typeof ObservabilitySchema> = {
    schema: ObservabilitySchema,
    handler: async (params, context) => {
        const start = Date.now();
        Logger.info(`[pg_monitor.observability] action: ${params.action}`, { params });

        let sql = "";
        const args: any[] = [];

        switch (params.action) {
            case "activity":
                const activityFilter = params.options?.include_idle ? "" : "WHERE state != 'idle' AND pid != pg_backend_pid()";
                sql = `
                    SELECT 
                        pid, 
                        usename as user, 
                        datname as database, 
                        state, 
                        query, 
                        query_start
                    FROM pg_stat_activity 
                    ${activityFilter}
                    ORDER BY query_start DESC;
                `;
                break;
            case "connections":
                const filter = params.options?.include_idle ? "" : "WHERE state != 'idle'";
                sql = `
                    SELECT 
                        datname as database,
                        count(*) as count,
                        state
                    FROM pg_stat_activity
                    ${filter}
                    GROUP BY datname, state;
                `;
                break;
            case "locks":
                sql = `
                    SELECT 
                        t.relname,
                        l.locktype,
                        l.mode,
                        l.granted,
                        a.query,
                        a.query_start
                    FROM pg_locks l
                    JOIN pg_stat_activity a ON l.pid = a.pid
                    LEFT JOIN pg_class t ON l.relation = t.oid
                    WHERE a.datname = current_database()
                    ORDER BY a.query_start;
                `;
                break;
            case "size":
                if (params.options?.database) {
                    sql = `SELECT pg_size_pretty(pg_database_size($1)) as size`;
                    args.push(params.options.database);
                } else {
                    sql = `
                        SELECT 
                            relname as name,
                            pg_size_pretty(pg_total_relation_size(relid)) as size
                        FROM pg_catalog.pg_statio_user_tables
                        ORDER BY pg_total_relation_size(relid) DESC
                        LIMIT 20;
                    `;
                }
                break;
        }

        try {
            const result = await context.executor.execute(sql, args);
            const elapsed = Date.now() - start;
            Logger.info(`[pg_monitor.observability] completed in ${elapsed}ms`);

            if (params.action === "size" && params.options?.database) {
                return {
                    ...result,
                    rows: [{ name: params.options.database, size: result.rows[0].size }]
                };
            }
            return result;
        } catch (error: any) {
            Logger.error(`[pg_monitor.observability] error: ${error.message}`);
            throw error;
        }
    },
};
