#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

topology_choice="${1:-}"
dependency_choice="${2:-}"
offline_choice="${3:-}"
ecu_state_choice="${4:-}"
transport="${5:-${OTA_TRANSPORT:-doip}}"
mode="${6:-run}"
quiet="${OTA_DEMO_QUIET:-1}"
scheduler_delay="${OTA_CAMPAIGN_PUBLISH_DELAY:-5}"
log_dir="${OTA_DEMO_LOG_DIR:-logs}"

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

3. Mid-size vehicle example
   gateway_zone -> Gateway ECU + TCU Proxy ECU
   body_zone    -> BCM ECU + Door FL ECU
   cockpit_zone -> Cluster ECU + Infotainment ECU + HVAC ECU
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
STEP 4: SELECT TRANSPORT MEDIUM
============================================================
1. DoIP
   TCU -> DoIP gateway -> zone controllers -> ECU

2. VCAN
   TCU -> CAN FD / ISO-TP path -> ECU
============================================================
Deep-zonal routing is the default mode.
Cloud control remains HTTPS artifacts + MQTT notify.
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

resolve_topology_mode() {
    case "$1" in
        1|default) echo "default" ;;
        2|body-two|body_two|body_two_ecus) echo "body_two_ecus" ;;
        3|midsize|mid-size|midsize_demo) echo "midsize_demo" ;;
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

print_stack_hint() {
    local topology_mode="$1"
    local transport="$2"
    local ecu_state_preset="$3"

    echo "Stack startup for this selection:"
    if [[ "${topology_mode}" == "body_two_ecus" ]]; then
        echo "  Terminal 1: bash scripts/run_body_multi_gateway_pair.sh"
        echo "  Terminal 2: bash scripts/run_body_multi_body_zone.sh"
        echo "  Terminal 3: bash scripts/run_body_multi_bcm_ecu.sh"
        echo "  Terminal 4: bash scripts/run_body_multi_cluster_ecu.sh"
        echo "  Terminal 5: bash scripts/run_ota_server_https.sh"
    elif [[ "${topology_mode}" == "midsize_demo" ]]; then
        echo "  Architecture only: use vehicle/topology.midsize_demo.json for customer walkthroughs"
        echo "  Runtime note    : this example is not fully runnable because extra ECUs are not yet implemented"
        echo "  Validate it     : python3 scripts/show_vehicle_example.py vehicle/topology.midsize_demo.json"
    else
        echo "  Terminal 1: bash scripts/run_gateway_zone_pair.sh"
        echo "  Terminal 2: bash scripts/run_bcm_zone_pair.sh"
        echo "  Terminal 3: bash scripts/run_cluster_zone_pair.sh"
        echo "  Terminal 4: bash scripts/run_ota_server_https.sh"
    fi
    echo "  MQTT      : broker must already be listening on 127.0.0.1:1883"
    echo "  Scheduler : backend MQTT publish is auto-started by this launcher in run mode"
    echo "  ECU state : ${ecu_state_preset}"
    if [[ "${transport}" == "vcan" ]]; then
        echo "  Note      : VCAN still uses the selected zonal topology; ECU CAN channels must match it."
    else
        echo "  Note      : DoIP uses the selected zonal topology; zone routing must match it."
    fi
}

if [[ -z "${topology_choice}" ]]; then
    print_topology_menu
    read -r -p "Enter topology choice [1-3]: " topology_choice
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

if [[ -z "${5:-}" && -z "${OTA_TRANSPORT:-}" ]]; then
    print_transport_menu
    read -r -p "Enter transport choice [1-2]: " transport
fi

if ! topology_mode="$(resolve_topology_mode "${topology_choice}")"; then
    echo "Invalid topology choice: ${topology_choice}" >&2
    print_topology_menu >&2
    exit 2
fi

if ! dependency_mode="$(resolve_dependency_mode "${dependency_choice}")"; then
    echo "Invalid dependency choice: ${dependency_choice}" >&2
    print_dependency_menu >&2
    exit 2
fi

if ! offline_ecus="$(resolve_offline_ecus "${offline_choice}")"; then
    echo "Invalid offline choice: ${offline_choice}" >&2
    print_offline_menu >&2
    exit 2
fi

if ! ecu_state_preset="$(resolve_ecu_state_preset "${ecu_state_choice}")"; then
    echo "Invalid ECU state choice: ${ecu_state_choice}" >&2
    print_ecu_state_menu >&2
    exit 2
fi

if ! transport="$(resolve_transport "${transport}")"; then
    echo "Invalid transport choice: ${transport}" >&2
    print_transport_menu >&2
    exit 2
fi

