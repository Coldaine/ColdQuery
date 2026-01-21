# ColdQuery Deployment Guide

This guide covers deployment of ColdQuery. For automated deployment via GitHub Actions, see [../.github/WORKFLOWS.md](../.github/WORKFLOWS.md).

## Deployment Options

| Method | Description | Best For |
|--------|-------------|----------|
| Manual | Build locally, transfer to target | One-time deploys, debugging |
| GitHub Actions | Automated on push to main | Production deployments |
| Local Docker | Run in local container | Development, testing |

## Prerequisites

- Docker installed on target machine
- Docker Buildx installed locally (for ARM64 cross-compilation)
- SSH access to target (for manual deployment)
- PostgreSQL accessible from target

## Manual Deployment

### 1. Build the ARM64 Image

```bash
# From the project root
docker buildx build --platform linux/arm64 -t coldquery:VERSION --load .
```

Replace `VERSION` with your desired tag (e.g., `latest`, `v1.0.0`, or a git SHA).

### 2. Transfer to Target Server

```bash
docker save coldquery:VERSION | gzip | ssh user@target 'gunzip | docker load'
```

### 3. Run the Container

```bash
ssh user@target

# Stop existing container (if running)
docker stop coldquery 2>/dev/null || true
docker rm coldquery 2>/dev/null || true

# Start new container
docker run -d \
  --name coldquery \
  --restart unless-stopped \
  --network postgres_network \
  -p 19002:3000 \
  -e PGHOST=postgres_container \
  -e PGPORT=5432 \
  -e PGUSER=your_user \
  -e PGPASSWORD=your_password \
  -e PGDATABASE=your_database \
  coldquery:VERSION
```

### 4. Verify Deployment

```bash
# Check container is running
docker ps | grep coldquery

# Check health endpoint
curl http://localhost:19002/health

# View logs
docker logs coldquery
```

## Local Docker Deployment

For development and testing on your local machine:

```bash
# Build for your platform
docker build -t coldquery:local .

# Run locally
docker run -d \
  --name coldquery-local \
  -p 3000:3000 \
  -e PGHOST=host.docker.internal \
  -e PGPORT=5432 \
  -e PGUSER=postgres \
  -e PGPASSWORD=your_password \
  -e PGDATABASE=postgres \
  coldquery:local

# Verify
curl http://localhost:3000/health

# Cleanup
docker stop coldquery-local && docker rm coldquery-local
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `3000` | Server port (internal) |
| `NODE_ENV` | `production` | Node environment |
| `PGHOST` | `localhost` | PostgreSQL host |
| `PGPORT` | `5432` | PostgreSQL port |
| `PGUSER` | `postgres` | PostgreSQL user |
| `PGPASSWORD` | - | PostgreSQL password |
| `PGDATABASE` | `postgres` | PostgreSQL database name |
| `LOG_LEVEL` | `info` | Log level (debug, info, warn, error) |
| `MCP_ALLOWED_ORIGINS` | - | Comma-separated allowed origins |

See [CONFIGURATION.md](CONFIGURATION.md) for complete configuration options.

## MCP Client Configuration

### HTTP Transport (Remote Server)

Add to your MCP client configuration (e.g., `.mcp.json`):

```json
{
  "mcpServers": {
    "coldquery": {
      "type": "http",
      "url": "http://your-server:19002/mcp"
    }
  }
}
```

### Tailscale URL

If using Tailscale for access:

```json
{
  "mcpServers": {
    "coldquery": {
      "type": "http",
      "url": "http://100.65.x.x:19002/mcp"
    }
  }
}
```

## Docker Networking

### Connecting to PostgreSQL in Docker

If PostgreSQL runs in a Docker container:

1. Create a network:
   ```bash
   docker network create postgres_network
   ```

2. Connect PostgreSQL to the network:
   ```bash
   docker network connect postgres_network postgres_container
   ```

3. Use the container name as hostname:
   ```bash
   -e PGHOST=postgres_container
   ```

### Connecting to Host PostgreSQL

If PostgreSQL runs on the host:

```bash
-e PGHOST=host.docker.internal  # macOS/Windows
-e PGHOST=172.17.0.1            # Linux (Docker bridge IP)
```

## GitHub Actions Deployment

Automated deployment triggers on push to `main` branch.

### Required Secrets

Configure in repository settings:

| Secret | Description |
|--------|-------------|
| `PI_SSH_PRIVATE_KEY` | SSH private key for target server |
| `PI_POSTGRES_PASSWORD` | PostgreSQL password |
| `TS_OAUTH_CLIENT_ID` | Tailscale OAuth client ID |
| `TS_OAUTH_SECRET` | Tailscale OAuth client secret |

Configure at: `https://github.com/Coldaine/ColdQuery/settings/secrets/actions`

See [WORKFLOWS.md](../.github/WORKFLOWS.md) for detailed workflow documentation.

## Troubleshooting

### Container won't start

```bash
# Check logs
docker logs coldquery

# Check if port is in use
ss -tlnp | grep 19002
# or
netstat -tlnp | grep 19002
```

### Health check failing

```bash
# Test inside container
docker exec coldquery wget --no-verbose --tries=1 --spider http://localhost:3000/health

# Check if server.js exists
docker exec coldquery ls -la dist/packages/core/src/
```

### Can't connect to PostgreSQL

```bash
# Test connection from inside container
docker exec coldquery sh -c 'nc -zv $PGHOST $PGPORT'

# Verify environment variables
docker exec coldquery env | grep PG
```

### Can't connect from network

- Ensure container is on correct Docker network
- Check firewall rules: `sudo iptables -L`
- Verify Tailscale is running if using Tailscale IP
- Test with curl: `curl -v http://server:port/health`

### Image build fails

```bash
# Ensure buildx is available
docker buildx version

# Create builder if needed
docker buildx create --use --name multiarch

# Check available platforms
docker buildx inspect --bootstrap
```

## Health Checks

The server provides a health endpoint:

```
GET /health
```

Response:
```json
{
  "status": "healthy",
  "database": "your_database",
  "version": "PostgreSQL 16.1...",
  "server_time": "2025-01-21T..."
}
```

For Docker health checks:

```dockerfile
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:3000/health || exit 1
```

## Security Considerations

1. **Never expose directly to internet** - Use Tailscale or reverse proxy
2. **Use strong PostgreSQL password** - Inject via secrets, not in command
3. **Network isolation** - Use Docker networks to limit access
4. **Log monitoring** - Set up log aggregation for production

See [SECURITY.md](SECURITY.md) for complete security model.
