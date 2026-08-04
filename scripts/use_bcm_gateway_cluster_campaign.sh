#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

cp campaigns/campaign_v1.json campaigns/campaign_v1.json.bak 2>/dev/null || true
cp campaigns/campaign_dependency_bcm_gateway_cluster.json campaigns/campaign_v1.json
python3 scripts/refresh_active_scenario.py \
  --base-campaign campaigns/campaign_dependency_bcm_gateway_cluster.json \
  --dependency-mode bcm_before_gateway \
  --source direct_campaign_helper >/dev/null
echo "Campaign dependency override activated"
echo "Dependency chain is now BCM ECU -> Gateway ECU -> Cluster ECU"
echo "Canonical active scenario refreshed"
