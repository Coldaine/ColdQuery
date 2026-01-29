from fastmcp import Context
from fastmcp.prompts import Message
from coldquery.server import mcp

@mcp.prompt()
async def debug_lock_contention(ctx: Context) -> list[Message]:
    """Debug lock contention issues.

    Guides the LLM to investigate blocking queries and locks.
    """
    return [
        Message(
            role="user",
            content="""Investigate database lock contention:

1. Use `pg_monitor` with `action="locks"` to see current locks.
2. Use `pg_monitor` with `action="activity"` to see blocking queries.
3. Use `pg_tx` with `action="list"` to see active transactions.
4. Provide recommendations for resolving contention based on the findings.
"""
        )
    ]
