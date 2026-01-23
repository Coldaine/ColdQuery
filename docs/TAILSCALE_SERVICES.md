# Tailscale Serve Architecture

This document describes the modern "Tailscale Serve" architecture for ColdQuery.

## Overview

We have transitioned from manual IP/Port management to named Tailscale services using `tailscale serve`. This decouples the application from the underlying infrastructure IP addresses and provides secure, authenticated access.

### Services

| Service Name | Protocol | Address | Replaces |
| :--- | :--- | :--- | :--- |
| `coldquery-mcp` | TCP & HTTP | `https://coldquery-mcp.tail4c911d.ts.net/` | `http://100.65.x.x:19002` |
| `raspberryoracle` | TCP | `tcp://raspberryoracle.tail4c911d.ts.net:5432` | `postgres://100.65.198.61` |

## Deployment

Deployment is handled via `docker-compose` which includes a Tailscale sidecar container.

### Prerequisites

1.  **Tailscale Auth Key**: You need a reusable, tagged auth key (e.g., `tag:server`) from the Tailscale Admin Console.
2.  **Environment Variables**:
    *   `TAILSCALE_AUTH_KEY`: The Tailscale auth key (secret name: `TAILSCALE_AUTH_KEY`).
    *   `PGPASSWORD`: The PostgreSQL password.

### Running Manually

1.  Ensure you have the `docker-compose.deploy.yml` file (typically renamed to `docker-compose.yml` on the server).
2.  Run:

    ```bash
    export TAILSCALE_AUTH_KEY=tskey-auth-...
    export PGPASSWORD=your_password
    docker-compose up -d
    ```

### Accessing the Service

You can now access the service from any device on your Tailscale network using the full DNS name:

```
https://coldquery-mcp.tail4c911d.ts.net/
```

(Note: Ensure your Tailscale ACLs allow access to `tag:server` or the specific machine/service).

## Configuration Details

*   **ColdQuery Container**:
    *   Does NOT bind ports to the host.
    *   Uses `network_mode: service:tailscale` to share the network namespace with the Tailscale sidecar.
    *   Connects to the database via `raspberryoracle.tail4c911d.ts.net` on port 5432.

*   **Tailscale Sidecar**:
    *   Advertises `coldquery-mcp` hostname.
    *   Runs `tailscale serve --bg --https=443 http://localhost:3000` to proxy incoming traffic to the application port 3000.
    *   Stores state in a docker volume `tailscale-data` to persist identity across restarts.

## Troubleshooting

### Hostname Collisions (Service Registers as `coldquery-mcp-2`)

**Problem:** After deployment, the service is accessible at `coldquery-mcp-2.tail4c911d.ts.net` instead of `coldquery-mcp.tail4c911d.ts.net`.

**Root Cause:** The Tailscale volume (`tailscale-data`) was deleted between deployments, causing the container to register as a new device. Tailscale appends a numeric suffix when a hostname collision is detected with an existing (possibly offline) device.

**Prevention:**
- **DO NOT** delete the `tailscale-data` volume between normal deployments
- The volume contains the device's persistent identity
- Destroying it causes each restart to appear as a new device

**Solution:**

1. Identify and delete the old device using the [Tailscale MCP Server](TAILSCALE_MCP_SERVER.md):

```bash
# List devices to find duplicates
tailscale status | grep coldquery

# Use Tailscale MCP server to delete old device
mcp__tailscale__device_action(
  deviceId="nT7wKM7DLh11CNTRL",  # Get ID from tailscale status or network status
  action="delete"
)
```

2. Stop containers and clear Tailscale state:

```bash
ssh raspberrypi "cd ~/coldquery && docker-compose down && docker volume rm coldquery_tailscale-data"
```

3. Redeploy to claim the correct hostname:

```bash
gh workflow run deploy.yml
```

4. Verify the service is accessible at the correct URL:

```bash
curl https://coldquery-mcp.tail4c911d.ts.net/health
```

### Service Not Accessible

**Problem:** Cannot reach service at `https://coldquery-mcp.tail4c911d.ts.net/`

**Debugging Steps:**

1. Check if containers are running:
```bash
ssh raspberrypi "docker ps --filter name=coldquery"
```

2. Check Tailscale sidecar logs:
```bash
ssh raspberrypi "docker logs coldquery-tailscale"
# Look for: "Available within your tailnet: https://coldquery-mcp.tail4c911d.ts.net/"
```

3. Verify device is online in your tailnet:
```bash
tailscale status | grep coldquery
```

4. Check application logs:
```bash
ssh raspberrypi "docker logs coldquery"
```

5. Test locally on the Pi:
```bash
ssh raspberrypi "docker exec coldquery curl -f http://localhost:3000/health"
```

### Container Health Checks Failing

**Problem:** Docker shows container as unhealthy

**Common Causes:**
- Application not listening on expected port (3000)
- Database connection failed (check `PGHOST`, `PGPORT`, `PGPASSWORD`)
- Application crashed (check logs)

**Solution:**
```bash
# Check health check status
ssh raspberrypi "docker inspect coldquery | grep -A 10 Health"

# View detailed logs
ssh raspberrypi "docker logs --tail 100 coldquery"

# Restart if needed
ssh raspberrypi "cd ~/coldquery && docker-compose restart coldquery"
```

## Best Practices

### 1. Preserve Tailscale Identity

The `tailscale-data` volume contains the device's persistent identity. **Do not delete it** unless you specifically want to register as a new device (e.g., when fixing hostname collisions).

### 2. Monitor Deployments

After each deployment, verify:
- Correct hostname: `tailscale status | grep coldquery`
- Service accessible: `curl https://coldquery-mcp.tail4c911d.ts.net/health`
- Containers healthy: `ssh raspberrypi "docker ps"`

### 3. Use the Tailscale MCP Server

Install the [Tailscale MCP Server](TAILSCALE_MCP_SERVER.md) in Claude Code for easier device management and troubleshooting.

### 4. Tag Appropriately

Use `tag:server` for production services to enable ACL-based access control.

## Related Documentation

- [Tailscale MCP Server](TAILSCALE_MCP_SERVER.md) - Using the MCP server for device management
- [GitHub Actions Deployment](.github/workflows/deploy.yml) - Automated deployment workflow
- [Docker Compose Configuration](docker-compose.deploy.yml) - Service configuration
