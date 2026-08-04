#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

cp campaigns/campaign_v1.json campaigns/campaign_v1.json.bak 2>/dev/null || true
cp campaigns/campaign_v1.default.json campaigns/campaign_v1.json
python3 scripts/refresh_active_scenario.py \
  --base-campaign campaigns/campaign_v1.default.json \
  --dependency-mode topology_default \
  --source direct_campaign_helper >/dev/null
echo "Default full campaign activated"
echo "Canonical active scenario refreshed"
