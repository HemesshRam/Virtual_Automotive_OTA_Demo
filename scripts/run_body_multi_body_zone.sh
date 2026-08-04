#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

export OTA_VEHICLE_TOPOLOGY=vehicle/topology.body_multi_ecu.json
export OTA_USE_ZONAL_CONTROLLERS=1
export OTA_ZONE_TRANSPORT=tcp
export OTA_ECU_CLUSTER_CAN_CHANNEL=vcan_bcm

sudo ./scripts/setup_vcan_zones.sh
export LOCAL_UID="${LOCAL_UID:-$(id -u)}"
export LOCAL_GID="${LOCAL_GID:-$(id -g)}"

echo
echo "Body multi-ECU topology"
echo "Terminal role : shared body_zone controller"
echo "Owns          : BCM ECU + Cluster ECU"
echo "CAN channel   : vcan_bcm"
echo "Service       : zone-body"
echo

docker compose -f docker/docker-compose.ecus.yml \
    --profile deep-zonal \
    up --build zone-body
