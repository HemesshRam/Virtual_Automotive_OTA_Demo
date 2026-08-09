#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

pair="${1:-}"

usage() {
    echo "Usage: $0 [gateway|bcm|cluster]" >&2
}

require_vcan() {
    local interfaces=(vcan_gate vcan_bcm vcan_clus)
    local missing=()

    for iface in "${interfaces[@]}"; do
        if [[ ! -e "/sys/class/net/$iface" ]]; then
            missing+=("$iface")
        fi
    done

    if ((${#missing[@]} > 0)); then
        echo "[VCAN PREFLIGHT] Missing interfaces: ${missing[*]}" >&2
        echo "[VCAN PREFLIGHT] Run: sudo ./scripts/setup_vcan_zones.sh" >&2
        exit 1
    fi

    echo "[VCAN PREFLIGHT] Interfaces ready: ${interfaces[*]}"
}

case "${pair,,}" in
    gateway|gate)
        ecu_label="Gateway ECU"
        zone_label="gateway_zone"
        health_var="OTA_ZONE_GATEWAY_ZONE_HEALTH"
        services=(zone-gateway gateway)
        export OTA_USE_ZONAL_CONTROLLERS=1
        export OTA_ZONE_TRANSPORT=tcp
        ;;
    bcm|body)
        ecu_label="BCM ECU"
        zone_label="body_zone"
        health_var="OTA_ZONE_BODY_ZONE_HEALTH"
        services=(zone-body bcm)
        ;;
    cluster|clus|cockpit)
        ecu_label="Cluster ECU"
        zone_label="cluster_zone"
        health_var="OTA_ZONE_CLUSTER_ZONE_HEALTH"
        services=(zone-cluster cluster)
        ;;
    *)
        usage
        exit 2
        ;;
esac

require_vcan
export LOCAL_UID="${LOCAL_UID:-$(id -u)}"
export LOCAL_GID="${LOCAL_GID:-$(id -g)}"

echo
echo "ECU              : ${ecu_label}"
echo "Zone Controller  : ${zone_label}"
echo "Docker Services  : ${services[*]}"
echo "Zone Health      : ${!health_var:-AUTO}"
echo "Heartbeat Check  : ${OTA_ZONE_HEARTBEAT_MONITOR_ENABLED:-1}"
if [[ "${pair,,}" == "gateway" || "${pair,,}" == "gate" ]]; then
    echo "Gateway Routing  : DoIP -> TCP zone services"
fi
echo

docker compose -f docker/docker-compose.ecus.yml \
    --profile deep-zonal \
    up --build "${services[@]}"
