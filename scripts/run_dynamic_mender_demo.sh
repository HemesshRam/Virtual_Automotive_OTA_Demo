#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

topology_choice="${1:-}"
dependency_choice="${2:-}"
offline_choice="${3:-}"
ecu_state_choice="${4:-}"
transport_choice="${5:-}"
runtime_mode="${6:-docker}"
mode="${7:-deploy-help}"
artifact_family="${OTA_MENDER_ARTIFACT_NAME:-virtual-ota-dynamic}"
scenario_name="mender_dynamic_demo"

print_topology_menu() {
    cat <<'MENU'

============================================================
STEP 1: SELECT TOPOLOGY
============================================================
1. Default topology
   gateway_zone -> Gateway ECU
   body_zone    -> BCM ECU
   cluster_zone -> Cluster ECU

2. One zone with 2 ECUs
   gateway_zone -> Gateway ECU
   body_zone    -> BCM ECU + Cluster ECU
============================================================
MENU
}

print_dependency_menu() {
    cat <<'MENU'

============================================================
STEP 2: SELECT DEPENDENCY POLICY
============================================================
1. Topology default
   Gateway ECU -> BCM ECU -> Cluster ECU

2. Cluster depends on Gateway
   Gateway ECU -> BCM ECU
   Gateway ECU -> Cluster ECU

3. BCM before Gateway before Cluster
   BCM ECU -> Gateway ECU -> Cluster ECU

4. Partial rollout / Cluster optional skip
   Gateway ECU -> BCM ECU
   Cluster ECU optional and intentionally incompatible
============================================================
MENU
}

print_offline_menu() {
    cat <<'MENU'

============================================================
STEP 3: SELECT OFFLINE ECU CASE
============================================================
1. All ECUs online
2. Gateway ECU offline
3. BCM ECU offline
4. Cluster ECU offline
5. Gateway ECU + BCM ECU offline
6. Gateway ECU + Cluster ECU offline
7. BCM ECU + Cluster ECU offline
============================================================
MENU
}

print_transport_menu() {
    cat <<'MENU'

============================================================
STEP 4: SELECT TRANSPORT
============================================================
1. DoIP
2. VCAN
============================================================
MENU
}

print_ecu_state_menu() {
    cat <<'MENU'

============================================================
STEP 4: SELECT ECU VERSION STATE
============================================================
1. Keep current ECU state
2. Fresh baseline
   Gateway ECU = 1.0.0
   BCM ECU     = 1.0.0
   Cluster ECU = 1.0.0

3. Gateway + BCM already updated
   Gateway ECU = 2.0.0
   BCM ECU     = 2.0.0
   Cluster ECU = 1.0.0

4. Gateway + Cluster already updated
   Gateway ECU = 2.0.0
   BCM ECU     = 1.0.0
   Cluster ECU = 2.0.0

5. BCM + Cluster already updated
   Gateway ECU = 1.0.0
   BCM ECU     = 2.0.0
   Cluster ECU = 2.0.0
============================================================
MENU
}

print_runtime_menu() {
    cat <<'MENU'

============================================================
STEP 5: SELECT VEHICLE RUNTIME
============================================================
1. Docker ECU + zone stack
2. Python ECU + zone processes
============================================================
MENU
}

resolve_topology_mode() {
    case "$1" in
        1|default) echo "default" ;;
        2|body-two|body_two|body_two_ecus) echo "body_two_ecus" ;;
        *) return 1 ;;
    esac
}

resolve_dependency_mode() {
    case "$1" in
        1|default|topology) echo "topology_default" ;;
        2|cluster-gateway|cluster_gateway) echo "cluster_depends_gateway" ;;
        3|bcm-gateway-cluster|bcm_gateway_cluster) echo "bcm_before_gateway" ;;
        4|partial|partial-skip|partial_skip) echo "partial_skip_cluster" ;;
        *) return 1 ;;
    esac
}

resolve_offline_ecus() {
    case "$1" in
        1|none|online) echo "" ;;
        2|gateway) echo "Gateway ECU" ;;
        3|bcm) echo "BCM ECU" ;;
        4|cluster) echo "Cluster ECU" ;;
        5|gateway-bcm|gateway_bcm) echo "Gateway ECU,BCM ECU" ;;
        6|gateway-cluster|gateway_cluster) echo "Gateway ECU,Cluster ECU" ;;
        7|bcm-cluster|bcm_cluster) echo "BCM ECU,Cluster ECU" ;;
        *) return 1 ;;
    esac
}

resolve_transport() {
    case "$1" in
        1|doip|DOIP) echo "doip" ;;
        2|vcan|VCAN) echo "vcan" ;;
        *) return 1 ;;
    esac
}

resolve_ecu_state_preset() {
    case "$1" in
        1|keep|keep_current|current) echo "keep_current" ;;
        2|fresh|fresh_baseline|baseline) echo "fresh_baseline" ;;
        3|gateway-bcm|gateway_bcm|gateway_bcm_updated_cluster_pending) echo "gateway_bcm_updated_cluster_pending" ;;
        4|gateway-cluster|gateway_cluster|gateway_cluster_updated_bcm_pending) echo "gateway_cluster_updated_bcm_pending" ;;
        5|bcm-cluster|bcm_cluster|bcm_cluster_updated_gateway_pending) echo "bcm_cluster_updated_gateway_pending" ;;
        *) return 1 ;;
    esac
}

