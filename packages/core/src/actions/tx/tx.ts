import { z } from "zod";
import { ActionHandler } from "../../types.js";
import { sanitizeIdentifier } from "@pg-mcp/shared/security/identifiers.js";

export const TxSchema = z.object({
    action: z.enum(["begin", "commit", "rollback", "savepoint", "release"]),
    name: z.string().optional(),
    options: z.object({
        isolation_level: z.enum(["read_committed", "repeatable_read", "serializable"]).optional(),
    }).optional(),
});

export const txHandler: ActionHandler<typeof TxSchema> = {
    schema: TxSchema,
    handler: async (params, context) => {
        let sql = "";

        switch (params.action) {
            case "begin":
                const isoLevel = params.options?.isolation_level
                    ? ` ISOLATION LEVEL ${params.options.isolation_level.replace("_", " ").toUpperCase()}`
                    : "";
                sql = `BEGIN${isoLevel}`;
                break;
            case "commit":
                sql = "COMMIT";
                break;
            case "rollback":
                sql = "ROLLBACK";
                break;
            case "savepoint":
                if (!params.name) throw new Error("Savepoint name is required");
                sql = `SAVEPOINT ${sanitizeIdentifier(params.name)}`;
                break;
            case "release":
                if (!params.name) throw new Error("Savepoint name is required for release");
                sql = `RELEASE SAVEPOINT ${sanitizeIdentifier(params.name)}`;
                break;
        }

        const result = await context.executor.execute(sql);
        return {
            ...result,
            status: "success"
        };
    },
};
