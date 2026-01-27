# Phase 5: Docker, CI/CD, and Deployment

Production deployment infrastructure with Docker, GitHub Actions CI/CD, and Raspberry Pi deployment.

**Estimated Additions**: ~300 lines of config + docs

---

## Overview

### What This Phase Delivers

✅ **Multi-stage Dockerfile** - Optimized Python image
✅ **Docker Compose** - Local development and deployment stacks
✅ **GitHub Actions CI/CD** - Automated testing and deployment
✅ **ARM64 Build** - Cross-platform Docker images for Raspberry Pi
✅ **Tailscale Integration** - Secure private network deployment
✅ **Health Checks** - Container health monitoring
✅ **Deployment Documentation** - Complete deployment guide

---

## Part 1: Dockerfile

**File**: `Dockerfile`

```dockerfile
# Multi-stage build for optimized production image

# Stage 1: Builder
FROM python:3.12-alpine AS builder

WORKDIR /build

# Install build dependencies
RUN apk add --no-cache \
    gcc \
    musl-dev \
    postgresql-dev \
    python3-dev

# Copy dependency files
COPY pyproject.toml ./
COPY coldquery ./coldquery

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

# Stage 2: Runtime
FROM python:3.12-alpine

WORKDIR /app

# Install runtime dependencies
RUN apk add --no-cache \
    libpq \
    wget \
    && addgroup -g 1000 coldquery \
    && adduser -D -u 1000 -G coldquery coldquery

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY coldquery ./coldquery
COPY pyproject.toml ./

# Switch to non-root user
USER coldquery

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOST=0.0.0.0 \
    PORT=3000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget --spider -q http://localhost:${PORT}/health || exit 1

# Expose port
EXPOSE 3000

# Run server
CMD ["python", "-m", "coldquery.server", "--transport", "http"]
```

---

## Part 2: Docker Compose (Development)

**File**: `docker-compose.yml`

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:16-alpine
    container_name: coldquery-postgres
    environment:
      POSTGRES_USER: mcp
      POSTGRES_PASSWORD: mcp
      POSTGRES_DB: mcp_test
    ports:
      - "5433:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U mcp"]
      interval: 10s
      timeout: 5s
      retries: 5

  coldquery:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: coldquery-server
    environment:
      DB_HOST: postgres
      DB_PORT: 5432
      DB_USER: mcp
      DB_PASSWORD: mcp
      DB_DATABASE: mcp_test
      HOST: 0.0.0.0
      PORT: 3000
    ports:
      - "3000:3000"
    depends_on:
      postgres:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "wget", "--spider", "-q", "http://localhost:3000/health"]
      interval: 30s
      timeout: 5s
      retries: 3

volumes:
  postgres_data:
```

---

## Part 3: Docker Compose (Production with Tailscale)

**File**: `docker-compose.deploy.yml`

```yaml
version: '3.8'

services:
  tailscale:
    image: tailscale/tailscale:latest
    container_name: coldquery-tailscale
    hostname: coldquery-server
    environment:
      - TS_AUTHKEY=${TS_AUTHKEY}
      - TS_STATE_DIR=/var/lib/tailscale
      - TS_EXTRA_ARGS=--advertise-tags=tag:server
    volumes:
      - tailscale_data:/var/lib/tailscale
      - /dev/net/tun:/dev/net/tun
    cap_add:
      - NET_ADMIN
      - SYS_MODULE
    restart: unless-stopped
    network_mode: host

  coldquery:
    build:
      context: .
      dockerfile: Dockerfile
      platforms:
        - linux/arm64
    container_name: coldquery-server
    environment:
      DB_HOST: ${DB_HOST}
      DB_PORT: ${DB_PORT}
      DB_USER: ${DB_USER}
      DB_PASSWORD: ${DB_PASSWORD}
      DB_DATABASE: ${DB_DATABASE}
      HOST: 100.0.0.0  # Tailscale subnet
      PORT: 3000
    ports:
      - "3000:3000"
    depends_on:
      - tailscale
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "wget", "--spider", "-q", "http://localhost:3000/health"]
      interval: 30s
      timeout: 5s
      retries: 3

volumes:
  tailscale_data:
```

---

## Part 4: Environment Configuration

**File**: `.env.example`

```bash
# Database Configuration
DB_HOST=localhost
DB_PORT=5433
DB_USER=mcp
DB_PASSWORD=mcp
DB_DATABASE=mcp_test

