import { z } from "zod";
import { ActionHandler, ActionContext } from "../../types.js";
import { sanitizeIdentifier } from "@pg-mcp/shared/security/identifiers.js";

/**
 * DDL (Data Definition Language) handler for schema modifications.
 *
 * SECURITY MODEL:
 * - params.name and params.schema are sanitized via sanitizeIdentifier()
 * - params.definition accepts raw SQL (see below for why)
 *
 * WHY params.definition ACCEPTS RAW SQL:
 * PostgreSQL column definitions are complex (constraints, defaults, generated columns,
 * foreign keys, CHECK expressions, etc.). Parsing and validating all possible DDL syntax:
 * - Would be error-prone (always incomplete vs actual PostgreSQL grammar)
 * - Creates maintenance burden (new PostgreSQL versions add syntax)
 * - Limits users (can't use features we didn't implement)
 *
 * TRUST MODEL:
 * This tool assumes the AI generates valid DDL. It is NOT designed for untrusted
 * human input. If accepting user input for definitions, validate in your app first.
 */
export const DDLSchema = z.object({
    action: z.enum(["create", "alter", "drop"]),
    target: z.enum(["table", "index", "view", "function", "trigger", "schema"]),
    name: z.string(),
    schema: z.string().optional(),
    definition: z.string().optional(),
    options: z.object({
        cascade: z.boolean().optional(),
        if_exists: z.boolean().optional(),
        if_not_exists: z.boolean().optional(),
    }).optional(),
});

export const ddlHandler: ActionHandler<typeof DDLSchema> = {
    schema: DDLSchema,
    handler: async (params, context) => {
        switch (params.action) {
            case "create":
                return await handleCreate(params, context);
            case "alter":
                return await handleAlter(params, context);
            case "drop":
                return await handleDrop(params, context);
            default:
                throw new Error(`DDL action "${params.action}" not implemented yet`);
        }
    },
};

async function handleCreate(params: z.infer<typeof DDLSchema>, context: ActionContext) {
    const safeName = sanitizeIdentifier(params.name);
    const schemaPrefix = params.schema ? `${sanitizeIdentifier(params.schema)}.` : "";
    let sql = "";

    switch (params.target) {
        case "table":
            if (!params.definition) throw new Error("Definition required for create table");
            const ifNotExists = params.options?.if_not_exists ? "IF NOT EXISTS " : "";
            // Note: params.definition is raw SQL (column definitions) and cannot be easily sanitized
            // without a full SQL parser. We assume the user has validated the schema definition.
            sql = `CREATE TABLE ${ifNotExists}${schemaPrefix}${safeName} (${params.definition})`;
            break;
        case "index":
            if (!params.definition) throw new Error("Definition required for create index (target table)");
            // For index, params.definition is usually "table_name(column)" or just "table_name"
            // We'll treat it as raw to allow complex index definitions, but we sanitize the index name
            sql = `CREATE INDEX ${safeName} ON ${schemaPrefix}${params.definition}`;
            break;
        case "view":
            if (!params.definition) throw new Error("Definition required for create view (select query)");
            sql = `CREATE VIEW ${schemaPrefix}${safeName} AS ${params.definition}`;
            break;
        default:
            throw new Error(`Create target "${params.target}" not implemented yet`);
    }

    return await context.executor.execute(sql);
}

async function handleAlter(params: z.infer<typeof DDLSchema>, context: ActionContext) {
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

    return await context.executor.execute(sql);
}

async function handleDrop(params: z.infer<typeof DDLSchema>, context: ActionContext) {
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

    return await context.executor.execute(sql);
}
