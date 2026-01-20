export type LogLevel = "info" | "warn" | "error" | "debug";

export interface LogEntry {
    timestamp: string;
    level: LogLevel;
    message: string;
    context?: Record<string, unknown>;
}

/**
 * Structured JSON logger that writes to stderr.
 *
 * WHY ALL LOGS GO TO console.error (stderr), NOT console.log (stdout):
 * MCP servers communicate with clients via stdout using JSON-RPC.
 * Any stray console.log() corrupts the protocol stream and breaks communication.
 * stdout = sacred (protocol only), stderr = humans (logs, diagnostics).
 *
 * This is also why ESLint is configured to forbid console.log in this codebase.
 */
export class Logger {
    private static format(level: LogLevel, message: string, context?: Record<string, unknown>): string {
        const entry: any = {
            timestamp: new Date().toISOString(),
            level,
            message,
        };
        if (context) {
            entry.context = context;
        }
        return JSON.stringify(entry);
    }

    static info(message: string, context?: Record<string, unknown>) {
        console.error(this.format("info", message, context));
    }

    static warn(message: string, context?: Record<string, unknown>) {
        console.error(this.format("warn", message, context));
    }

    static error(message: string, context?: Record<string, unknown>) {
        console.error(this.format("error", message, context));
    }

    static debug(message: string, context?: Record<string, unknown>) {
        if (process.env['DEBUG']) {
            console.error(this.format("debug", message, context));
        }
    }
}
