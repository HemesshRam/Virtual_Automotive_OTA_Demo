#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

docker compose -f docker/docker-compose.ecus.yml --profile deep-zonal down --remove-orphans
docker rm -f \
    virtual-ota-gateway \
    virtual-ota-bcm \
    virtual-ota-cluster \
    virtual-ota-zone-gateway \
    virtual-ota-zone-body \
    virtual-ota-zone-cluster \
    virtual-ota-zone-cockpit \
    >/dev/null 2>&1 || true
