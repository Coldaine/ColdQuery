import { describe, it, expect, beforeAll } from "vitest";
import { pgTxHandler } from "../../src/tools/pg-tx.js";
import { PostgresExecutor } from "../../../../shared/executor/postgres.js";
import { SessionManager } from "../../src/session.js";

describe("pg_tx (live)", () => {
    let executor: PostgresExecutor;
    let context: any;

    beforeAll(async () => {
        executor = new PostgresExecutor({
            host: "127.0.0.1",
            port: 5433,
            user: "mcp",
            password: "mcp",
            database: "mcp_test",
        });
        const sessionManager = new SessionManager(executor);
        context = { executor, sessionManager };
    });

    it("should handle begin", async () => {
        const result = await pgTxHandler({
            action: "begin"
        }, context);

        expect(result.status).toBe("success");
        expect(result.session_id).toBeDefined();
        await pgTxHandler({ action: "rollback", session_id: result.session_id }, context);
    });

    it("should handle commit", async () => {
        const beginRes = await pgTxHandler({ action: "begin" }, context);
        const result = await pgTxHandler({
            action: "commit",
            session_id: beginRes.session_id
        }, context);

        expect(result.status).toBe("success");
    });

    it("should handle rollback", async () => {
        const beginRes = await pgTxHandler({ action: "begin" }, context);
        const result = await pgTxHandler({
            action: "rollback",
            session_id: beginRes.session_id
        }, context);

        expect(result.status).toBe("success");
    });

    it("should handle savepoint", async () => {
        const beginRes = await pgTxHandler({ action: "begin" }, context);
        const result = await pgTxHandler({
            action: "savepoint",
            name: "sp1",
            session_id: beginRes.session_id
        }, context);

        expect(result.status).toBe("success");
        await pgTxHandler({ action: "rollback", session_id: beginRes.session_id }, context);
    });

    it("should handle list", async () => {
        const beginRes = await pgTxHandler({ action: "begin" }, context);
        const result = await pgTxHandler({ action: "list" }, context);
        
        expect(result.status).toBe("success");
        expect(result.sessions.some((s: any) => s.id === beginRes.session_id)).toBe(true);
        await pgTxHandler({ action: "rollback", session_id: beginRes.session_id }, context);
    });
});
