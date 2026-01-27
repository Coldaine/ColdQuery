import { z } from "zod";
import { ActionHandler, resolveExecutor } from "../../types.js";

export const DescribeSchema = z.object({
    action: z.literal("describe").describe("Describe action - get detailed structure of a database object"),
    target: z.enum(["table", "view", "function", "trigger", "sequence"]).describe("Type of object to describe. Currently implemented: table"),
    name: z.string().describe("Name of the object to describe"),
    schema: z.string().optional().describe("Schema where the object resides (defaults to 'public')"),
    session_id: z.string().optional().describe("Session ID. Required to describe objects created in uncommitted transactions."),
});

/**
 * Describe handler for schema introspection.
 * 
 * WHY SESSION SUPPORT:
 * An AI agent might create a table inside a transaction and then immediately 
 * want to describe it to verify its structure. Without session support, 
 * 'describe' would look at the global state and fail to find the uncommitted table.
 */
export const describeHandler: ActionHandler<typeof DescribeSchema> = {
    schema: DescribeSchema,
    handler: async (params, context) => {
        const executor = resolveExecutor(context, params.session_id);
        switch (params.target) {
            case "table":
                return await describeTable(params, executor);
            default:
                throw new Error(`Describe target "${params.target}" not implemented yet`);
        }
    },
};

async function describeTable(params: z.infer<typeof DescribeSchema>, executor: any) {
    const schema = params.schema || "public";

    // Get columns
    const columnsSql = `
        SELECT 
            column_name as name,
            data_type as type,
            is_nullable as nullable,
            column_default as default_value
        FROM information_schema.columns
        WHERE table_schema = $1 AND table_name = $2
        ORDER BY ordinal_position;
    `;
    const columns = await executor.execute(columnsSql, [schema, params.name]);

    // Get indexes
    const indexesSql = `
        SELECT indexname as name, indexdef as definition
        FROM pg_indexes
        WHERE schemaname = $1 AND tablename = $2;
    `;
    const indexes = await executor.execute(indexesSql, [schema, params.name]);

    return {
        name: params.name,
        schema,
        columns: columns.rows,
        indexes: indexes.rows,
    };
}
