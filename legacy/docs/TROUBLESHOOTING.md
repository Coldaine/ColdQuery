# Troubleshooting Guide

This guide covers common issues and their solutions when working with ColdQuery.

## Connection Issues

### Connection Refused

**Error:**
```
Error: connect ECONNREFUSED 127.0.0.1:5432
```

**Causes:**
- PostgreSQL server is not running
- Wrong host or port configuration
- Firewall blocking connection

**Solutions:**
1. Verify PostgreSQL is running:
   ```bash
   # Linux/macOS
   systemctl status postgresql
   # or for Docker
   docker compose ps
   ```

2. Check connection settings in `.env`:
   ```bash
   PGHOST=localhost
   PGPORT=5432  # or 5433 for test container
   ```

3. Test connection directly:
   ```bash
   psql -h localhost -p 5432 -U postgres
   ```

### Authentication Failed

**Error:**
```
Error: password authentication failed for user "postgres"
```

**Causes:**
- Wrong password
- Wrong username
- pg_hba.conf misconfiguration

**Solutions:**
1. Verify credentials in `.env` match your PostgreSQL setup
2. For test container, use:
   ```
   PGUSER=mcp
   PGPASSWORD=mcp
   PGDATABASE=mcp_test
   ```
3. Check PostgreSQL logs for detailed auth errors

### Database Does Not Exist

**Error:**
```
Error: database "mydb" does not exist
```

**Solutions:**
1. Verify database name in `PGDATABASE`
2. Create the database:
   ```bash
   createdb mydb
   ```
3. For test container, recreate:
   ```bash
   docker compose down -v
   docker compose up -d
   ```

### Connection Timeout

**Error:**
```
Error: Connection timeout after 30000ms
```

**Causes:**
- Network issues (especially with Tailscale)
- Database server overloaded
- Firewall or VPN blocking connection

**Solutions:**
1. Check network connectivity:
   ```bash
   ping <database-host>
   ```
2. For Tailscale connections, verify node is online:
   ```bash
   tailscale status
   ```
3. Increase connection timeout in pool configuration

### SSL Required

**Error:**
```
Error: SSL required
```

**Solutions:**
1. Add SSL to connection string:
   ```
   POSTGRES_URL=postgres://user:pass@host:5432/db?sslmode=require
   ```
2. Or disable SSL (local development only):
   ```
   PGSSLMODE=disable
   ```

## Build Errors

### TypeScript Compilation Errors

**Error:**
```
error TS2322: Type 'X' is not assignable to type 'Y'
```

**Solutions:**
1. Run type check to see all errors:
   ```bash
   npm run typecheck
   ```
2. Fix type annotations
3. Avoid `any` types - use proper interfaces

**Common strict mode issues:**

```typescript
// noUncheckedIndexedAccess
// Bad
const first = array[0];
// Good
const first = array[0];
if (first !== undefined) { /* use first */ }

// noImplicitReturns
// Bad
function getValue(x: boolean) {
  if (x) return "yes";
  // Missing else return
}
// Good
function getValue(x: boolean) {
  if (x) return "yes";
  return "no";
}
```

### Module Resolution Errors

**Error:**
```
Error: Cannot find module '@pg-mcp/shared'
```

**Solutions:**
1. Rebuild the project:
   ```bash
   npm run build
   ```
2. Reinstall dependencies:
   ```bash
   rm -rf node_modules
   npm install
   ```
3. Check workspace configuration in `package.json`

### ESLint Errors

**Error:**
```
error: 'x' is defined but never used
```

**Solutions:**
1. Run lint with auto-fix:
   ```bash
   npm run lint -- --fix
   ```
2. Prefix unused variables with underscore: `_unused`
3. Remove truly unused code

## Runtime Errors

### Session Not Found

**Error:**
```
Error: Session not found: tx_abc123
```

**Causes:**
- Session was already committed or rolled back
- Session timed out (30 minute TTL)
- Invalid session ID

**Solutions:**
1. Begin a new transaction:
   ```json
   {"action": "begin"}
   ```
2. Check active sessions:
   ```json
   {"action": "list"}
   ```
3. Don't reuse session IDs after commit/rollback

### Maximum Sessions Reached

**Error:**
```
Error: Maximum session limit (10) reached
```

**Solutions:**
1. Close unused sessions:
   ```json
   {"action": "rollback", "session_id": "<id>"}
   ```
2. Check for session leaks in your code
3. Sessions auto-close after 30 minutes