resolve_runtime() {
    case "$1" in
        1|docker|containers) echo "docker" ;;
        2|python|process|processes) echo "python" ;;
        *) return 1 ;;
    esac
}

print_runtime_stack() {
    local topology_mode="$1"
    local runtime_mode="$2"
    local transport="$3"
    local ecu_state_preset="$4"

    echo
    echo "============================================================"
    echo "START THE VEHICLE RUNTIME FIRST"
    echo "============================================================"
    echo "Reset:"
    echo "  bash scripts/stop_demo.sh || true"
    echo "  bash scripts/reset_demo_state.sh"
    echo "  sudo ./scripts/setup_vcan_zones.sh"
    echo
    echo "OTA server:"
    echo "  bash scripts/run_ota_server_https.sh"
    echo

    if [[ "${runtime_mode}" == "docker" ]]; then
        if [[ "${topology_mode}" == "body_two_ecus" ]]; then
            echo "Docker stack:"
            echo "  Terminal 1: bash scripts/run_body_multi_gateway_pair.sh"
            echo "  Terminal 2: bash scripts/run_body_multi_body_zone.sh"
            echo "  Terminal 3: bash scripts/run_body_multi_bcm_ecu.sh"
            echo "  Terminal 4: bash scripts/run_body_multi_cluster_ecu.sh"
        else
            echo "Docker stack:"
            echo "  Terminal 1: bash scripts/run_gateway_zone_pair.sh"
            echo "  Terminal 2: bash scripts/run_bcm_zone_pair.sh"
            echo "  Terminal 3: bash scripts/run_cluster_zone_pair.sh"
        fi
    else
        if [[ "${topology_mode}" == "body_two_ecus" ]]; then
            echo "Python stack:"
            echo "  Terminal 1: OTA_VEHICLE_TOPOLOGY=vehicle/topology.body_multi_ecu.json python run_gateway.py"
            echo "  Terminal 2: OTA_VEHICLE_TOPOLOGY=vehicle/topology.body_multi_ecu.json python zones/run_zone_service.py gateway_zone"
            echo "  Terminal 3: OTA_VEHICLE_TOPOLOGY=vehicle/topology.body_multi_ecu.json python zones/run_zone_service.py body_zone"
            echo "  Terminal 4: OTA_VEHICLE_TOPOLOGY=vehicle/topology.body_multi_ecu.json OTA_ECU_BCM_CAN_CHANNEL=vcan_bcm python run_bcm.py"
            echo "  Terminal 5: OTA_VEHICLE_TOPOLOGY=vehicle/topology.body_multi_ecu.json OTA_ECU_CLUSTER_CAN_CHANNEL=vcan_bcm python run_cluster.py"
        else
            echo "Python stack:"
            echo "  Terminal 1: python run_gateway.py"
            echo "  Terminal 2: python run_bcm.py"
            echo "  Terminal 3: python run_cluster.py"
            echo "  Terminal 4: python zones/run_zone_service.py gateway_zone"
            echo "  Terminal 5: python zones/run_zone_service.py body_zone"
            echo "  Terminal 6: python zones/run_zone_service.py cluster_zone"
        fi
    fi
    echo
    echo "Mender-triggered OTA path:"
    echo "  Mender client on host starts the TCU automatically."
    echo "  Do not run 'python -m tcu.main' manually for this flow."
    echo
    echo "Transport selected : ${transport^^}"
    echo "Cloud control      : Mender trigger + HTTPS local payload/artifact download"
    echo "ECU state preset   : ${ecu_state_preset}"
}

if [[ -z "${topology_choice}" ]]; then
    print_topology_menu
    read -r -p "Enter topology choice [1-2]: " topology_choice
fi

if [[ -z "${dependency_choice}" ]]; then
    print_dependency_menu
    read -r -p "Enter dependency choice [1-4]: " dependency_choice
fi

if [[ -z "${offline_choice}" ]]; then
    print_offline_menu
    read -r -p "Enter offline choice [1-7]: " offline_choice
fi

if [[ -z "${ecu_state_choice}" ]]; then
    print_ecu_state_menu
    read -r -p "Enter ECU state choice [1-5]: " ecu_state_choice
fi

if [[ -z "${transport_choice}" ]]; then
    print_transport_menu
    read -r -p "Enter transport choice [1-2]: " transport_choice
fi

if [[ -z "${6:-}" ]]; then
    print_runtime_menu
    read -r -p "Enter runtime choice [1-2]: " runtime_mode
fi

if ! topology_mode="$(resolve_topology_mode "${topology_choice}")"; then
    echo "Invalid topology choice: ${topology_choice}" >&2
    exit 2
fi

