import { z } from "zod";
import { ActionHandler, ActionContext } from "../../types.js";
import { Logger } from "../../logger.js";

export const SettingsSchema = z.object({
    action: z.literal("settings"),
    subaction: z.enum(["list", "get", "set"]).default("list"),
    target: z.string().optional(),
    value: z.string().optional(),
});

export const settingsHandler: ActionHandler<typeof SettingsSchema> = {
    schema: SettingsSchema,
    handler: async (params, context) => {
        const start = Date.now();
        Logger.info(`[pg_admin.settings] params: ${JSON.stringify(params)}`);

        let sql = "";
        const args: any[] = [];

        switch (params.subaction) {
            case "get":
                if (!params.target) throw new Error("Target setting name is required for 'get'");
                sql = "SELECT name, setting, unit, category, short_desc FROM pg_settings WHERE name = $1";
                args.push(params.target);
                break;
            case "set":
                if (!params.target || params.value === undefined) {
                    throw new Error("Both target and value are required for 'set'");
                }
                // Note: SET is session-local. ALTER SYSTEM would be persistent but requires superuser/restart for some.
                // We'll use SET for now as it's safer for a tool.
                sql = `SET ${params.target} = $1`;
                args.push(params.value);
                break;
            case "list":
            default:
                sql = "SELECT name, setting, unit, short_desc FROM pg_settings ORDER BY name LIMIT 50";
                if (params.target) {
                    sql = "SELECT name, setting, unit, short_desc FROM pg_settings WHERE category ILIKE $1 ORDER BY name";
                    args.push(`%${params.target}%`);
                }
                break;
        }

        try {
            const result = await context.executor.execute(sql, args);
            const elapsed = Date.now() - start;
            Logger.info(`[pg_admin.settings] completed in ${elapsed}ms`);

            if (params.subaction === "set") {
                return { status: "success", message: `Setting ${params.target} updated to ${params.value}` };
            }
            return result;
        } catch (error: any) {
            Logger.error(`[pg_admin.settings] error: ${error.message}`);
            throw error;
        }
    },
};
