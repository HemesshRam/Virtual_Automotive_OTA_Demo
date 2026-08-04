#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
exec bash scripts/check_body_multi_ecu_zone_health.sh
