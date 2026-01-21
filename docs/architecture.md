# ColdQuery Architecture

## Problem Statement

Managing a PostgreSQL database from multiple development environments is painful:

1. **Credential sprawl**: Every machine needs PostgreSQL credentials configured
2. **Connection management**: Each environment opens its own connections, risking pool exhaustion
3. **No unified interface**: Different tools, different CLIs, different mental models
4. **Security surface**: Database credentials on every laptop, desktop, and device

## Solution

A single MCP server that acts as a gateway to PostgreSQL, deployed once and accessed from anywhere via Tailscale.

```
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ Claude Code      │  │ VS Code + Cline  │  │ Cursor           │
│ (laptop)         │  │ (desktop)        │  │ (wherever)       │
└────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘
         │                     │                     │
         └─────────────────────┼─────────────────────┘
                               │ Tailscale (private network)
                               ▼
                    ┌─────────────────────────────────┐
                    │ Raspberry Pi                    │
                    │ ┌─────────────────────────────┐ │
                    │ │ ColdQuery                   │ │
                    │ │ - Streamable HTTP transport │ │
                    │ │ - Session management        │ │
                    │ │ - Connection pooling        │ │
                    │ └──────────────┬──────────────┘ │
                    │                │ localhost      │
                    │ ┌──────────────▼──────────────┐ │
                    │ │ PostgreSQL                  │ │
                    │ │ - All databases             │ │
                    │ │ - All credentials here only │ │
                    │ └─────────────────────────────┘ │
                    └─────────────────────────────────┘
```

## Design Principles

### 1. Single Point of Configuration

PostgreSQL credentials live in ONE place: the Pi. No credentials on laptops, desktops, or other devices. The MCP server is configured once with:

```bash
export PGHOST=localhost
export PGUSER=postgres
export PGPASSWORD=<secret>
export PGDATABASE=postgres
```

### 2. Network Security via Tailscale

Instead of exposing PostgreSQL to the network:
- MCP server binds to `localhost`
- Exposed via `tailscale serve` (HTTPS)
- Access controlled by Tailnet ACLs
- No public internet exposure

### 3. Multiple Clients, One Server

The MCP server handles concurrent connections from different coding environments:

| Environment | How it connects |
|-------------|-----------------|
| Claude Code | HTTP transport to `https://<your-hostname>.tailnet.ts.net/mcp` |
| VS Code + Cline | Same URL |
| Cursor | Same URL |
| Any MCP client | Same URL |

> **Note:** Replace `<your-hostname>` with your Tailscale machine name (run `tailscale status`).

### 4. Stateful Sessions for Client Isolation

Each coding environment gets its own MCP session:
- Session ID assigned at initialization
- Requests routed to correct session
- PostgreSQL transactions isolated per client
- Clean disconnect handling

## Transport Choice: Streamable HTTP

### Why Not stdio?

The stdio transport (MCP default) spawns a server per client:

```
❌ Each client needs PostgreSQL credentials
❌ Each client spawns its own process
❌ No central management
❌ Credential sprawl
```

### Why Streamable HTTP?

```
✓ One server, many clients
✓ Credentials in one place
✓ Central connection pooling
✓ Tailscale handles auth
✓ MCP 2025-11-25 spec compliant
```

## Session Model

Two distinct session concepts:

| Layer | Purpose | Implementation |
|-------|---------|----------------|
| **MCP Transport** | Client identity across HTTP requests | `Mcp-Session-Id` header, managed by SDK |
| **PostgreSQL Transactions** | `BEGIN`...`COMMIT` state | `session_id` parameter from `pg_tx` |

These are independent:
- An MCP session can have multiple PostgreSQL transactions
- A PostgreSQL transaction belongs to one MCP session

## Security Layers

| Layer | Mechanism | What it protects against |
|-------|-----------|-------------------------|
| Network | Tailscale | Public internet, unauthorized networks |
| Transport | Origin validation | DNS rebinding attacks |
| Application | (Future) API keys | Fine-grained access control |

### Current Security Model

1. **Tailscale ACLs**: Define which users/devices can reach the MCP server
2. **Origin validation**: MCP SDK validates `Origin` header to prevent DNS rebinding
3. **Localhost binding**: Server only accepts connections from Tailscale proxy

### Future Enhancement: API Keys

For multi-tenant or more granular control:
```typescript
// Not implemented yet
{
  "api_key": "sk-...",
  "allowed_databases": ["mydb"],
  "permissions": ["read", "write"]
}
```

## Deployment

### On the Pi

```bash
# One-time setup
export PGHOST=localhost
export PGUSER=postgres
export PGPASSWORD=<secret>
export PGDATABASE=postgres
export MCP_ALLOWED_ORIGINS="https://<your-hostname>.tailnet.ts.net"

# Start server
PORT=3000 node dist/packages/core/src/server.js --transport http

# Expose via Tailscale
tailscale serve https:443 / http://127.0.0.1:3000
```

### On Client Machines

Configure MCP client to use the HTTP endpoint:

```json
{
  "mcpServers": {
    "postgres": {
      "url": "https://<your-hostname>.tailnet.ts.net/mcp"
    }
  }
}
```

No PostgreSQL credentials needed on client machines.

## Tools Provided

| Tool | Purpose |
|------|---------|
| `pg_query` | Execute SQL (read/write with safety checks) |
| `pg_schema` | DDL operations (create/alter/drop tables) |
| `pg_tx` | Transaction control (begin/commit/rollback) |
| `pg_monitor` | Health checks, connections, locks |
| `pg_admin` | Database administration |

## Trade-offs

| Benefit | Cost |
|---------|------|
| Centralized credentials | Single point of failure (Pi) |
| One server to update | Must keep Pi running |
| Tailscale security | Requires Tailscale on all devices |
| Connection pooling | Slightly higher latency than local |

For a home lab / personal infrastructure setup, the benefits far outweigh the costs.
