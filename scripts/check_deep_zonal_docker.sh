#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

required_containers=(
    virtual-ota-gateway
    virtual-ota-zone-gateway
    virtual-ota-zone-body
    virtual-ota-zone-cluster
    virtual-ota-bcm
    virtual-ota-cluster
)

echo "[CHECK] Deep zonal Docker containers"

for container in "${required_containers[@]}"; do
    status="$(docker inspect -f '{{.State.Status}}' "${container}" 2>/dev/null || true)"
    if [[ "${status}" != "running" ]]; then
        echo "[FAIL] ${container} is not running; status=${status:-missing}" >&2
        exit 1
    fi
    echo "[OK] ${container} running"
done

echo
echo "[CHECK] Zone TCP services"
python3 scripts/check_zone_services.py
