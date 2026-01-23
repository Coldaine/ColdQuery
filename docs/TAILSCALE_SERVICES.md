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
    *   Runs `tailscale serve --bg 3000` to proxy incoming traffic to the application port 3000.
    *   Stores state in a docker volume `tailscale-data` to persist identity across restarts.