### Write Operation Safety Check Failed

**Error:**
```
Error: Write operations require either session_id or autocommit:true for safety
```

**Explanation:** This is the **Default-Deny** policy working as intended.

**Solutions:**
1. For transactions, use session_id:
   ```json
   {"action": "begin"}
   // Then use returned session_id
   ```
2. For standalone writes, use autocommit:
   ```json
   {"action": "write", "sql": "...", "autocommit": true}
   ```

### Transaction Aborted

**Error:**
```
Error: current transaction is aborted, commands ignored until end of transaction block
```

**Cause:** A previous statement in the transaction failed.

**Solutions:**
1. Rollback and start fresh:
   ```json
   {"action": "rollback", "session_id": "<id>"}
   {"action": "begin"}
   ```
2. Fix the failing query before retry

### SQL Syntax Error

**Error:**
```
Error: syntax error at or near "SELEC"
```

**Solutions:**
1. Check SQL syntax
2. Use parameterized queries for values:
   ```json
   {"sql": "SELECT * FROM users WHERE id = $1", "params": [123]}
   ```
3. Test query in psql first

## Deployment Issues

### Docker Build Fails

**Error:**
```
ERROR: failed to solve: process "/bin/sh -c npm ci" did not complete successfully
```

**Solutions:**
1. Clear Docker cache:
   ```bash
   docker build --no-cache -t coldquery .
   ```
2. Check Dockerfile syntax
3. Verify all files are in Docker context

### SSH Connection Timeout

**Error:**
```
Error: Connection timed out
```

**Solutions:**
1. Verify SSH key is configured
2. Check Tailscale is connected:
   ```bash
   tailscale status
   ```
3. Verify target host is online
4. Check firewall rules

### Health Check Fails

**Error:**
```
Container health: unhealthy
```

**Solutions:**
1. Check container logs:
   ```bash
   docker logs <container-name>
   ```
2. Verify environment variables are set
3. Check database is accessible from container
4. Ensure health check endpoint responds

### GitHub Actions Fails

**Common causes:**
- Missing secrets (check repository settings)
- Tailscale OAuth token expired
- SSH key permissions

**Solutions:**
1. Verify all secrets are configured in repo settings
2. Check workflow logs for specific error
3. Test locally first with `npm run test:ci`

## MCP Protocol Errors

### Invalid Request

**Error:**
```
Error: Invalid request: missing required field 'action'
```

**Solutions:**
1. Check request format matches tool schema
2. Refer to [TOOL_REFERENCE.md](TOOL_REFERENCE.md)
3. Verify JSON is valid

### Tool Not Found

**Error:**
```
Error: Unknown tool: pg_nonexistent
```

**Solutions:**
1. Check available tools: `tools/list` method
2. Verify tool name spelling
3. Check tool registration in server.ts

### Connection Reset

**Error:**
```
Error: Connection reset by peer
```

**Causes:**
- Server crashed
- Network interruption
- Client timeout

**Solutions:**
1. Check server logs
2. Verify server is still running
3. Increase client timeout settings

## Performance Issues

### Slow Queries

**Symptoms:** Queries taking longer than expected

**Solutions:**
1. Use `pg_query.explain` to analyze:
   ```json
   {"action": "explain", "sql": "SELECT ...", "analyze": true}
   ```
2. Check for missing indexes:
   ```json
   {"action": "stats", "target": "table_name"}
   ```
3. Run ANALYZE to update statistics:
   ```json
   {"action": "analyze", "target": "table_name"}
   ```

### Connection Pool Exhaustion

**Symptoms:** Requests hang or fail with connection errors

**Solutions:**
1. Check connection usage:
   ```json
   {"action": "connections"}
   ```
2. Close idle transactions
3. Increase pool size (if resources allow)
4. Look for connection leaks

### High Memory Usage

**Symptoms:** Server using excessive memory

**Solutions:**
1. Check for large result sets
2. Use pagination (LIMIT/OFFSET)
3. Close unused sessions
4. Monitor with `pg_monitor.activity`

## Getting Help

If your issue isn't covered here:

1. **Search existing issues**: [GitHub Issues](https://github.com/Coldaine/ColdQuery/issues)
2. **Check the logs**: Enable debug logging with `LOG_LEVEL=debug`
3. **Open a new issue**: Include error message, steps to reproduce, and environment details
4. **Include context**:
   - Node.js version
   - PostgreSQL version
   - Operating system
   - Relevant configuration
