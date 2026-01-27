import { SessionManager } from "../session.js";

export function wrapResponse(result: any, params: any, toolName: string, sessionManager: SessionManager) {
    const sessionId = params.session_id;
    if (!sessionId) {
        // If it's a 'begin' action, it returns session_id in the result
        if (toolName === "pg_tx" && params.action === "begin" && result.session_id) {
            return {
                ...result,
                active_session: {
                    id: result.session_id,
                    hint: "Use this session_id for subsequent transactional queries."
                }
            };
        }
        return result;
    }

    const sessions = sessionManager.listSessions();
    const currentSession = sessions.find(s => s.id === sessionId);
    
    if (!currentSession) return result;

    // Check if we should echo based on the plan:
    // 1. Write operations (action: 'write', 'ddl', 'set', etc.)
    // 2. Near expiry (< 5 minutes)
    
    const isWriteOp = 
        (toolName === "pg_query" && (params.action === "write" || params.action === "transaction")) ||
        (toolName === "pg_schema" && (params.action === "create" || params.action === "alter" || params.action === "drop")) ||
        (toolName === "pg_admin" && params.subaction === "set");

    const expiresInMinutes = parseInt(currentSession.expires_in);
    const isNearExpiry = expiresInMinutes < 5;

    if (isWriteOp || isNearExpiry) {
        return {
            ...result,
            active_session: {
                id: currentSession.id,
                expires_in: currentSession.expires_in,
                hint: isNearExpiry 
                    ? "Warning: Session expiring soon. Commit your work shortly." 
                    : `Active transaction: ${currentSession.id}`
            }
        };
    }

    return result;
}
