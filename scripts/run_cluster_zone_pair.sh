#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
exec bash scripts/run_ecu_zone_pair.sh cluster
