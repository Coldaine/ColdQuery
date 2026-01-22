# Tailscale Services Architecture

This document describes the modern "Tailscale Services" architecture for ColdQuery.

## Overview

We have transitioned from manual IP/Port management to named Tailscale services. This decouples the application from the underlying infrastructure IP addresses.

### Services

| Service Name | Protocol | Port | Replaces |
| :--- | :--- | :--- | :--- |
| `svc:coldquery` | TCP & HTTP | 19002 | `http://100.65.x.x:19002` |
| `svc:config-db` | TCP | 5432 | `postgres://100.65.198.61` |

## Deployment

Deployment is now handled via `docker-compose` which includes a Tailscale sidecar container.

### Prerequisites

1.  **Tailscale Auth Key**: You need a reusable, tagged auth key (e.g., `tag:container`) from the Tailscale Admin Console.
2.  **Environment Variables**:
    *   `TS_AUTHKEY`: The Tailscale auth key.
    *   `PGPASSWORD`: The PostgreSQL password.

### Running Manually

1.  Ensure you have the `docker-compose.deploy.yml` file (typically renamed to `docker-compose.yml` on the server).
2.  Run:

    ```bash
    export TS_AUTHKEY=tskey-auth-...
    export PGPASSWORD=your_password
    docker-compose up -d
    ```

### Accessing the Service

You can now access the service from any device on your Tailscale network using the magic DNS name:

```
http://svc.coldquery
```

(Note: Ensure your Tailscale ACLs allow access to `tag:container` or the specific machine/service).

## Configuration Details

*   **ColdQuery Container**:
    *   Does NOT bind ports to the host.
    *   Uses `network_mode: service:tailscale` to share the network namespace with the Tailscale sidecar.
    *   Connects to the database via `svc.config-db`.

*   **Tailscale Sidecar**:
    *   Advertises `svc-coldquery` hostname.
    *   Stores state in a docker volume `tailscale-data` to persist identity across restarts.
