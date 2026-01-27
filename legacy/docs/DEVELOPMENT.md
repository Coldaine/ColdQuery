# Development Guide

This guide covers local setup, testing, debugging, and development workflows for ColdQuery.

## Prerequisites

- **Node.js 24+** - Required for modern ES module support
- **npm** - Included with Node.js
- **Docker** - For running the test PostgreSQL container
- **PostgreSQL client** (optional) - For manual database inspection (`psql`)

### Verify Prerequisites

```bash
node --version    # Should be v24.0.0 or higher
npm --version     # Should be v10.0.0 or higher
docker --version  # Any recent version
```

## Project Structure

ColdQuery uses an npm workspaces monorepo structure:

```
ColdQuery/
├── packages/
│   └── core/                 # Main MCP server package
│       └── src/
│           ├── server.ts     # Server entry point
│           ├── tools/        # Tool definitions (pg-query, pg-schema, etc.)
│           ├── actions/      # Action handlers for each tool
│           ├── transports/   # HTTP/SSE transport layer
│           ├── middleware/   # Request processing middleware
│           └── session.ts    # Transaction session management
├── shared/                   # Shared utilities
│   ├── executor/             # Database executor interface
│   └── security/             # Security utilities (identifier sanitization)
├── scripts/                  # Build and test automation
├── test-database/            # Test database schema and seed data
├── docs/                     # Documentation
└── dist/                     # Compiled output (generated)
```

### Key Files

| File | Purpose |
|------|---------|
| `packages/core/src/server.ts` | Server initialization and tool registration |
| `packages/core/src/session.ts` | Transaction session lifecycle management |
| `packages/core/src/transports/http.ts` | SSE/HTTP transport implementation |
| `shared/executor/postgres.ts` | PostgreSQL connection pool and executor |
| `tsconfig.json` | TypeScript configuration (strict mode) |
| `vitest.config.ts` | Test framework configuration |

## Local Setup

### 1. Clone Repository

```bash
git clone https://github.com/Coldaine/ColdQuery.git
cd ColdQuery
```

### 2. Install Dependencies

```bash
npm install
```

This installs dependencies for all workspaces (root, packages/core, shared).

### 3. Build TypeScript

```bash
npm run build
```

Output is generated in `dist/` directories within each package.

### 4. Configure Environment (Optional)

For local development, copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` to match your local PostgreSQL setup. The default test configuration uses:
- Host: `localhost`
- Port: `5433` (Docker-mapped)
- User: `mcp`
- Password: `mcp`
- Database: `mcp_test`

### 5. Start Test Database

```bash
docker compose up -d
```

This starts a PostgreSQL container pre-configured with test data.

### 6. Verify Setup

```bash
npm test
```

All tests should pass. If not, see [Troubleshooting](TROUBLESHOOTING.md).

## Running the Server

### Development Mode (with watch)

```bash
npm run dev
```

This starts TypeScript compiler in watch mode. Rebuild on file changes.

### Production Mode

```bash
npm run build
node dist/packages/core/src/server.js
```

### HTTP/SSE Transport

To start the server with HTTP transport for MCP clients:

```bash
MCP_TRANSPORT=http PORT=3000 node dist/packages/core/src/server.js
```

## Running Tests

### All Tests

```bash
npm test
```

### With Database Lifecycle (CI mode)

Automatically starts/stops the test database:

```bash
npm run test:ci
```

### With Coverage

```bash
npm run test:coverage
```

Coverage report is generated in `coverage/` directory.

### Watch Mode

```bash
npx vitest watch
```

Re-runs tests on file changes.

### Single Test File

```bash
npx vitest packages/core/src/actions/query/__tests__/read.test.ts
```

### Test Database Setup

The test database is defined in `docker-compose.yml` and initialized with `test-database/test-database.sql`.

**Manual database management:**
```bash
# Start
docker compose up -d

# Check status
docker compose ps

# View logs
docker compose logs -f

# Stop (preserves data)
docker compose stop

