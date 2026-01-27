# Tailscale MCP Server

This document describes how to use the Tailscale MCP server for managing Tailscale devices and troubleshooting deployment issues.

## Overview

The [Tailscale MCP Server](https://github.com/HexSleeves/tailscale-mcp) provides Claude Code with tools to manage Tailscale devices, routes, and network configuration programmatically. This is particularly useful for:

- Cleaning up duplicate/stale devices
- Managing device lifecycle (authorize, deauthorize, delete)
- Troubleshooting network connectivity
- Automating Tailscale administration tasks

## Installation

### Prerequisites

You need OAuth credentials from the Tailscale admin console. These are stored in Bitwarden Secrets Manager:

- `TAILSCALE_OAUTH_CLIENT_ID_GITHUB_CI` - OAuth client ID
- `TAILSCALE_OAUTH_CLIENT_SECRET_GITHUB_CI` - OAuth client secret

### Configuration

Add to your Claude Code configuration (`~/.claude.json`):

```json
{
  "mcpServers": {
    "tailscale": {
      "type": "stdio",
      "command": "cmd",
      "args": [
        "/c",
        "npx",
        "--package=@hexsleeves/tailscale-mcp-server",
        "tailscale-mcp-server"
      ],
      "env": {
        "TAILSCALE_OAUTH_CLIENT_ID": "your-client-id",
        "TAILSCALE_OAUTH_CLIENT_SECRET": "your-client-secret",
        "TAILSCALE_TAILNET": "tail4c911d.ts.net"
      }
    }
  }
}
```

### Quick Setup

```bash
# Get credentials from BWS
bws secret get 9325fb2f-4c65-426f-aefd-b3d900d47675  # OAuth Client ID
bws secret get 4314e60f-c068-4e23-877b-b3d900d47bf7  # OAuth Client Secret

# Claude Code will automatically load the MCP server on next restart
```

## Available Tools

### Device Management

- `list_devices` - List all devices in the Tailscale network
- `device_action` - Perform actions on devices (authorize, deauthorize, delete, expire-key)
- `manage_routes` - Enable/disable routes for devices

### Network Operations

- `get_network_status` - Get current network status from CLI
- `connect_network` - Connect to Tailscale network
- `disconnect_network` - Disconnect from network
- `ping_peer` - Test connectivity to peer devices

### Information

- `get_version` - Get Tailscale version
- `get_tailnet_info` - Get detailed network information

## Common Use Cases

### Cleaning Up Duplicate Devices

When deploying services with Tailscale Serve, hostname collisions can occur if the Tailscale state volume is destroyed between deployments. Each fresh start registers as a new device.

**Symptoms:**
- Service registers with hostname suffix (e.g., `coldquery-mcp-2` instead of `coldquery-mcp`)
- `tailscale status` shows multiple devices with the same base hostname
- Old devices appear as "offline"

**Solution:**

1. List devices to find duplicates:
```bash
# Using MCP server
mcp__tailscale__list_devices(includeRoutes=false)

# Or use CLI
tailscale status | grep coldquery
```

2. Get detailed device information:
```bash
mcp__tailscale__get_network_status(format="json")
```

3. Delete old/offline devices:
```bash
mcp__tailscale__device_action(
  deviceId="nT7wKM7DLh11CNTRL",  # Get from network status
  action="delete"
)
```

4. Redeploy service to claim correct hostname:
```bash
# Stop containers and clear Tailscale state
ssh raspberrypi "cd ~/coldquery && docker-compose down && docker volume rm coldquery_tailscale-data"

# Trigger fresh deployment
gh workflow run deploy.yml
```

### Verifying Deployment

After deploying a service:

1. Check device registered correctly:
```bash
tailscale status | grep service-name
```

2. Verify service is accessible:
```bash
curl https://service-name.tail4c911d.ts.net/health
```

3. Check container logs:
```bash
ssh raspberrypi "docker logs service-tailscale"
```

## Troubleshooting

### Hostname Collisions

**Problem:** Service registers as `service-name-2` instead of `service-name`

**Root Cause:** An old device with the same hostname still exists in Tailscale (even if offline)

**Solution:**
1. Use `list_devices` to find the old device ID
2. Use `device_action` with `delete` to remove it
3. Stop containers and remove the Tailscale volume
4. Redeploy

### OAuth Authentication Errors

**Problem:** MCP server fails to connect or returns "API token invalid"

**Causes:**
- Incorrect OAuth credentials
- OAuth client doesn't have required permissions
- Expired credentials

**Solution:**
1. Verify credentials in BWS are current
2. Check OAuth client has `Devices:Write` permission
3. Regenerate OAuth credentials if needed
4. Update Claude Code config with new credentials

### Service Not Accessible

**Problem:** Can't reach service at `https://service-name.tail4c911d.ts.net/`

**Debugging Steps:**

1. Verify Tailscale container is running:
```bash
ssh raspberrypi "docker ps --filter name=service-tailscale"
```

2. Check Tailscale serve configuration:
```bash
ssh raspberrypi "docker logs service-tailscale | grep 'Available within'"
```

3. Verify device is online:
```bash
tailscale status | grep service-name
```

4. Check application container health:
```bash
ssh raspberrypi "docker ps --filter name=service-name"
```

5. Test from Pi locally:
```bash
ssh raspberrypi "docker exec service-name curl -f http://localhost:3000/health"
```

## Best Practices

### 1. Preserve Tailscale State

**DON'T** destroy the Tailscale volume between deployments unless cleaning up hostname collisions:

```bash
# BAD - causes new device registration
docker volume rm service_tailscale-data
```

**DO** preserve the volume for container restarts:

```yaml
# docker-compose.yml
volumes:
  tailscale-data:
    # Volume persists across container restarts
```

### 2. Use Ephemeral Auth Keys for CI/CD

For GitHub Actions and other ephemeral environments, use auth keys that auto-cleanup:

```yaml
# GitHub Actions
env:
  TS_AUTHKEY: ${{ secrets.TAILSCALE_AUTH_KEY }}
  # Key should be configured as:
  # - Reusable: true
  # - Ephemeral: false (for persistent services)
  # - Tags: tag:server
```

### 3. Monitor Device Lifecycle

Periodically check for stale devices:

```bash
# List all devices
mcp__tailscale__list_devices(includeRoutes=false)

# Check for offline devices
tailscale status | grep offline
```

### 4. Tag Devices Appropriately

Use tags to organize and control ACLs:

```yaml
# docker-compose.yml
environment:
  - TS_EXTRA_ARGS=--advertise-tags=tag:server --hostname=service-name
```

### 5. Document Service Hostnames

Maintain a service registry in documentation:

| Service | Hostname | Purpose |
|---------|----------|---------|
| coldquery | `coldquery-mcp.tail4c911d.ts.net` | ColdQuery MCP server |
| postgres | `raspberryoracle.tail4c911d.ts.net:5432` | PostgreSQL database |

## Future Considerations

### MCP Gateway

As we deploy more MCP servers, consider using an MCP gateway to:
- Centralize MCP server management
- Reduce per-service overhead
- Simplify client configuration
- Provide unified service discovery

### Service Mesh

For multiple interconnected services:
- Consider using Tailscale Serve for all inter-service communication
- Implement health checks and service discovery
- Use consistent tagging for ACL management
- Document service dependencies

## References

- [Tailscale MCP Server GitHub](https://github.com/HexSleeves/tailscale-mcp)
- [Tailscale Serve Documentation](https://tailscale.com/kb/1242/tailscale-serve/)
- [Tailscale OAuth Clients](https://tailscale.com/kb/1215/oauth-clients/)
- [Model Context Protocol](https://modelcontextprotocol.io/)
