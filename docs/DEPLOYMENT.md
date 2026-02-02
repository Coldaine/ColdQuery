# ColdQuery Deployment Guide

## Production Deployment (Raspberry Pi)

ColdQuery runs on a Raspberry Pi at `/opt/coldquery/`, exposed via Tailscale at:
- `https://raspberryoracle.tail4c911d.ts.net/` (proxies to port 19002)

### Architecture

```
┌─────────────────────────────────────────────────────┐
│ Raspberry Pi (raspberryoracle)                      │
│                                                     │
│  ┌─────────────────┐    ┌─────────────────────────┐│
│  │ coldquery-server│    │ llm_postgres            ││
│  │ (Docker)        │───▶│ (Docker)                ││
│  │                 │    │ PostgreSQL 18 + pgvector││
│  │ Code mounted    │    └─────────────────────────┘│
│  │ from host       │                               │
│  └────────┬────────┘                               │
│           │ :19002                                 │
│           ▼                                        │
│  ┌─────────────────┐                               │
│  │ Tailscale Serve │ ◀── https://raspberryoracle  │
│  │ (host service)  │     .tail4c911d.ts.net       │
│  └─────────────────┘                               │
└─────────────────────────────────────────────────────┘
```

### Deployment Model

The deployment uses a **deps-image + mounted-code** approach:

- `Dockerfile.deps` - Base image with Python 3.12 and dependencies (fastmcp, asyncpg, pydantic)
- `docker-compose.deploy.yml` - Mounts `/opt/coldquery/coldquery` into the container
- Code updates don't require image rebuilds

### Update Code

```bash
ssh raspberrypi
cd /opt/coldquery
git pull
docker restart coldquery-server
```

### Update Dependencies

Only needed when `pyproject.toml` changes:

```bash
ssh raspberrypi
cd /opt/coldquery
git pull
docker build -f Dockerfile.deps -t coldquery-deps:latest .
docker compose -f docker-compose.deploy.yml up -d
```

### Initial Setup

```bash
# Clone repo
sudo mkdir -p /opt/coldquery
sudo chown $USER:$USER /opt/coldquery
git clone https://github.com/korrektly/coldquery.git /opt/coldquery

# Create .env
cat > /opt/coldquery/.env << EOF
DB_HOST=raspberryoracle.tail4c911d.ts.net
DB_PORT=5432
DB_USER=llm_archival
DB_PASSWORD=<from bitwarden>
DB_DATABASE=llm_archival
EOF

# Build deps image and start
cd /opt/coldquery
docker build -f Dockerfile.deps -t coldquery-deps:latest .
docker compose -f docker-compose.deploy.yml up -d

# Expose via Tailscale (one-time)
tailscale serve --bg --https=443 http://localhost:19002
```

### Verify

```bash
# Health check
curl http://localhost:19002/health

# Via Tailscale
curl https://raspberryoracle.tail4c911d.ts.net/health
```

### Logs

```bash
docker logs coldquery-server -f
```

---

## Local Development

See [DEVELOPMENT.md](DEVELOPMENT.md) for local setup with `docker-compose.yml` (includes local Postgres).

---

## Files

| File | Purpose |
|------|---------|
| `Dockerfile` | Full image build (code baked in) - for CI/GHCR |
| `Dockerfile.deps` | Deps-only image (code mounted) - for Pi deployment |
| `docker-compose.yml` | Local dev with Postgres |
| `docker-compose.deploy.yml` | Production on Pi |
| `.env.example` | Environment template |
