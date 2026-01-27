import { z } from "zod";
import { ActionHandler, resolveExecutor } from "../../types.js";
import { sanitizeIdentifier } from "@pg-mcp/shared/security/identifiers.js";
import { QueryExecutor } from "@pg-mcp/shared/executor/interface.js";

export const DDLSchema = z.object({
    action: z.enum(["create", "alter", "drop"]).describe("DDL action: create new objects, alter existing ones, or drop them"),
    target: z.enum(["table", "index", "view", "function", "trigger", "schema"]).describe("Type of object to modify. Implemented: table, index, view for create; table for alter; table, view, index, schema for drop"),
    name: z.string().describe("Name of the object to create/alter/drop"),
    schema: z.string().optional().describe("Target schema name (omit to use 'public')"),
    session_id: z.string().optional().describe("Session ID for transactional DDL. Required for schema changes within a transaction."),
    autocommit: z.boolean().optional().describe("Set to true to execute DDL immediately without a transaction. Required if session_id is not provided."),
    definition: z.string().optional().describe("Object definition SQL (e.g., 'id SERIAL PRIMARY KEY, name TEXT' for table, 'SELECT ...' for view)"),
    options: z.object({
        cascade: z.boolean().optional().describe("Use CASCADE to drop dependent objects (for drop action)"),
        if_exists: z.boolean().optional().describe("Add IF EXISTS to prevent error if object doesn't exist (for drop)"),
        if_not_exists: z.boolean().optional().describe("Add IF NOT EXISTS to prevent error if object already exists (for create)"),
    }).optional().describe("DDL options for conditional execution"),
});

/**
 * DDL Handler for Schema Mutations.
 * 
 * WHY SESSION SUPPORT IN DDL:
 * PostgreSQL supports transactional DDL. This is critical for AI agents 
 * performing complex refactorings (e.g. adding a column and populating data).
 * If the data migration fails, we want the schema change to rollback as well.
 */
export const ddlHandler: ActionHandler<typeof DDLSchema> = {
    schema: DDLSchema,
    handler: async (params, context) => {
        // Default-Deny Policy: Prevent accidental non-transactional DDL
        if (!params.session_id && !params.autocommit) {
            throw new Error(
                "Safety Check Failed: DDL operations require either a valid 'session_id' (for transactions) or 'autocommit: true' (for immediate execution). " +
                "Example: { action: 'drop', target: 'table', name: 'old_table', autocommit: true }"
            );
        }

        // Resolve executor - if session_id is provided, we use the dedicated connection
        const executor = resolveExecutor(context, params.session_id);

        switch (params.action) {
            case "create":
                return await handleCreate(params, executor);
            case "alter":
                return await handleAlter(params, executor);
            case "drop":
                return await handleDrop(params, executor);
            default:
                throw new Error(`DDL action "${params.action}" not implemented yet`);
        }
    },
};

// ... existing handleCreate/handleAlter/handleDrop functions updated to take executor instead of context ...
async function handleCreate(params: z.infer<typeof DDLSchema>, executor: QueryExecutor) {
    const safeName = sanitizeIdentifier(params.name);
    const schemaPrefix = params.schema ? `${sanitizeIdentifier(params.schema)}.` : "";
    let sql = "";

    switch (params.target) {
        case "table":
            if (!params.definition) throw new Error("Definition required for create table");
            const ifNotExists = params.options?.if_not_exists ? "IF NOT EXISTS " : "";
            sql = `CREATE TABLE ${ifNotExists}${schemaPrefix}${safeName} (${params.definition})`;
            break;
        case "index":
            if (!params.definition) throw new Error("Definition required for create index (target table)");
            sql = `CREATE INDEX ${safeName} ON ${schemaPrefix}${params.definition}`;
            break;
        case "view":
            if (!params.definition) throw new Error("Definition required for create view (select query)");
            sql = `CREATE VIEW ${schemaPrefix}${safeName} AS ${params.definition}`;
            break;
        default:
            throw new Error(`Create target "${params.target}" not implemented yet`);
    }

    return await executor.execute(sql);
}

async function handleAlter(params: z.infer<typeof DDLSchema>, executor: QueryExecutor) {
    const safeName = sanitizeIdentifier(params.name);
    const schemaPrefix = params.schema ? `${sanitizeIdentifier(params.schema)}.` : "";
    let sql = "";

    switch (params.target) {
        case "table":
            if (!params.definition) throw new Error("Definition required for alter table");
            sql = `ALTER TABLE ${schemaPrefix}${safeName} ${params.definition}`;
            break;
        default:
            throw new Error(`Alter target "${params.target}" not implemented yet`);
    }

    return await executor.execute(sql);
}

async function handleDrop(params: z.infer<typeof DDLSchema>, executor: QueryExecutor) {
    const safeName = sanitizeIdentifier(params.name);
    const schemaPrefix = params.schema ? `${sanitizeIdentifier(params.schema)}.` : "";
    const ifExists = params.options?.if_exists ? "IF EXISTS " : "";
    const cascade = params.options?.cascade ? " CASCADE" : "";

    let sql = "";
    switch (params.target) {
        case "table":
            sql = `DROP TABLE ${ifExists}${schemaPrefix}${safeName}${cascade}`;
            break;
        case "view":
            sql = `DROP VIEW ${ifExists}${schemaPrefix}${safeName}${cascade}`;
            break;
        case "index":
            sql = `DROP INDEX ${ifExists}${schemaPrefix}${safeName}${cascade}`;
            break;
        case "schema":
            sql = `DROP SCHEMA ${ifExists}${safeName}${cascade}`;
            break;
        default:
            throw new Error(`Drop target "${params.target}" not implemented yet`);
    }

    return await executor.execute(sql);
}
