# GitHub Actions Workflows

This document describes the CI/CD pipelines for ColdQuery.

## Overview

ColdQuery uses a two-workflow CI/CD system:
1. **ci.yml** - Runs tests and linting on PRs and pushes
2. **deploy.yml** - Deploys code changes to Raspberry Pi

## ci.yml - Continuous Integration

**Location:** `.github/workflows/ci.yml`

### Trigger

- Pull requests to `main` branch
- Pushes to `main` branch

### Jobs

#### 1. lint (Lint and Type Check)
- Runs pre-commit hooks (Ruff formatting/linting)
- Runs mypy type checking
- Auto-commits formatting fixes on PRs

#### 2. unit-tests
- Runs unit tests (`tests/unit/`)
- Generates coverage report
- Uploads coverage to Codecov

#### 3. integration-tests
- Runs integration tests (`tests/integration/`)
- Uses PostgreSQL 16 service container
- Currently set to `continue-on-error: true` (known test failures)

#### 4. docker-build
- Tests building both Docker images:
  - `Dockerfile` - Full image with code baked in
  - `Dockerfile.deps` - Deps-only image for Pi deployment
- Uses buildx with layer caching

### Environment

All jobs run on `ubuntu-latest` with Python 3.12.

## deploy.yml - Automated Deployment

**Location:** `.github/workflows/deploy.yml`

### Overview

Deploys code changes to Raspberry Pi using a **deps-image + mounted-code** approach. The deployment does NOT rebuild the Docker image unless dependencies change.

### Trigger

| Event | Condition |
|-------|-----------|
| Push | `main` branch, when `coldquery/`, `Dockerfile.deps`, `docker-compose.deploy.yml`, or `pyproject.toml` change |
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
│  2. Set up Tailscale                                            │
│       └── OAuth authentication with tag:ci                      │
│                                                                  │
│  3. Set up SSH                                                  │
│       └── Configure private key for Pi access                   │
│                                                                  │
│  4. Sync code to Pi                                             │
│       └── rsync code to /opt/coldquery/ (excludes .git, cache) │
│                                                                  │
│  5. Deploy on Raspberry Pi                                      │
│       ├── Create .env file with secrets                         │
│       ├── Check if coldquery-deps:latest image exists          │
│       ├── Build deps image if missing (first deploy only)       │
│       └── Restart container (code is mounted, not copied)       │
│                                                                  │
│  6. Wait for health check                                       │
│       └── Poll /health endpoint (30 attempts, 5s interval)      │
│                                                                  │
│  7. Rebuild deps if pyproject.toml changed                      │
│       └── docker build -f Dockerfile.deps && restart            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Deployment Model

**Key Innovation**: The production deployment uses a **two-layer approach**:

1. **Deps Image** (`coldquery-deps:latest`):
   - Built from `Dockerfile.deps`
   - Contains Python 3.12 and dependencies (fastmcp, asyncpg, pydantic)
   - Only rebuilt when `pyproject.toml` changes
   - Stored locally on the Pi (not pushed to registry)

2. **Mounted Code**:
   - Source code in `/opt/coldquery/coldquery/` is mounted into the container
   - Code changes require only `git pull && docker restart`
   - No image rebuild needed for code-only changes

**Benefits**:
- Fast deployments (2-5 seconds for code changes)
- No need to push/pull large images
- No cross-compilation needed
- Simple rollback (just `git checkout` and restart)

### Container Configuration

```yaml
services:
  coldquery:
    image: coldquery-deps:latest
    container_name: coldquery-server
    volumes:
      - /opt/coldquery/coldquery:/app/coldquery:ro
    ports:
      - "19002:19002"
    environment:
      DB_HOST: raspberryoracle.tail4c911d.ts.net
      DB_PORT: 5432
      DB_USER: llm_archival
      DB_PASSWORD: <from secrets>
      DB_DATABASE: llm_archival
      HOST: 0.0.0.0
      PORT: 19002
    restart: unless-stopped
```

### Required Secrets

Configure in repository settings (Settings → Secrets and variables → Actions):

| Secret | Description |
|--------|-------------|
| `TS_OAUTH_CLIENT_ID` | Tailscale OAuth client ID |
| `TS_OAUTH_SECRET` | Tailscale OAuth client secret |
| `PI_SSH_KEY` | SSH private key for Pi (ed25519) |
| `PI_HOST` | Pi Tailscale hostname (raspberryoracle.tail4c911d.ts.net) |
| `PI_USER` | SSH user on Pi (coldaine) |
| `DB_HOST` | PostgreSQL host |
| `DB_PORT` | PostgreSQL port (5432) |
| `DB_USER` | PostgreSQL user |
| `DB_PASSWORD` | PostgreSQL password |
| `DB_DATABASE` | PostgreSQL database name |

### Tailscale OAuth Setup

