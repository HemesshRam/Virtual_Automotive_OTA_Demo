#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

cp campaigns/campaign_v1.json campaigns/campaign_v1.json.bak 2>/dev/null || true
cp campaigns/campaign_dependency_cluster_gateway.json campaigns/campaign_v1.json
python3 scripts/refresh_active_scenario.py \
  --base-campaign campaigns/campaign_dependency_cluster_gateway.json \
  --dependency-mode cluster_depends_gateway \
  --source direct_campaign_helper >/dev/null
echo "Campaign dependency override activated"
echo "Cluster ECU now depends on Gateway ECU instead of BCM ECU for this campaign"
echo "Canonical active scenario refreshed"
