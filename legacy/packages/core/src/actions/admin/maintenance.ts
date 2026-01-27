import { z } from "zod";
import { ActionHandler } from "../../types.js";

export const MaintenanceSchema = z.object({
    action: z.enum(["vacuum", "analyze", "reindex"]).describe("Maintenance action: vacuum (reclaim storage), analyze (update stats), reindex (rebuild indexes)"),
    target: z.string().optional().describe("Table name to operate on. If omitted, applies to all tables (except reindex which requires a target)"),
    options: z.object({
        full: z.boolean().optional().describe("Use VACUUM FULL (completely rewrites table, requires exclusive lock)"),
        verbose: z.boolean().optional().describe("Output detailed progress information"),
        analyze: z.boolean().optional().describe("Run ANALYZE after VACUUM to update statistics"),
    }).optional().describe("Maintenance operation options"),
});

export const maintenanceHandler: ActionHandler<typeof MaintenanceSchema> = {
    schema: MaintenanceSchema,
    handler: async (params, context) => {
        let sql = "";
        const target = params.target ? `"${params.target}"` : "";

        switch (params.action) {
            case "vacuum":
                const vacuumOpts = [];
                if (params.options?.full) vacuumOpts.push("FULL");
                if (params.options?.verbose) vacuumOpts.push("VERBOSE");
                if (params.options?.analyze) vacuumOpts.push("ANALYZE");
                const vacuumOptStr = vacuumOpts.length > 0 ? `(${vacuumOpts.join(", ")})` : "";
                sql = `VACUUM ${vacuumOptStr} ${target}`.trim();
                break;
            case "analyze":
                const analyzeOpts = [];
                if (params.options?.verbose) analyzeOpts.push("VERBOSE");
                const analyzeOptStr = analyzeOpts.join(" ");
                sql = `ANALYZE ${analyzeOptStr} ${target}`.trim();
                break;
            case "reindex":
                sql = `REINDEX TABLE ${target}`.trim();
                break;
        }

        const result = await context.executor.execute(sql);
        return {
            ...result,
            status: "success"
        };
    },
};