case "${mode,,}" in
    run|prepare|prepare-only) ;;
    *)
        echo "Mode must be one of: run, prepare, prepare-only" >&2
        exit 2
        ;;
esac

preflight_failed=0
if [[ "${mode,,}" == "run" ]]; then
    if ! ss -ltn | grep -q ':1883 '; then
        echo "[PRECHECK] MQTT broker not listening on 127.0.0.1:1883" >&2
        echo "[ACTION] Start mosquitto or your MQTT service first." >&2
        preflight_failed=1
    fi
    if ! ss -ltn | grep -q ':8080 '; then
        echo "[PRECHECK] OTA HTTPS server not listening on 127.0.0.1:8080" >&2
        echo "[ACTION] Run: bash scripts/run_ota_server_https.sh" >&2
        preflight_failed=1
    fi
fi

if [[ "${preflight_failed}" == "1" ]]; then
    echo
    print_stack_hint "${topology_mode}" "${transport}" "${ecu_state_preset}"
    echo "[TIP] Use 'prepare-only' if you only want to generate the runtime scenario." >&2
    exit 1
fi

if [[ "${topology_mode}" == "midsize_demo" ]]; then
    echo
    echo "============================================================"
    echo "ARCHITECTURE WALKTHROUGH MODE"
    echo "============================================================"
    echo "This example is intended for customer-facing architecture discussion."
    echo "It is not bound to the current 3-ECU runnable demo stack."
    echo
    exec python3 scripts/show_vehicle_example.py vehicle/topology.midsize_demo.json
fi

scenario_name="dynamic_$(date +%Y%m%d_%H%M%S)"

echo
echo "============================================================"
echo "DYNAMIC OTA DEMO"
echo "============================================================"
echo "Scenario name : ${scenario_name}"
echo "Topology mode : ${topology_mode}"
echo "Dependency    : ${dependency_mode}"
echo "Offline ECUs  : ${offline_ecus:-None}"
echo "ECU state     : ${ecu_state_preset}"
echo "Transport     : ${transport^^}"
echo "Zonal mode    : deep-zonal (default)"
echo "Cloud         : HTTPS artifacts + MQTT notify"
echo "Scheduler     : automatic backend publish (${scheduler_delay}s delay)"
echo "Quiet         : ${quiet}"
echo "Mode          : ${mode}"
echo "============================================================"
echo

print_stack_hint "${topology_mode}" "${transport}" "${ecu_state_preset}"
echo

args=(
    .venv/bin/python -m tcu.scenario_runner scenarios/dynamic_demo_template.json
    --transport "${transport,,}"
    --quiet "${quiet}"
    --topology-mode "${topology_mode}"
    --dependency-mode "${dependency_mode}"
    --ecu-state-preset "${ecu_state_preset}"
)

if [[ -n "${offline_ecus}" ]]; then
    args+=(--offline-ecus "${offline_ecus}")
fi

if [[ "${mode,,}" == "prepare" || "${mode,,}" == "prepare-only" ]]; then
    args+=(--prepare-only)
fi

export OTA_SCENARIO_NAME_OVERRIDE="${scenario_name}"

if [[ "${mode,,}" == "run" ]]; then
    mkdir -p "${log_dir}"
    scheduler_log="${log_dir}/dynamic_demo_scheduler_${scenario_name}.log"
    export OTA_HTTPS_ENABLED=1
    export OTA_PUBLIC_BASE_URL="${OTA_PUBLIC_BASE_URL:-https://127.0.0.1:8080}"
    export OTA_SERVER_URL="${OTA_SERVER_URL:-https://127.0.0.1:8080}"
    export OTA_STATUS_URL="${OTA_STATUS_URL:-https://127.0.0.1:8080/status}"

    if [[ "${quiet,,}" == "1" || "${quiet,,}" == "true" || "${quiet,,}" == "yes" || "${quiet,,}" == "on" ]]; then
        echo "Scheduler log: ${scheduler_log}"
    fi

    python -m ota_server.clear_mqtt_job_notification >/dev/null 2>&1 || true

    (
        sleep "${scheduler_delay}"
        if [[ "${quiet,,}" == "1" || "${quiet,,}" == "true" || "${quiet,,}" == "yes" || "${quiet,,}" == "on" ]]; then
            OTA_CAMPAIGN_PUBLISH_DELAY=0 python -u -m ota_server.campaign_scheduler >"${scheduler_log}" 2>&1
        else
            OTA_CAMPAIGN_PUBLISH_DELAY=0 python -u -m ota_server.campaign_scheduler 2>&1 \
                | sed -u 's/^/[SCHEDULER] /'
        fi
    ) &
fi

exec "${args[@]}"
