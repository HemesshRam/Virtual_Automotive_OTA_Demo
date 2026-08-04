#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
export OTA_ZONE_BODY_ZONE_HEALTH=OFFLINE
exec bash scripts/run_ecu_zone_pair.sh bcm
