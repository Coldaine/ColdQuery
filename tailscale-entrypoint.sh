#!/bin/sh
set -e

# Start tailscaled in the background
/usr/local/bin/containerboot &
sleep 5

# Wait for tailscale to be ready
while ! tailscale status &>/dev/null; do
  echo "Waiting for Tailscale to start..."
  sleep 2
done

# Setup serve configuration
tailscale serve --bg --https=443 3000

# Keep container running
wait