# Server Configuration
HOST=0.0.0.0
PORT=3000

# Debug Mode
DEBUG=false

# Tailscale (for production deployment)
TS_AUTHKEY=tskey-auth-xxxxxxxxxxxxx
```

**File**: `.dockerignore`

```
.git
.github
.vscode
__pycache__
*.pyc
*.pyo
*.pyd
.pytest_cache
.coverage
htmlcov
*.egg-info
dist
build
node_modules
.env
.env.local
docs/
tests/
legacy/
.ruff_cache
.mypy_cache
*.md
!README.md
```

---

## Part 5: GitHub Actions - CI Pipeline

**File**: `.github/workflows/ci.yml`

```yaml
name: CI

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  lint:
    name: Lint and Type Check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install --upgrade pip
          pip install -e ".[dev]"

      - name: Run Ruff
        run: ruff check coldquery/ tests/

      - name: Run mypy
        run: mypy coldquery/

  unit-tests:
    name: Unit Tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install --upgrade pip
          pip install -e ".[dev]"

      - name: Run unit tests
        run: pytest tests/unit/ -v --cov=coldquery --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          file: ./coverage.xml
          fail_ci_if_error: false

  integration-tests:
    name: Integration Tests
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: mcp
          POSTGRES_PASSWORD: mcp
          POSTGRES_DB: mcp_test
        ports:
          - 5433:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install --upgrade pip
          pip install -e ".[dev]"

      - name: Run integration tests
        run: pytest tests/integration/ -v
        env:
          DB_HOST: localhost
          DB_PORT: 5433
          DB_USER: mcp
          DB_PASSWORD: mcp
          DB_DATABASE: mcp_test

  docker-build:
    name: Docker Build Test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build Docker image
        uses: docker/build-push-action@v5
        with:
          context: .
          push: false
          tags: coldquery:test
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

---

## Part 6: GitHub Actions - Deployment Pipeline

**File**: `.github/workflows/deploy.yml`

```yaml
name: Deploy to Raspberry Pi

on:
  push:
    branches: [main]
    paths:
      - 'coldquery/**'
      - 'Dockerfile'
      - 'docker-compose.deploy.yml'
  workflow_dispatch:

jobs:
  build-and-deploy:
    name: Build ARM64 Image and Deploy
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up QEMU
        uses: docker/setup-qemu-action@v3
        with:
          platforms: arm64

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build ARM64 Docker Image
        uses: docker/build-push-action@v5
        with:
          context: .
          platforms: linux/arm64
          tags: coldquery:arm64-latest
          outputs: type=docker,dest=/tmp/coldquery-arm64.tar
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Copy image to Raspberry Pi
        env:
          SSH_PRIVATE_KEY: ${{ secrets.RASPBERRY_PI_SSH_KEY }}
        run: |
          mkdir -p ~/.ssh
          echo "$SSH_PRIVATE_KEY" > ~/.ssh/id_ed25519
          chmod 600 ~/.ssh/id_ed25519
          ssh-keyscan -H raspberrypi >> ~/.ssh/known_hosts

          scp -i ~/.ssh/id_ed25519 /tmp/coldquery-arm64.tar pmacl@raspberrypi:/tmp/
          scp -i ~/.ssh/id_ed25519 docker-compose.deploy.yml pmacl@raspberrypi:/opt/coldquery/docker-compose.yml

      - name: Deploy on Raspberry Pi
        env:
          SSH_PRIVATE_KEY: ${{ secrets.RASPBERRY_PI_SSH_KEY }}
          DB_HOST: ${{ secrets.DB_HOST }}
          DB_PORT: ${{ secrets.DB_PORT }}
          DB_USER: ${{ secrets.DB_USER }}
          DB_PASSWORD: ${{ secrets.DB_PASSWORD }}
          DB_DATABASE: ${{ secrets.DB_DATABASE }}
          TS_AUTHKEY: ${{ secrets.TAILSCALE_AUTH_KEY }}
        run: |
          ssh -i ~/.ssh/id_ed25519 pmacl@raspberrypi << 'EOF'
            cd /opt/coldquery

            # Load new image
            docker load -i /tmp/coldquery-arm64.tar
            rm /tmp/coldquery-arm64.tar

            # Create .env file
            cat > .env << ENVEOF
            DB_HOST=${{ secrets.DB_HOST }}
            DB_PORT=${{ secrets.DB_PORT }}
            DB_USER=${{ secrets.DB_USER }}
            DB_PASSWORD=${{ secrets.DB_PASSWORD }}
            DB_DATABASE=${{ secrets.DB_DATABASE }}
            TS_AUTHKEY=${{ secrets.TAILSCALE_AUTH_KEY }}
            ENVEOF

            # Stop existing containers
            docker-compose down

            # Start new containers
            docker-compose up -d

            # Wait for health check
            sleep 10
            docker ps

            # Verify health
            curl -f http://localhost:3000/health || exit 1

            echo "✅ Deployment successful"
          EOF
```

