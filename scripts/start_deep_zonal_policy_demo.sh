#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

export OTA_ZONE_BODY_ZONE_PROGRAMMING_ALLOWED=0

echo "[DEMO] Starting deep-zonal policy demo"
echo "[DEMO] body_zone programming is blocked; BCM update should fail/skip dependents"

exec bash scripts/start_demo.sh deep-zonal