1. Go to [Tailscale Admin Console](https://login.tailscale.com/admin/settings/oauth)
2. Create new OAuth client
3. Grant permissions: `Devices: write`
4. Add tag: `tag:ci`
5. Copy client ID and secret to GitHub secrets

### Tailscale ACL Requirements

Your Tailscale ACL must allow CI to access the Pi:

```json
{
  "acls": [
    {
      "action": "accept",
      "src": ["tag:ci"],
      "dst": ["raspberryoracle:*"]
    }
  ],
  "tagOwners": {
    "tag:ci": ["autogroup:admin"]
  }
}
```

### Health Check

The deployment waits up to 150 seconds (30 attempts × 5s) for the container to become healthy:

```bash
docker container inspect coldquery-server --format '{{.State.Health.Status}}'
# Must return: healthy
```

The container's healthcheck calls `wget --spider http://localhost:19002/health` every 30 seconds.

### Troubleshooting

#### Deployment Fails with "Health check failed"

**Check container logs:**
```bash
ssh raspberrypi "docker logs coldquery-server --tail 50"
```

**Common causes:**
- Database connection failed (check .env credentials)
- Port 19002 already in use
- Code syntax error (pre-commit hooks should catch this)

#### Tailscale Connection Fails

**Solutions:**
1. Verify OAuth credentials in GitHub secrets
2. Check Tailscale ACL allows `tag:ci` → `raspberryoracle`
3. Verify Pi is online: `tailscale status | grep raspberryoracle`

#### SSH Connection Fails

**Solutions:**
1. Verify `PI_SSH_KEY` matches Pi's `~/.ssh/authorized_keys`
2. Check Pi is accessible via Tailscale: `ssh raspberrypi`
3. Verify `PI_HOST` and `PI_USER` secrets are correct

#### rsync Fails

**Common causes:**
- `/opt/coldquery/` directory doesn't exist (create with `sudo mkdir -p /opt/coldquery && sudo chown $USER:$USER /opt/coldquery`)
- Permission denied (check directory ownership)
- Network timeout (check Tailscale connection)

### Local Testing

Test the deployment process locally:

```bash
# Build deps image
docker build -f Dockerfile.deps -t coldquery-deps:latest .

# Run with mounted code (like production)
docker run -d \
  --name coldquery-test \
  -v $(pwd)/coldquery:/app/coldquery:ro \
  -p 19002:19002 \
  -e DB_HOST=raspberryoracle.tail4c911d.ts.net \
  -e DB_PORT=5432 \
  -e DB_USER=llm_archival \
  -e DB_PASSWORD=<password> \
  -e DB_DATABASE=llm_archival \
  coldquery-deps:latest

# Check health
curl http://localhost:19002/health

# View logs
docker logs coldquery-test -f

# Cleanup
docker stop coldquery-test && docker rm coldquery-test
```

### Manual Deployment

If automated deployment fails, deploy manually:

```bash
# On your local machine
git push origin main

# SSH to Pi
ssh raspberrypi

# Update code
cd /opt/coldquery
git pull

# Restart container (fast - just code reload)
docker restart coldquery-server

# If dependencies changed
docker build -f Dockerfile.deps -t coldquery-deps:latest .
docker compose -f docker-compose.deploy.yml up -d --force-recreate

# Verify
curl http://localhost:19002/health
docker logs coldquery-server --tail 20
```

### Update Process

#### Code-Only Changes
Most common case - no dependency changes:
```bash
# Automated via GitHub Actions on push to main
# Or manually:
ssh raspberrypi "cd /opt/coldquery && git pull && docker restart coldquery-server"
```

#### Dependency Changes
When `pyproject.toml` changes:
```bash
# Automated via GitHub Actions (detects pyproject.toml change)
# Or manually:
ssh raspberrypi
cd /opt/coldquery
git pull
docker build -f Dockerfile.deps -t coldquery-deps:latest .
docker compose -f docker-compose.deploy.yml up -d --force-recreate
```

### Monitoring

After deployment, verify the service is running:

```bash
# Via Tailscale (public endpoint)
curl https://raspberryoracle.tail4c911d.ts.net/health

# Via SSH to Pi (internal)
ssh raspberrypi "curl http://localhost:19002/health"

# Check container status
ssh raspberrypi "docker ps | grep coldquery"

# View logs
ssh raspberrypi "docker logs coldquery-server --tail 50 -f"
```

### Rollback

If a deployment breaks production:

```bash
ssh raspberrypi
cd /opt/coldquery

# Find the last working commit
git log --oneline

# Rollback code
git checkout <commit-hash>

# Restart container
docker restart coldquery-server

# Verify
curl http://localhost:19002/health
```

## Security Notes

- SSH private key is used only during deployment and cleaned up
- Tailscale OAuth token has limited scope (`tag:ci` only)
- Database credentials are injected via secrets, never in code
- Container runs as non-root user
- Code is mounted read-only (`:ro` flag)

## Future Improvements

Potential workflow enhancements:
- Blue/green deployment with zero downtime
- Automated rollback on health check failure
- Slack/Discord notifications on deployment success/failure
- Performance regression testing
- Automated database migrations
