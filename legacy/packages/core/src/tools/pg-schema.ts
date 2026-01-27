import { z } from "zod";
import { ActionRegistry, ActionContext, ToolDefinition } from "../types.js";
import { listHandler } from "../actions/schema/list.js";
import { describeHandler } from "../actions/schema/describe.js";
import { ddlHandler } from "../actions/schema/ddl.js";

const schemaRegistry: ActionRegistry = {
    list: listHandler,
    describe: describeHandler,
    create: ddlHandler,
    alter: ddlHandler,
    drop: ddlHandler,
};

export const PgSchemaToolSchema = z.object({
    action: z.enum(["list", "describe", "create", "alter", "drop"]).describe("Action to perform on schema objects"),
    target: z.enum(["database", "schema", "table", "column", "index", "view", "function", "trigger", "sequence", "constraint"]).describe("Target object type"),
    schema: z.string().optional().describe("Schema name (filter for list, or target schema for others)"),
    name: z.string().optional().describe("Object name (required for describe, create, alter, drop)"),
    definition: z.string().optional().describe("SQL definition body (for create/alter, e.g. column defs or view query)"),
    table: z.string().optional().describe("Parent table name (filter for list triggers/constraints)"),
    session_id: z.string().optional().describe("Session ID for transactional operations"),
    autocommit: z.boolean().optional().describe("Execute DDL immediately (required if no session_id provided)"),
    options: z.object({
        // List options
        include_sizes: z.boolean().optional().describe("Include table sizes in list output"),
        include_materialized: z.boolean().optional().describe("Include materialized views when listing views"),
        limit: z.number().optional().describe("Max results to return (list)"),
        offset: z.number().optional().describe("Pagination offset (list)"),
        // DDL options
        cascade: z.boolean().optional().describe("Use CASCADE to drop dependent objects (drop)"),
        if_exists: z.boolean().optional().describe("Add IF EXISTS (drop)"),
        if_not_exists: z.boolean().optional().describe("Add IF NOT EXISTS (create)"),
    }).optional().describe("Options for list or DDL operations"),
});

export async function pgSchemaHandler(params: any, context: ActionContext) {
    const handler = schemaRegistry[params.action];
    if (!handler) {
        throw new Error(`Unknown action: ${params.action}`);
    }
    return await handler.handler(params, context);
}

export const pgSchemaTool: ToolDefinition = {
    name: "pg_schema",
    config: {
        description: `Manage database structure and schema objects (DDL).

Actions:
  • list: Enumerate schemas, tables, views, functions, triggers, sequences, constraints (read-only)
  • describe: Get detailed structure of tables (columns, indexes) (read-only)
  • create: Create new tables, indexes, views (requires session_id OR autocommit:true)
  • alter: Modify existing tables (requires session_id OR autocommit:true)
  • drop: Remove objects with optional CASCADE (requires session_id OR autocommit:true)

Safety: DDL mutations (create/alter/drop) use Default-Deny policy.
Without session_id or autocommit:true, DDL will fail with a safety error.

Examples:
  {"action": "list", "target": "table"}
  {"action": "describe", "target": "table", "name": "users"}
  {"action": "create", "target": "table", "name": "logs", "definition": "id SERIAL PRIMARY KEY", "autocommit": true}`,
        inputSchema: PgSchemaToolSchema,
        destructiveHint: true, // Contains create/alter/drop actions that can modify schema
    },
    handler: (context) => (params) => pgSchemaHandler(params, context),
};
