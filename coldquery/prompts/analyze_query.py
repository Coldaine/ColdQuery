from fastmcp import Context
from fastmcp.prompts import Message
from coldquery.server import mcp

@mcp.prompt()
async def analyze_query_performance(sql: str, ctx: Context) -> list[Message]:
    """Analyze query performance and suggest optimizations.

    This prompt guides the LLM to:
    1. Run EXPLAIN ANALYZE on the query
    2. Check table statistics
    3. Review indexes
    4. Suggest optimizations
    """
    return [
        Message(
            role="user",
            content=f"""Analyze the performance of this SQL query:

```sql
{sql}
```

Steps:

1. Use `pg_query` with `action="explain"` and `analyze=true` to get the query plan.
2. Use `pg_admin` with `action="stats"` to check table statistics for the tables involved in the query.
3. Use `pg_schema` with `action="describe"` to review the indexes on the tables.
4. Provide optimization recommendations based on the information gathered.
"""
        )
    ]
