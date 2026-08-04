#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

export OTA_ECU_GATEWAY_HEARTBEAT_ENABLED=0
export OTA_ZONE_GATEWAY_ZONE_HEALTH=AUTO
export OTA_ZONE_HEARTBEAT_MONITOR_ENABLED=1
export OTA_ZONE_HEARTBEAT_TIMEOUT_SECONDS="${OTA_ZONE_HEARTBEAT_TIMEOUT_SECONDS:-3.0}"

echo "[DEMO] Gateway ECU application starts, but heartbeat is disabled"
echo "[DEMO] gateway_zone should mark Gateway ECU unavailable after heartbeat timeout"

exec bash scripts/run_ecu_zone_pair.sh gateway
