#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

choice="${1:-}"

print_menu() {
    cat <<'MENU'

============================================================
SELECT OTA CAMPAIGN / DEPENDENCY SCENARIO
============================================================
1. Default topology
   Gateway ECU -> BCM ECU -> Cluster ECU

2. Cluster depends directly on Gateway
   Gateway ECU -> BCM ECU
   Gateway ECU -> Cluster ECU

3. BCM must update before Gateway
   BCM ECU -> Gateway ECU -> Cluster ECU

4. Partial rollout / Cluster optional skip
   Gateway ECU -> BCM ECU
   Cluster ECU optional and intentionally incompatible
============================================================
MENU
}

activate_campaign() {
    local source_file="$1"
    local label="$2"
    local dependency_mode="$3"
    local offline_ecus="${4:-}"

    cp campaigns/campaign_v1.json campaigns/campaign_v1.json.bak 2>/dev/null || true
    cp "${source_file}" campaigns/campaign_v1.json
    python3 scripts/refresh_active_scenario.py \
        --base-campaign "${source_file}" \
        --dependency-mode "${dependency_mode}" \
        --offline-ecus "${offline_ecus}" \
        --source direct_campaign_helper >/dev/null

    echo
    echo "Campaign scenario activated: ${label}"
    echo "Source campaign: ${source_file}"
    echo "Runtime campaign: campaigns/campaign_v1.json"
    echo "Canonical active scenario refreshed"
    python3 scripts/show_dependency_plan.py campaigns/campaign_v1.json
}

if [[ -z "${choice}" ]]; then
    print_menu
    read -r -p "Enter choice [1-4]: " choice
fi

case "${choice}" in
    1|default)
        activate_campaign \
            "campaigns/campaign_v1.default.json" \
            "Default topology" \
            "topology_default"
        ;;
    2|cluster-gateway|cluster_gateway)
        activate_campaign \
            "campaigns/campaign_dependency_cluster_gateway.json" \
            "Cluster depends directly on Gateway" \
            "cluster_depends_gateway"
        ;;
    3|bcm-gateway-cluster|bcm_gateway_cluster)
        activate_campaign \
            "campaigns/campaign_dependency_bcm_gateway_cluster.json" \
            "BCM -> Gateway -> Cluster" \
            "bcm_before_gateway"
        ;;
    4|partial|partial-skip|partial_skip)
        activate_campaign \
            "campaigns/campaign_partial_skip_cluster.json" \
            "Partial rollout / Cluster optional skip" \
            "partial_skip_cluster" \
            "Cluster ECU"
        ;;
    *)
        echo "Invalid scenario: ${choice}" >&2
        print_menu >&2
        exit 2
        ;;
esac
