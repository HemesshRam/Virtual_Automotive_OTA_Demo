#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

export OTA_VEHICLE_TOPOLOGY=vehicle/topology.body_multi_ecu.json
export OTA_USE_ZONAL_CONTROLLERS=1
export OTA_ZONE_TRANSPORT=tcp
export OTA_ECU_CLUSTER_CAN_CHANNEL=vcan_bcm

echo "[DEMO] Body zone owns two ECUs: BCM ECU + Cluster ECU"
echo "[DEMO] Cluster ECU is remapped from vcan_clus to vcan_bcm for this topology"

sudo ./scripts/setup_vcan_zones.sh
export LOCAL_UID="${LOCAL_UID:-$(id -u)}"
export LOCAL_GID="${LOCAL_GID:-$(id -g)}"

docker compose -f docker/docker-compose.ecus.yml --profile deep-zonal down --remove-orphans >/dev/null 2>&1 || true
docker rm -f virtual-ota-gateway virtual-ota-bcm virtual-ota-cluster virtual-ota-zone-gateway virtual-ota-zone-body virtual-ota-zone-cluster >/dev/null 2>&1 || true

docker compose -f docker/docker-compose.ecus.yml \
    --profile deep-zonal \
    up --build zone-gateway zone-body gateway bcm cluster
