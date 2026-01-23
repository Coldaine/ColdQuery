# Tailscale Serve Deployment

This document describes the Tailscale Serve deployment architecture for ColdQuery.

## Overview

We use **Tailscale Serve** to expose services with named hostnames instead of hardcoded IP addresses. This decouples the application from infrastructure changes and provides secure access across the tailnet.

### Services

| Service | Hostname | Port | Replaces |
| :--- | :--- | :--- | :--- |
| PostgreSQL | `raspberryoracle.tail4c911d.ts.net` | 5432 | `100.65.198.61:5432` |
| ColdQuery MCP | `coldquery-mcp.tail4c911d.ts.net` | 3000 | `http://100.65.x.x:19002` |

## Architecture

### PostgreSQL (Host-level)
- Runs as Docker container on Raspberry Pi
- Exposed via `tailscale serve` on the host
- Command: `tailscale serve --bg --tcp 5432 tcp://localhost:5432`
- Accessible at: `raspberryoracle.tail4c911d.ts.net:5432`

### ColdQuery MCP (Container-level)
- Runs with Tailscale sidecar container
- Uses `network_mode: service:tailscale` to share network namespace
- Sidecar runs `tailscale serve --bg 3000` to expose the service
- Accessible at: `coldquery-mcp.tail4c911d.ts.net`

## Deployment

Deployment is handled via `docker-compose` which includes a Tailscale sidecar container.

### Prerequisites

1. **Tailscale Auth Key**: Reusable, tagged auth key from Tailscale Admin Console
   - Secret: `TAILSCALE_AUTH_KEY`
   - Tag: `tag:container`

2. **Environment Variables**:
   - `TS_AUTHKEY`: The Tailscale auth key
   - `PGPASSWORD`: The PostgreSQL password

### Manual Deployment

1. Ensure you have the `docker-compose.deploy.yml` file on the server
2. Run:

   ```bash
   cd ~/coldquery
   export TS_AUTHKEY=tskey-auth-...
   export PGPASSWORD=your_password
   docker-compose -f docker-compose.deploy.yml up -d
   ```

### Accessing the Services

From any device on your Tailscale network:

**PostgreSQL:**
```bash
psql -h raspberryoracle.tail4c911d.ts.net -p 5432 -U llm_archival -d llm_archival
```

**ColdQuery MCP:**
```bash
curl http://coldquery-mcp.tail4c911d.ts.net:3000/health
```

Or use short hostnames (if MagicDNS search domains are configured):
```bash
psql -h raspberryoracle -p 5432 -U llm_archival -d llm_archival
curl http://coldquery-mcp:3000/health
```

## Configuration Details

### ColdQuery Container
- Does NOT bind ports to the host
- Uses `network_mode: service:tailscale` to share network namespace with sidecar
- Connects to PostgreSQL via `raspberryoracle.tail4c911d.ts.net:5432`
- Environment: `PGHOST=raspberryoracle.tail4c911d.ts.net`

### Tailscale Sidecar
- Hostname: `coldquery-mcp`
- Runs `tailscale serve --bg 3000` to expose the service
- Persists state in Docker volume `tailscale-data`
- Tags: `tag:container`

## Verification

Check services are running:

```bash
# On the Raspberry Pi
sudo tailscale serve status

# Should show:
# |-- tcp://raspberryoracle.tail4c911d.ts.net:5432 (TLS over TCP, tailnet only)
# |--> tcp://localhost:5432

# Check ColdQuery container
docker logs coldquery-tailscale
docker exec coldquery-tailscale tailscale serve status
```

Test connectivity from any tailnet device:

```bash
# Test Postgres
nc -zv raspberryoracle.tail4c911d.ts.net 5432

# Test ColdQuery
curl -v http://coldquery-mcp.tail4c911d.ts.net:3000/health
```

## Benefits

1. **Named Access**: Use hostnames instead of IP addresses
2. **Secure**: All traffic stays within your tailnet (no public exposure)
3. **Portable**: Services can move to different hosts without config changes
4. **Encrypted**: TLS over TCP automatically handled by Tailscale
5. **Simple**: No complex networking or port forwarding needed
