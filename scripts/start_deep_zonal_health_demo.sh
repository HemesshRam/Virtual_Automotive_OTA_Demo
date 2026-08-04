#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

export OTA_ZONE_CLUSTER_ZONE_HEALTH=OFFLINE

echo "[DEMO] Starting deep-zonal health demo"
echo "[DEMO] cluster_zone is OFFLINE; Cluster ECU should be unreachable"

exec bash scripts/start_demo.sh deep-zonal