if ! dependency_mode="$(resolve_dependency_mode "${dependency_choice}")"; then
    echo "Invalid dependency choice: ${dependency_choice}" >&2
    exit 2
fi

if ! offline_ecus="$(resolve_offline_ecus "${offline_choice}")"; then
    echo "Invalid offline choice: ${offline_choice}" >&2
    exit 2
fi

if ! ecu_state_preset="$(resolve_ecu_state_preset "${ecu_state_choice}")"; then
    echo "Invalid ECU state choice: ${ecu_state_choice}" >&2
    exit 2
fi

if ! transport="$(resolve_transport "${transport_choice}")"; then
    echo "Invalid transport choice: ${transport_choice}" >&2
    exit 2
fi

if ! runtime_mode="$(resolve_runtime "${runtime_mode}")"; then
    echo "Invalid runtime mode: ${runtime_mode}" >&2
    exit 2
fi

case "${mode,,}" in
    deploy-help|prepare-only|api) ;;
    *)
        echo "Mode must be one of: deploy-help, prepare-only, api" >&2
        exit 2
        ;;
esac

scenario_args=(
    .venv/bin/python integrations/mender/set_dynamic_scenario.py
    --scenario-name "${scenario_name}"
    --transport "${transport}"
    --topology-mode "${topology_mode}"
    --dependency-mode "${dependency_mode}"
    --ecu-state-preset "${ecu_state_preset}"
)

if [[ -n "${offline_ecus}" ]]; then
    scenario_args+=(--offline-ecus "${offline_ecus}")
fi

"${scenario_args[@]}"

timestamp="$(date +%Y%m%d-%H%M%S)"
artifact_name="${artifact_family}-${transport}-${timestamp}"
artifact_file="/tmp/${artifact_name}.mender"
deployment_name="${artifact_name}"

echo
echo "============================================================"
echo "DYNAMIC MENDER DEMO PREPARED"
echo "============================================================"
echo "Scenario name   : ${scenario_name}"
echo "Topology mode   : ${topology_mode}"
echo "Dependency mode : ${dependency_mode}"
echo "Offline ECUs    : ${offline_ecus:-None}"
echo "ECU state       : ${ecu_state_preset}"
echo "Transport       : ${transport^^}"
echo "Runtime         : ${runtime_mode}"
echo "Artifact        : ${artifact_name}"
echo "Artifact file   : ${artifact_file}"
echo "============================================================"

print_runtime_stack "${topology_mode}" "${runtime_mode}" "${transport}" "${ecu_state_preset}"

echo
echo "Packaging a fresh Mender artifact for this run..."
.venv/bin/python integrations/mender/package_artifact.py \
    "${artifact_file}" \
    --device-type "${MENDER_DEVICE_TYPE:-virtual-ota-tcu}" \
    --profile dynamic_generic \
    --artifact-name "${artifact_name}"

echo
echo "============================================================"
echo "MENDER DEPLOYMENT NEXT STEPS"
echo "============================================================"
echo "1. Open Hosted Mender UI."
echo "2. Upload/select the freshly built artifact:"
echo "   ${artifact_name}"
echo "3. Create a fresh deployment for your registered TCU device/group."
echo "4. Watch the host-side Mender client:"
echo "   journalctl -u mender-updated -f"
echo "5. Optional: verify the selected dynamic scenario:"
echo "   .venv/bin/python integrations/mender/set_dynamic_scenario.py --show"
echo
echo "This launcher updates the dynamic scenario file."
echo "The same generic Mender artifact is reused."

if [[ "${mode,,}" == "prepare-only" ]]; then
    exit 0
fi

if [[ "${mode,,}" == "api" ]]; then
    if [[ -z "${MENDER_API_TOKEN:-}" ]]; then
        echo
        echo "MENDER_API_TOKEN is not set. Cannot call the Mender Management API." >&2
        echo "Artifact is already packaged. You can upload/deploy it manually from Hosted Mender UI." >&2
        exit 1
    fi
    if [[ -z "${MENDER_DEVICE_GROUP:-}" ]]; then
        echo
        echo "MENDER_DEVICE_GROUP is not set. Cannot create a group deployment via API." >&2
        echo "Artifact is already packaged. You can upload/deploy it manually from Hosted Mender UI." >&2
        exit 1
    fi

    echo
    echo "============================================================"
    echo "CALLING MENDER MANAGEMENT API"
    echo "============================================================"
    .venv/bin/python integrations/mender/deploy_via_api.py \
        --artifact-file "${artifact_file}" \
        --artifact-name "${artifact_name}" \
        --deployment-name "${deployment_name}" \
        --group-name "${MENDER_DEVICE_GROUP}" \
        --base-url "${MENDER_BASE_URL:-https://hosted.mender.io}" \
        --retries "${MENDER_DEPLOYMENT_RETRIES:-1}"
    echo
    echo "Deployment created via API. Watch progress with:"
    echo "  journalctl -u mender-updated -f"
else
    echo
    echo "Manual deployment trigger selected."
    echo "Use Hosted Mender UI for upload/deployment, or rerun with mode 'api'."
fi
