#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

cp campaigns/campaign_v1.json campaigns/campaign_v1.json.bak 2>/dev/null || true
cp campaigns/campaign_partial_skip_cluster.json campaigns/campaign_v1.json
python3 scripts/refresh_active_scenario.py \
  --base-campaign campaigns/campaign_partial_skip_cluster.json \
  --dependency-mode partial_skip_cluster \
  --offline-ecus "Cluster ECU" \
  --source direct_campaign_helper >/dev/null
echo "Partial rollout demo campaign activated"
echo "Cluster ECU is optional and intentionally incompatible (minimum_bootloader=9.9.0)"
echo "Canonical active scenario refreshed"
