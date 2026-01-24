
import { Resource } from "fastmcp";
import { PostgresExecutor } from "@pg-mcp/shared/executor/postgres.js";

export function createSchemaResource(executor: PostgresExecutor): Resource<any> {
    return {
        uri: "postgres://schema",
        name: "Database Schema",
        mimeType: "application/json",
        description: "A JSON representation of the database schema, including tables and columns.",
        async load() {
            const sql = `
                SELECT
                    t.table_schema as schema,
                    t.table_name as table,
                    c.column_name as column,
                    c.data_type as type,
                    c.is_nullable as nullable
                FROM information_schema.tables t
                JOIN information_schema.columns c
                    ON t.table_schema = c.table_schema
                    AND t.table_name = c.table_name
                WHERE t.table_schema NOT IN ('information_schema', 'pg_catalog')
                ORDER BY t.table_schema, t.table_name, c.ordinal_position;
            `;

            const result = await executor.execute(sql, []);

            // Group by schema and table
            const schema: Record<string, Record<string, any[]>> = {};

            for (const row of result.rows) {
                if (!schema[row.schema]) {
                    schema[row.schema] = {};
                }
                if (!schema[row.schema][row.table]) {
                    schema[row.schema][row.table] = [];
                }
                schema[row.schema][row.table].push({
                    name: row.column,
                    type: row.type,
                    nullable: row.nullable === 'YES'
                });
            }

            return {
                text: JSON.stringify(schema, null, 2),
                mimeType: "application/json"
            };
        }
    };
}