---

## Part 7: Deployment Documentation

**File**: `docs/DEPLOYMENT.md`

```markdown
# ColdQuery Deployment Guide

## Prerequisites

- Docker and Docker Compose installed
- PostgreSQL database (local or remote)
- For production: Tailscale account and auth key

---

## Local Development Deployment

### 1. Start with Docker Compose

\`\`\`bash
# Start PostgreSQL and ColdQuery
docker-compose up -d

# View logs
docker-compose logs -f

# Check health
curl http://localhost:3000/health

# Stop services
docker-compose down
\`\`\`

### 2. Environment Configuration

Copy `.env.example` to `.env` and configure:

\`\`\`bash
DB_HOST=postgres
DB_PORT=5432
DB_USER=mcp
DB_PASSWORD=mcp
DB_DATABASE=mcp_test
\`\`\`

---

## Production Deployment (Raspberry Pi)

### 1. Server Setup

\`\`\`bash
# On Raspberry Pi
sudo apt update
sudo apt install docker.io docker-compose

# Add user to docker group
sudo usermod -aG docker $USER

# Create deployment directory
sudo mkdir -p /opt/coldquery
sudo chown $USER:$USER /opt/coldquery
\`\`\`

### 2. Tailscale Setup

\`\`\`bash
# Install Tailscale
curl -fsSL https://tailscale.com/install.sh | sh

# Authenticate
sudo tailscale up

# Get auth key for containers
# https://login.tailscale.com/admin/settings/keys
\`\`\`

### 3. Configure GitHub Secrets

In GitHub repository settings, add secrets:

- `RASPBERRY_PI_SSH_KEY` - SSH private key for deployment
- `DB_HOST` - Database hostname
- `DB_PORT` - Database port
- `DB_USER` - Database username
- `DB_PASSWORD` - Database password
- `DB_DATABASE` - Database name
- `TAILSCALE_AUTH_KEY` - Tailscale auth key

### 4. Deploy

Push to main branch triggers automatic deployment:

\`\`\`bash
git push origin main
\`\`\`

Or trigger manually:

\`\`\`bash
gh workflow run deploy.yml
\`\`\`

### 5. Verify Deployment

\`\`\`bash
# SSH to Raspberry Pi
ssh raspberrypi

# Check containers
docker ps

# Check logs
docker-compose -f /opt/coldquery/docker-compose.yml logs -f

# Test health endpoint
curl http://localhost:3000/health
\`\`\`

---

## Manual Deployment

### 1. Build Docker Image

\`\`\`bash
# Build for ARM64 (Raspberry Pi)
docker buildx build --platform linux/arm64 -t coldquery:arm64 .

# Build for AMD64 (x86_64)
docker buildx build --platform linux/amd64 -t coldquery:amd64 .
\`\`\`

### 2. Save and Transfer Image

\`\`\`bash
# Save image
docker save coldquery:arm64 -o coldquery-arm64.tar

# Copy to server
scp coldquery-arm64.tar user@server:/tmp/

# On server: Load image
docker load -i /tmp/coldquery-arm64.tar
\`\`\`

### 3. Run Container

\`\`\`bash
docker run -d \
  --name coldquery \
  -p 3000:3000 \
  -e DB_HOST=your-db-host \
  -e DB_PORT=5432 \
  -e DB_USER=mcp \
  -e DB_PASSWORD=mcp \
  -e DB_DATABASE=mcp_prod \
  coldquery:arm64
\`\`\`

---

## Monitoring

### Health Checks

\`\`\`bash
# Check container health
docker ps

# Health endpoint
curl http://localhost:3000/health

# Container logs
docker logs coldquery-server -f
\`\`\`

### Resource Usage

\`\`\`bash
# Container stats
docker stats coldquery-server

# Disk usage
docker system df
\`\`\`

---

## Troubleshooting

### Container Won't Start

\`\`\`bash
# Check logs
docker logs coldquery-server

# Check health
docker inspect coldquery-server | grep Health

# Restart container
docker restart coldquery-server
\`\`\`

### Database Connection Issues

\`\`\`bash
# Test database connectivity
docker exec coldquery-server sh -c 'wget -q -O- http://localhost:3000/health'

# Check environment variables
docker exec coldquery-server env | grep DB_
\`\`\`

### Tailscale Issues

\`\`\`bash
# Check Tailscale status
docker exec coldquery-tailscale tailscale status

# Restart Tailscale
docker restart coldquery-tailscale
\`\`\`

---

## Backup and Restore

### Backup Database

\`\`\`bash
# Dump database
docker exec coldquery-postgres pg_dump -U mcp mcp_test > backup.sql
\`\`\`

### Restore Database

\`\`\`bash
# Restore from dump
docker exec -i coldquery-postgres psql -U mcp mcp_test < backup.sql
\`\`\`

---

## Updating

### Update via CI/CD

\`\`\`bash
# Push changes to main
git push origin main

# Deployment runs automatically
\`\`\`

### Manual Update

\`\`\`bash
# On Raspberry Pi
cd /opt/coldquery

# Pull latest code
git pull

# Rebuild and restart
docker-compose down
docker-compose build
docker-compose up -d
\`\`\`
\`\`\`

**File**: `docs/DEPLOY.md` (short version for README link)

```markdown
# Deployment

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for complete deployment guide.

