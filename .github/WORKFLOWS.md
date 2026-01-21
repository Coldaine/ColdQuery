# GitHub Actions Workflows

This document describes the CI/CD pipelines for ColdQuery.

## deploy.yml - Automated Deployment

**Location:** `.github/workflows/deploy.yml`

### Overview

Automated deployment pipeline that builds an ARM64 Docker image and deploys to a Raspberry Pi via Tailscale.

### Trigger

| Event | Condition |
|-------|-----------|
| Push | `main` branch only |
| Manual | `workflow_dispatch` (Actions tab) |

### Pipeline Steps

```
┌─────────────────────────────────────────────────────────────────┐
│                    Deployment Pipeline                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Checkout code                                               │
│       └── Clone repository                                       │
│                                                                  │
│  2. Set up QEMU                                                  │
│       └── Enable ARM64 emulation for cross-compilation          │
│                                                                  │
│  3. Set up Docker Buildx                                        │
│       └── Multi-platform build support                          │
│                                                                  │
│  4. Build ARM64 image                                           │
│       └── docker buildx build --platform linux/arm64            │
│       └── Output: image.tar (gzip compressed)                   │
│                                                                  │
│  5. Connect to Tailscale                                        │
│       └── OAuth authentication                                   │
│       └── Tag: ci                                               │
│                                                                  │
│  6. Set up SSH                                                  │
│       └── Configure private key                                 │
│       └── Add Pi to known_hosts                                 │
│                                                                  │
│  7. Transfer image to Pi                                        │
│       └── gzip | ssh | gunzip | docker load                     │
│                                                                  │
│  8. Deploy container                                            │
│       └── Stop existing container                               │
│       └── Run new container                                     │
│       └── Wait for health check (30 attempts)                   │
│                                                                  │
│  9. Cleanup old images                                          │
│       └── docker image prune -f                                 │
│                                                                  │
│ 10. Cleanup local artifacts                                     │
│       └── Remove image.tar and SSH key                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Environment Variables

| Variable | Value | Description |
|----------|-------|-------------|
| `IMAGE_NAME` | `coldquery` | Docker image name |
| `PI_HOST` | `100.65.198.61` | Raspberry Pi Tailscale IP |
| `PI_USER` | `coldaine` | SSH user on Pi |
| `CONTAINER_NAME` | `coldquery` | Docker container name |
| `CONTAINER_PORT` | `19002` | Host port mapping |

### Required Secrets

These must be configured in repository settings (Settings → Secrets and variables → Actions):

| Secret | Description | How to Obtain |
|--------|-------------|---------------|
| `TS_OAUTH_CLIENT_ID` | Tailscale OAuth client ID | Tailscale Admin Console → Settings → OAuth clients |
| `TS_OAUTH_SECRET` | Tailscale OAuth client secret | Same as above |
| `PI_SSH_PRIVATE_KEY` | SSH private key for Pi | `cat ~/.ssh/id_ed25519` (or generate new) |
| `PI_POSTGRES_PASSWORD` | PostgreSQL password on Pi | Your database password |

### Tailscale OAuth Setup

1. Go to [Tailscale Admin Console](https://login.tailscale.com/admin/settings/oauth)
2. Create new OAuth client
3. Grant permissions:
   - `Devices: write` (to join network)
   - Tags: `tag:ci`
4. Copy client ID and secret to GitHub secrets

### Tailscale ACL Requirements

Your Tailscale ACL must allow the CI tag to access the server:

```json
{
  "acls": [
    {
      "action": "accept",
      "src": ["tag:ci"],
      "dst": ["tag:server:*"]
    }
  ],
  "tagOwners": {
    "tag:ci": ["autogroup:admin"],
    "tag:server": ["autogroup:admin"]
  }
}
```

### Container Configuration

The deployed container runs with:

```bash
docker run -d \
  --name coldquery \
  --restart unless-stopped \
  --network postgres_network \
  -p 19002:3000 \
  -e PGHOST=llm_postgres \
  -e PGPORT=5432 \
  -e PGUSER=llm_archival \
  -e PGPASSWORD=<secret> \
  -e PGDATABASE=llm_archival \
  coldquery:latest
```

**Network:** Connects to existing `postgres_network` Docker network
**Restart Policy:** `unless-stopped` (survives reboots)
**Port:** `19002` → `3000` (internal)

### Health Check

The deployment waits up to 60 seconds for the container to become healthy:

```bash
for i in {1..30}; do
  wget --spider http://localhost:3000/health
  sleep 2
done
```

The container must respond to `/health` endpoint for successful deployment.

### Troubleshooting

#### Tailscale Connection Fails

**Error:**
```
Error: Unable to connect to Tailscale
```

**Solutions:**
1. Verify OAuth credentials are correct
2. Check OAuth client has required permissions
3. Verify ACL allows `tag:ci`
4. Check Tailscale service is operational

#### SSH Connection Fails

**Error:**
```
ssh: connect to host 100.65.198.61 port 22: Connection timed out
```

**Solutions:**
1. Verify Pi is online (`tailscale status`)
2. Check ACL allows CI → server access
3. Verify SSH is running on Pi
4. Check SSH key matches authorized_keys on Pi

#### Health Check Fails

**Error:**
```
Health check failed
```

**Solutions:**
1. Check container logs: `docker logs coldquery`
2. Verify PostgreSQL is accessible
3. Check environment variables are correct
4. Verify `postgres_network` exists

#### Docker Build Fails

**Error:**
```
ERROR: failed to solve: ...
```

**Solutions:**
1. Check Dockerfile syntax
2. Verify all files are committed
3. Check for missing dependencies
4. Review build logs for specific error

### Local Testing

Before pushing, test the build locally:

```bash
# Build for ARM64 (requires QEMU on x86)
docker buildx build --platform linux/arm64 -t coldquery:test .

# Or build for your platform
docker build -t coldquery:test .

# Run locally
docker run -d \
  --name coldquery-test \
  -p 3000:3000 \
  -e PGHOST=host.docker.internal \
  -e PGPORT=5432 \
  -e PGUSER=postgres \
  -e PGPASSWORD=yourpassword \
  -e PGDATABASE=postgres \
  coldquery:test

# Check health
curl http://localhost:3000/health

# View logs
docker logs coldquery-test

# Cleanup
docker stop coldquery-test && docker rm coldquery-test
```

### Manual Deployment

If you need to deploy manually:

1. Build image locally
2. Transfer to Pi via SSH:
   ```bash
   docker save coldquery:latest | gzip | ssh coldaine@raspberryoracle 'gunzip | docker load'
   ```
3. SSH to Pi and restart container:
   ```bash
   ssh coldaine@raspberryoracle
   docker stop coldquery && docker rm coldquery
   docker run -d ... coldquery:latest
   ```

### Security Notes

- SSH private key is used only during deployment and cleaned up
- Tailscale OAuth token has limited scope
- PostgreSQL password is injected via secret, never in code
- Container runs in isolated Docker network

## Future Workflows

Planned additions:

- **test.yml**: Run tests on pull requests
- **release.yml**: Create GitHub releases with changelogs
- **security.yml**: Dependency vulnerability scanning
