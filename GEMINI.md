# Gemini Context for ColdQuery

**Updated:** January 2026
**Project:** ColdQuery - Secure PostgreSQL MCP Server
**Tech Stack:** Python 3.12+, FastMCP 3.0+, asyncpg, Pydantic

---

## 🧠 Core Architecture (CRITICAL)

### 1. The "App vs Server" Split
To prevent Python module shadowing and circular imports, we strictly separate the application definition from the entry point.

*   **`coldquery/app.py`**: **SINGLE SOURCE OF TRUTH.** Defines the `mcp = FastMCP(...)` instance and lifespan.
*   **`coldquery/server.py`**: **ENTRY POINT.** Imports `mcp` from `app.py` and registers tools.
*   **Tools/Resources**: Must import `mcp` from `coldquery.app`, NEVER from `coldquery.server`.

### 2. Default-Deny Security
We operate on a "Trust No One" model for database writes.
*   **Read-Only**: Allowed by default.
*   **Writes/DDL**: **FORBIDDEN** unless explicitly authorized via `session_id` (transactional) or `autocommit=True` (explicit override).
*   **Implementation**: Use `coldquery.security.access_control.require_write_access()`.

### 3. Dependency Injection
We use FastMCP's dependency injection system.
*   **Context**: `ActionContext` is injected via `lifespan`.
*   **Usage**:
    ```python
    @mcp.tool()
    async def my_tool(ctx: ActionContext = CurrentActionContext()):
        await ctx.executor.execute(...)
    ```

---

## 🛠️ Development Workflow

### Verification Suite
Always run the full suite before finishing a task.

1.  **Lint & Format**:
    ```powershell
    ruff check --fix coldquery/ tests/
    ruff format coldquery/ tests/
    ```
2.  **Type Check**:
    ```powershell
    mypy coldquery/
    ```
3.  **Tests**:
    ```powershell
    # Unit tests (Fast, mocks)
    pytest tests/unit/ -v

    # Integration tests (Requires DB on port 5433)
    # Ensure docker-compose up -d is running
    pytest tests/integration/ -v
    ```

### Pre-Commit
This project uses `pre-commit` hooks.
*   **Install**: `pip install pre-commit && pre-commit install`
*   **Run Manual**: `pre-commit run --all-files`

---

## 📂 Project Structure

```text
coldquery/
├── app.py              # <--- THE APP INSTANCE (Import mcp here)
├── server.py           # <--- THE ENTRY POINT (Run this)
├── core/
│   ├── executor.py     # Database execution logic (asyncpg)
│   ├── session.py      # Session state management
│   └── context.py      # ActionContext definition
├── security/           # Access control & sanitization
├── tools/              # MCP Tool definitions (@mcp.tool)
├── resources/          # MCP Resource definitions (@mcp.resource)
└── prompts/            # MCP Prompts (@mcp.prompt)
```

## ⚠️ Common Pitfalls

1.  **Circular Imports**: Never import `coldquery.server` inside `coldquery.tools.*`. It triggers the "empty tools list" bug.
2.  **Shadowing**: Do not name variables `mcp` inside functions if it shadows the global `mcp` object.
3.  **Port Conflicts**: The deployment port is **19002** (mapped to internal 3000/19002). Always check `docker-compose.deploy.yml`.
