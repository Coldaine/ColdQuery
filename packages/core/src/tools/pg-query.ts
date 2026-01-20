import { z } from "zod";
import { ActionRegistry, ActionContext, ToolDefinition } from "../types.js";
import { readHandler } from "../actions/query/read.js";
import { writeHandler } from "../actions/query/write.js";
import { explainHandler } from "../actions/query/explain.js";
import { transactionHandler } from "../actions/query/transaction.js";

const queryRegistry: ActionRegistry = {
    read: readHandler,
    write: writeHandler,
    explain: explainHandler,
    transaction: transactionHandler,
};

export const PgQuerySchema = z.discriminatedUnion("action", [
    readHandler.schema,
    writeHandler.schema,
    explainHandler.schema,
    transactionHandler.schema,
]);

export async function pgQueryHandler(params: z.infer<typeof PgQuerySchema>, context: ActionContext) {
    const handler = queryRegistry[params.action];
    if (!handler) {
        throw new Error(`Unknown action: ${params.action}`);
    }
    return await handler.handler(params, context);
}

export const pgQueryTool: ToolDefinition = {
    name: "pg_query",
    config: {
        description: "Execute SQL queries for data manipulation (DML) and raw read/write operations",
        inputSchema: PgQuerySchema,
    },
    handler: (context) => (params) => pgQueryHandler(params, context),
};
