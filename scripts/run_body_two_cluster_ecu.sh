#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
exec bash scripts/run_body_multi_cluster_ecu.sh
