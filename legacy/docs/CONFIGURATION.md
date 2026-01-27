# Configuration Guide

This document covers all configuration options for ColdQuery.

## Environment Variables

### PostgreSQL Connection

| Variable | Default | Description |
|----------|---------|-------------|
| `PGHOST` | `localhost` | PostgreSQL server hostname |
| `PGPORT` | `5432` | PostgreSQL server port |
| `PGUSER` | `postgres` | Database username |
| `PGPASSWORD` | (none) | Database password |
| `PGDATABASE` | `postgres` | Database name |
| `POSTGRES_URL` | (none) | Connection string (alternative to individual vars) |

**Connection String Format:**
```
postgres://user:password@host:port/database?sslmode=require
```

If `POSTGRES_URL` is set, it takes precedence over individual variables.

### Connection Pool

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_POOL_MIN` | `2` | Minimum connections in pool |
| `POSTGRES_POOL_MAX` | `10` | Maximum connections in pool |

### Server Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_TRANSPORT` | `stdio` | Transport type: `stdio`, `http` |
| `PORT` | `3000` | HTTP server port (when using HTTP transport) |
| `HOST` | `0.0.0.0` | HTTP server bind address |
| `LOG_LEVEL` | `info` | Log level: `debug`, `info`, `warn`, `error` |

### Security

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_ALLOWED_ORIGINS` | (none) | Comma-separated allowed origins for HTTP transport |

**Example:**
```bash
MCP_ALLOWED_ORIGINS=https://claude.ai,http://localhost:3000
```

### Session Management

| Variable | Default | Description |
|----------|---------|-------------|
| `SESSION_TTL_MS` | `1800000` | Session timeout in milliseconds (30 min) |
| `MAX_SESSIONS` | `10` | Maximum concurrent transaction sessions |

## MCP Client Configuration

### Claude Desktop / VS Code

Create or edit `.mcp.json` in the project root or user config directory:

```json
{
  "mcpServers": {
    "coldquery": {
      "command": "node",
      "args": ["/path/to/ColdQuery/dist/packages/core/src/server.js"],
      "env": {
        "PGHOST": "localhost",
        "PGPORT": "5432",
        "PGUSER": "postgres",
        "PGPASSWORD": "your-password",
        "PGDATABASE": "your-database"
      }
    }
  }
}
```

### Remote HTTP Server

For HTTP transport (remote access):

```json
{
  "mcpServers": {
    "coldquery": {
      "url": "http://your-server:3000/mcp",
      "transport": "sse"
    }
  }
}
```

## Transport Configuration

### stdio Transport (Default)

Standard input/output transport for local MCP clients.

```bash
# Run with stdio transport
node dist/packages/core/src/server.js
```

No additional configuration needed for stdio.

### HTTP Transport

Server-Sent Events (SSE) transport for remote clients.

```bash
# Run with HTTP transport
MCP_TRANSPORT=http PORT=3000 node dist/packages/core/src/server.js
```

**Endpoints:**
- `GET /mcp` - SSE connection endpoint
- `POST /mcp/messages` - Message endpoint
- `GET /health` - Health check

## Docker Configuration

### Environment File

Create `.env` for Docker deployments:

```bash
# PostgreSQL Connection
PGHOST=postgres
PGPORT=5432
PGUSER=app_user
PGPASSWORD=secure_password
PGDATABASE=production

# Server Configuration
MCP_TRANSPORT=http
PORT=3000
LOG_LEVEL=info

# Security
MCP_ALLOWED_ORIGINS=https://your-client.com
```

### Docker Compose

```yaml
version: '3.8'

services:
  coldquery:
    image: coldquery:latest
    ports:
      - "3000:3000"
    environment:
      - PGHOST=postgres
      - PGPORT=5432
      - PGUSER=app_user
      - PGPASSWORD=${POSTGRES_PASSWORD}
      - PGDATABASE=production
      - MCP_TRANSPORT=http
      - LOG_LEVEL=info
    depends_on:
      postgres:
        condition: service_healthy

  postgres:
    image: postgres:16
    environment:
      - POSTGRES_USER=app_user
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - POSTGRES_DB=production
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app_user -d production"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  pgdata:
```

## Configuration Examples

### Local Development

```bash
# .env
PGHOST=localhost
PGPORT=5433  # Docker-mapped port
PGUSER=mcp
PGPASSWORD=mcp
PGDATABASE=mcp_test
LOG_LEVEL=debug
```

### Production (Raspberry Pi)

```bash
# Environment variables in Docker run
PGHOST=llm_postgres
PGPORT=5432
PGUSER=llm_archival
PGPASSWORD=<secret>
PGDATABASE=llm_archival
MCP_TRANSPORT=http
LOG_LEVEL=info
```

### Tailscale Deployment

```bash
# MCP client configuration
{
  "mcpServers": {
    "coldquery": {
      "url": "http://100.65.198.61:19002/mcp",
      "transport": "sse"
    }
  }
}
```

## SSL/TLS Configuration

### PostgreSQL SSL

```bash
# Require SSL
PGSSLMODE=require

# Or in connection string
POSTGRES_URL=postgres://user:pass@host:5432/db?sslmode=require
```

**SSL Modes:**
| Mode | Description |
|------|-------------|
| `disable` | No SSL (not recommended for production) |
| `allow` | Try SSL, fall back to non-SSL |
| `prefer` | Try SSL first (default) |
| `require` | Require SSL, don't verify certificate |
| `verify-ca` | Require SSL, verify CA |
| `verify-full` | Require SSL, verify CA and hostname |

### HTTPS for HTTP Transport

ColdQuery itself does not handle HTTPS. Use a reverse proxy:

```nginx
# nginx configuration
server {
    listen 443 ssl;
    server_name coldquery.example.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
    }
}
```

## Validation

### Test Connection

After configuration, verify connectivity:

```bash
# Using curl (HTTP transport)
curl http://localhost:3000/health

# Expected response:
# {"status":"healthy","database":"your_db","version":"PostgreSQL 16..."}
```

### Verify MCP Registration

Test that tools are registered:

```bash
curl -X POST http://localhost:3000/mcp/messages \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

## Troubleshooting

### Connection Issues

1. **Check environment variables are set:**
   ```bash
   env | grep PG
   ```

2. **Test direct PostgreSQL connection:**
   ```bash
   psql -h $PGHOST -p $PGPORT -U $PGUSER -d $PGDATABASE
   ```

3. **Verify network connectivity:**
   ```bash
   nc -zv $PGHOST $PGPORT
   ```

### Configuration Not Applied

1. Ensure variables are exported (not just set):
   ```bash
   export PGHOST=localhost
   ```

2. For Docker, verify env file is loaded:
   ```bash
   docker compose config
   ```

3. Check for typos in variable names

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for more detailed solutions.
