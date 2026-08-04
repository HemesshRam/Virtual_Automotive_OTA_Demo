#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

export OTA_ECU_CLUSTER_HEARTBEAT_ENABLED=0
export OTA_ZONE_CLUSTER_ZONE_HEALTH=AUTO
export OTA_ZONE_HEARTBEAT_MONITOR_ENABLED=1
export OTA_ZONE_HEARTBEAT_TIMEOUT_SECONDS="${OTA_ZONE_HEARTBEAT_TIMEOUT_SECONDS:-3.0}"

echo "[DEMO] Cluster ECU application starts, but heartbeat is disabled"
echo "[DEMO] cluster_zone should mark Cluster ECU unavailable after heartbeat timeout"

exec bash scripts/run_ecu_zone_pair.sh cluster
