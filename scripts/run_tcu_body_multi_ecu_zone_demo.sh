#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

export OTA_VEHICLE_TOPOLOGY=vehicle/topology.body_multi_ecu.json
export OTA_USE_ZONAL_CONTROLLERS=1
export OTA_ZONE_TRANSPORT=tcp
export OTA_ECU_CLUSTER_CAN_CHANNEL=vcan_bcm

exec bash scripts/run_tcu_mqtt_job_demo.sh "${1:-doip}" deep-zonal
