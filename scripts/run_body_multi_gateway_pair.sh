#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

export OTA_VEHICLE_TOPOLOGY=vehicle/topology.body_multi_ecu.json
export OTA_USE_ZONAL_CONTROLLERS=1
export OTA_ZONE_TRANSPORT=tcp

sudo ./scripts/setup_vcan_zones.sh
export LOCAL_UID="${LOCAL_UID:-$(id -u)}"
export LOCAL_GID="${LOCAL_GID:-$(id -g)}"

echo
echo "Body multi-ECU topology"
echo "Terminal role : gateway_zone + Gateway ECU / central DoIP gateway"
echo "Services      : zone-gateway gateway"
echo

docker compose -f docker/docker-compose.ecus.yml \
    --profile deep-zonal \
    up --build zone-gateway gateway