## Quick Start

### Local Development

\`\`\`bash
docker-compose up -d
\`\`\`

### Production (Raspberry Pi)

Automatic via GitHub Actions on push to main.

Configure secrets in GitHub:
- RASPBERRY_PI_SSH_KEY
- DB_* (database credentials)
- TAILSCALE_AUTH_KEY
\`\`\`

---

## Part 8: README Updates

Update `README.md` to include Docker deployment:

```markdown
## Docker Deployment

### Local Development

\`\`\`bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f coldquery

# Stop services
docker-compose down
\`\`\`

### Production

See [DEPLOY.md](DEPLOY.md) for production deployment guide.

Build for ARM64 (Raspberry Pi):

\`\`\`bash
docker buildx build --platform linux/arm64 -t coldquery:arm64 .
\`\`\`
```

---

## Implementation Checklist

### Docker
- [ ] `Dockerfile` - Multi-stage Python build
- [ ] `.dockerignore` - Exclude unnecessary files
- [ ] `docker-compose.yml` - Development stack
- [ ] `docker-compose.deploy.yml` - Production stack with Tailscale
- [ ] `.env.example` - Environment template

### CI/CD
- [ ] `.github/workflows/ci.yml` - Lint, test, build
- [ ] `.github/workflows/deploy.yml` - ARM64 build + deploy
- [ ] Configure GitHub secrets

### Documentation
- [ ] `docs/DEPLOYMENT.md` - Complete deployment guide
- [ ] `docs/DEPLOY.md` - Quick reference
- [ ] Update `README.md` with Docker instructions

### Testing
- [ ] Test Docker build locally
- [ ] Test docker-compose stack
- [ ] Test ARM64 build with QEMU
- [ ] Verify health checks work

---

## Success Criteria

✅ Docker image builds successfully
✅ Multi-stage build reduces image size
✅ Health checks work correctly
✅ Docker Compose stack runs locally
✅ CI pipeline passes (lint, test, build)
✅ ARM64 image builds for Raspberry Pi
✅ Deployment pipeline deploys to Pi
✅ Tailscale integration works
✅ Documentation complete

---

## GitHub Secrets Configuration

Required secrets for deployment:

| Secret | Description | Example |
|--------|-------------|---------|
| `RASPBERRY_PI_SSH_KEY` | SSH private key | `-----BEGIN OPENSSH PRIVATE KEY-----...` |
| `DB_HOST` | Database host | `postgres.example.com` |
| `DB_PORT` | Database port | `5432` |
| `DB_USER` | Database user | `mcp` |
| `DB_PASSWORD` | Database password | `secure_password` |
| `DB_DATABASE` | Database name | `coldquery_prod` |
| `TAILSCALE_AUTH_KEY` | Tailscale auth key | `tskey-auth-xxxxx` |

Set via: Repository Settings → Secrets and variables → Actions → New repository secret