# Stop and remove data
docker compose down -v
```

**Connect to test database:**
```bash
psql -h localhost -p 5433 -U mcp -d mcp_test
# Password: mcp
```

## Code Quality

### Linting

```bash
npm run lint
```

Uses ESLint with TypeScript rules.

### Type Checking

```bash
npm run typecheck
```

Runs TypeScript compiler without emitting files.

### Full Check

```bash
npm run check
```

Runs both lint and typecheck.

## TypeScript Configuration

ColdQuery uses **strict TypeScript** configuration (`tsconfig.json`):

```json
{
  "compilerOptions": {
    "strict": true,
    "noImplicitAny": true,
    "strictNullChecks": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noImplicitReturns": true,
    "noUncheckedIndexedAccess": true
    // ... and more
  }
}
```

All code must pass strict type checking. No `any` types unless explicitly justified.

## Debugging

### TypeScript Compilation Errors

Common issues:

1. **Missing type annotations**
   ```typescript
   // Bad
   const result = await db.query(sql);

   // Good
   const result: QueryResult = await db.query(sql);
   ```

2. **Unchecked index access** (due to `noUncheckedIndexedAccess`)
   ```typescript
   // Bad
   const first = array[0];

   // Good
   const first = array[0];
   if (first) { /* use first */ }
   ```

### Database Connection Issues

1. **Connection refused**
   ```
   Error: connect ECONNREFUSED 127.0.0.1:5433
   ```
   - Verify Docker container is running: `docker compose ps`
   - Check correct port: `5433` (not `5432`)

2. **Authentication failed**
   ```
   Error: password authentication failed for user "mcp"
   ```
   - Verify password in `.env` matches `docker-compose.yml`

3. **Database does not exist**
   ```
   Error: database "mcp_test" does not exist
   ```
   - Recreate container: `docker compose down -v && docker compose up -d`

### MCP Protocol Debugging

Enable debug logging:
```bash
LOG_LEVEL=debug node dist/packages/core/src/server.js
```

For HTTP transport, inspect requests:
```bash
curl -X POST http://localhost:3000/mcp/messages \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}'
```

### Session Management Testing

To debug transaction sessions:

```typescript
// In your test
const result = await client.callTool("pg_tx", { action: "list" });
console.log("Active sessions:", result.sessions);
```

Check session limits (max 10) and TTL (30 minutes).

## Making Changes

### Development Workflow

1. **Create feature branch**
   ```bash
   git checkout -b feature/my-feature
   ```

2. **Make changes** with tests

3. **Run checks**
   ```bash
   npm run check && npm test
   ```

4. **Commit with conventional commits**
   ```bash
   git commit -m "feat: add new capability"
   ```

5. **Submit pull request**

### Adding a New Tool

1. Create action handlers in `packages/core/src/actions/<tool>/`
2. Create tool definition in `packages/core/src/tools/`
3. Register tool in `packages/core/src/server.ts`
4. Add tests in `__tests__/` directory
5. Document in `docs/toolDescriptions/`
6. Update `docs/TOOL_REFERENCE.md`

### Adding a New Action to Existing Tool

1. Create action handler in appropriate `actions/` subdirectory
2. Add to action registry in tool file
3. Update tool schema (discriminated union)
4. Add tests
5. Update tool description documentation

## Code Style

### File Organization

- One tool per file in `tools/`
- Actions grouped by tool in `actions/<tool>/`
- Tests co-located in `__tests__/` directories
- Shared utilities in `shared/`

### Naming Conventions

- Files: `kebab-case.ts` (e.g., `pg-query.ts`)
- Classes: `PascalCase` (e.g., `SessionManager`)
- Functions: `camelCase` (e.g., `createMcpServer`)
- Constants: `SCREAMING_SNAKE_CASE` (e.g., `MAX_SESSIONS`)
- Types/Interfaces: `PascalCase` (e.g., `ToolDefinition`)

### Error Handling

- Use descriptive error messages
- Include context in errors
- Throw specific errors, not generic `Error`

```typescript
// Good
throw new Error(`Session not found: ${sessionId}. Use pg_tx begin to create a session.`);

// Bad
throw new Error("Invalid session");
```

### Comments

Document **why**, not **what**:

```typescript
// Good: Explains the rationale
// WHY CLOSE ON COMMIT: Release connection back to pool to prevent leaks

// Bad: States the obvious
// Close the session
await session.close();
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PGHOST` | `localhost` | PostgreSQL host |
| `PGPORT` | `5432` | PostgreSQL port |
| `PGUSER` | `postgres` | Database user |
| `PGPASSWORD` | (none) | Database password |
| `PGDATABASE` | `postgres` | Database name |
| `MCP_TRANSPORT` | `stdio` | Transport type: `stdio`, `http` |
| `PORT` | `3000` | HTTP server port |
| `LOG_LEVEL` | `info` | Log level: `debug`, `info`, `warn`, `error` |

See [CONFIGURATION.md](CONFIGURATION.md) for full details.

## Release Process

1. **Update version** in `package.json` files
2. **Update CHANGELOG.md** with release notes
3. **Create release commit**
   ```bash
   git commit -m "chore: release v0.2.0"
   ```
4. **Tag release**
   ```bash
   git tag v0.2.0
   ```
5. **Push with tags**
   ```bash
   git push && git push --tags
   ```

GitHub Actions will automatically deploy on push to main.

## Useful Commands

| Command | Description |
|---------|-------------|
| `npm install` | Install all dependencies |
| `npm run build` | Compile TypeScript |
| `npm run dev` | Watch mode compilation |
| `npm test` | Run tests |
| `npm run test:ci` | Run tests with database lifecycle |
| `npm run test:coverage` | Run tests with coverage |
| `npm run lint` | Run ESLint |
| `npm run typecheck` | Type check without emit |
| `npm run check` | Lint + typecheck |
| `docker compose up -d` | Start test database |
| `docker compose down` | Stop test database |
| `docker compose down -v` | Stop and remove data |

## Further Reading

- [ARCHITECTURE.md](../ARCHITECTURE.md) - System architecture overview
- [TOOL_REFERENCE.md](TOOL_REFERENCE.md) - Complete tool API reference
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Common issues and solutions
- [CONTRIBUTING.md](../CONTRIBUTING.md) - Contribution guidelines
