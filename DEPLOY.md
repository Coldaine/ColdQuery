# ColdQuery Deployment Guide

This guide covers manual deployment of ColdQuery to Raspberry Pi. For automated deployment, see the GitHub Actions workflow in `.github/workflows/deploy.yml`.

## Prerequisites

- SSH access to `raspberryoracle` (passwordless)
- Docker installed on the Pi
- Docker Buildx installed locally (for ARM64 cross-compilation)

## Manual Deployment

### 1. Build the ARM64 Image

```bash
# From the project root
docker buildx build --platform linux/arm64 -t coldquery:VERSION --load .
```

Replace `VERSION` with your desired tag (e.g., `latest`, `v1.0.0`, or a git SHA).

### 2. Transfer to Raspberry Pi

```bash
docker save coldquery:VERSION | gzip | ssh coldaine@raspberryoracle 'gunzip | docker load'
```

### 3. Run the Container

```bash
ssh coldaine@raspberryoracle

# Stop existing container (if running)
docker stop coldquery 2>/dev/null || true
docker rm coldquery 2>/dev/null || true

# Start new container (connects to postgres_network for DB access)
docker run -d \
  --name coldquery \
  --restart unless-stopped \
  --network postgres_network \
  -p 19002:3000 \
  -e PGHOST=llm_postgres \
  -e PGPORT=5432 \
  -e PGUSER=llm_archival \
  -e PGPASSWORD=<your-password> \
  -e PGDATABASE=llm_archival \
  coldquery:VERSION
```

### 4. Verify Deployment

```bash
# Check container is running
docker ps | grep coldquery

# Check health endpoint
curl http://100.65.198.61:19002/health

# View logs
docker logs coldquery
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

## MCP Client Configuration

Add to your MCP client configuration (e.g., `.mcp.json`):

```json
{
  "mcpServers": {
    "coldquery": {
      "type": "http",
      "url": "http://100.65.198.61:19002/mcp"
    }
  }
}
```

## Troubleshooting

### Container won't start

```bash
# Check logs
docker logs coldquery

# Check if port is in use
ss -tlnp | grep 19002
```

### Health check failing

```bash
# Test inside container
docker exec coldquery wget --no-verbose --tries=1 --spider http://localhost:3000/health

# Check if server.js exists
docker exec coldquery ls -la dist/packages/core/src/
```

### Can't connect from network

- Ensure container is on `postgres_network` (for PostgreSQL access via Docker DNS)
- Check firewall rules on Pi: `sudo iptables -L`
- Verify Tailscale is running if using Tailscale IP

### Image build fails

```bash
# Ensure buildx is available
docker buildx version

# Create builder if needed
docker buildx create --use --name multiarch

# Check available platforms
docker buildx inspect --bootstrap
```

## GitHub Actions Setup

The automated deployment requires these secrets in your GitHub repository:

| Secret | Description |
|--------|-------------|
| `PI_SSH_PRIVATE_KEY` | SSH private key for raspberryoracle |
| `PI_POSTGRES_PASSWORD` | PostgreSQL password |
| `TS_OAUTH_CLIENT_ID` | Tailscale OAuth client ID |
| `TS_OAUTH_SECRET` | Tailscale OAuth client secret |

Configure at: `https://github.com/Coldaine/ColdQuery/settings/secrets/actions`
