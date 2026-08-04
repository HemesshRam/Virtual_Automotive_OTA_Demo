#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

mode="${1:-quick}"

print_header() {
    echo
    echo "============================================================"
    echo "$1"
    echo "============================================================"
}

check_cmd() {
    local label="$1"
    shift
    if "$@"; then
        echo "[OK] ${label}"
    else
        echo "[FAIL] ${label}"
        return 1
    fi
}

check_vcan() {
    ip link show vcan_gate >/dev/null 2>&1 &&
    ip link show vcan_bcm >/dev/null 2>&1 &&
    ip link show vcan_clus >/dev/null 2>&1
}

check_trust() {
    .venv/bin/python - <<'PY'
from tcu.trust.uptane_verifier import UptaneVerifier
UptaneVerifier("firmware/releases/2.0.0").verify()
PY
}

check_compose() {
    docker compose -f docker/docker-compose.ecus.yml config >/dev/null &&
    docker compose -f docker/docker-compose.yml config >/dev/null
}

check_campaign_json() {
    python3 - <<'PY'
import json
for path in [
    "campaigns/campaign_v1.json",
    "campaigns/campaign_v1.default.json",
    "campaigns/campaign_partial_skip_cluster.json",
    "campaigns/campaign_dependency_cluster_gateway.json",
    "campaigns/campaign_dependency_bcm_gateway_cluster.json",
]:
    with open(path, "r", encoding="utf-8") as fp:
        json.load(fp)
PY
}

check_unit_suite() {
    .venv/bin/python -m unittest \
        test_doip_discovery.py \
        test_doip_library_client_timeout.py \
        test_doip_server_strict_mode.py \
        test_doip_server_vehicle_ident.py \
        test_isotp_flow_control.py \
        test_flash_memory_emulator.py \
        test_flash_manager.py \
        test_realism_profile.py \
        test_uds_response_pending.py \
        test_uds_programmer_state.py \
        test_uptane_verifier.py \
        test_partial_campaign_behavior.py \
        test_post_install_validator.py \
        test_update_scheduler_status.py \
        test_dynamic_dependency_policy.py \
        test_topology_dependency_planner.py \
        test_vehicle_topology_validation.py \
        test_uds_response_filtering.py \
        test_zone_heartbeat_policy.py \
        test_runtime_control.py \
        test_zone_availability_guard.py \
        test_dynamic_update_planner.py \
        test_scenario_runner.py
}

show_demo_state() {
    bash scripts/verify_demo_state.sh
}

check_demo_consistency() {
    python3 scripts/validate_demo_consistency.py
}

check_realism_profile() {
    python3 scripts/validate_realism_profile.py
}

check_vehicle_topology() {
    python3 scripts/check_vehicle_topology.py &&
    OTA_VEHICLE_TOPOLOGY=vehicle/topology.body_multi_ecu.json \
        python3 scripts/check_vehicle_topology.py
}

check_terminal_pair_scripts() {
    bash -n scripts/run_ecu_zone_pair.sh &&
    bash -n scripts/run_gateway_zone_pair.sh &&
    bash -n scripts/run_gateway_zone_pair_offline.sh &&
    bash -n scripts/run_gateway_zone_pair_heartbeat_offline.sh &&
    bash -n scripts/run_bcm_zone_pair.sh &&
    bash -n scripts/run_bcm_zone_pair_offline.sh &&
    bash -n scripts/run_bcm_zone_pair_heartbeat_offline.sh &&
    bash -n scripts/run_cluster_zone_pair.sh &&
    bash -n scripts/run_cluster_zone_pair_offline.sh &&
    bash -n scripts/run_cluster_zone_pair_heartbeat_offline.sh &&
    bash -n scripts/run_body_multi_ecu_zone_stack.sh &&
    bash -n scripts/run_body_multi_gateway_pair.sh &&
    bash -n scripts/run_body_multi_body_zone.sh &&
    bash -n scripts/run_body_multi_bcm_ecu.sh &&
    bash -n scripts/run_body_multi_cluster_ecu.sh &&
    bash -n scripts/run_tcu_body_multi_ecu_zone_demo.sh &&
    bash -n scripts/check_body_multi_ecu_zone_health.sh &&
    bash -n scripts/select_campaign_scenario.sh &&
    bash -n scripts/run_dynamic_demo.sh &&
    test -x scripts/run_ecu_zone_pair.sh &&
    test -x scripts/run_gateway_zone_pair.sh &&
    test -x scripts/run_gateway_zone_pair_offline.sh &&
    test -x scripts/run_gateway_zone_pair_heartbeat_offline.sh &&
    test -x scripts/run_bcm_zone_pair.sh &&
    test -x scripts/run_bcm_zone_pair_offline.sh &&
    test -x scripts/run_bcm_zone_pair_heartbeat_offline.sh &&
    test -x scripts/run_cluster_zone_pair.sh &&
    test -x scripts/run_cluster_zone_pair_offline.sh &&
    test -x scripts/run_cluster_zone_pair_heartbeat_offline.sh &&
    test -x scripts/run_body_multi_ecu_zone_stack.sh &&
    test -x scripts/run_body_multi_gateway_pair.sh &&
    test -x scripts/run_body_multi_body_zone.sh &&
    test -x scripts/run_body_multi_bcm_ecu.sh &&
    test -x scripts/run_body_multi_cluster_ecu.sh &&
    test -x scripts/run_tcu_body_multi_ecu_zone_demo.sh &&
    test -x scripts/check_body_multi_ecu_zone_health.sh &&
    test -x scripts/select_campaign_scenario.sh &&
    test -x scripts/run_dynamic_demo.sh
}

print_header "FEATURE CHECK (${mode})"

check_cmd "Campaign JSON files parse" check_campaign_json
check_cmd "Vehicle topology JSON loads" check_vehicle_topology
check_cmd "Terminal-pair runner scripts validate" check_terminal_pair_scripts
check_cmd "Uptane-style trust chain verifies" check_trust
check_cmd "Docker compose files validate" check_compose

if [[ "${mode}" == "quick" ]]; then
    if ! check_cmd "VCAN zonal interfaces exist" check_vcan; then
        echo "[ACTION] Run: sudo ./scripts/setup_vcan_zones.sh"
        echo "[INFO] This is a host network preflight issue, not a code failure."
    fi
    exit 0
fi

if [[ "${mode}" == "full" ]]; then
    check_cmd "VCAN zonal interfaces exist" check_vcan
    check_cmd "Production-style simulation profile validates" check_realism_profile
    check_cmd "Core feature/unit test suite passes" check_unit_suite
    check_cmd "ECU demo state is internally consistent" check_demo_consistency || true
    print_header "CURRENT ECU SLOT/VERSION/FLASH STATE"
    show_demo_state
    exit 0
fi

echo "Unknown mode: ${mode}" >&2
echo "Usage: bash scripts/check_features.sh [quick|full]" >&2
exit 1
