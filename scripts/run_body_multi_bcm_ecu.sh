#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

export OTA_VEHICLE_TOPOLOGY=vehicle/topology.body_multi_ecu.json
export OTA_ECU_BCM_CAN_CHANNEL=vcan_bcm

sudo ./scripts/setup_vcan_zones.sh
export LOCAL_UID="${LOCAL_UID:-$(id -u)}"
export LOCAL_GID="${LOCAL_GID:-$(id -g)}"

echo
echo "Body multi-ECU topology"
echo "Terminal role : BCM ECU"
echo "Zone          : body_zone"
echo "CAN channel   : vcan_bcm"
echo "Service       : bcm"
echo

docker compose -f docker/docker-compose.ecus.yml \
    --profile deep-zonal \
    up --build bcm
