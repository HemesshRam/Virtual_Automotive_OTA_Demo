#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

transport="${1:-doip}"
zonal_mode="${2:-${OTA_USE_ZONAL_CONTROLLERS:-0}}"
scheduler_delay="${OTA_CAMPAIGN_PUBLISH_DELAY:-5}"
quiet="${OTA_DEMO_QUIET:-1}"
log_dir="${OTA_DEMO_LOG_DIR:-logs}"
https_enabled="${OTA_HTTPS_ENABLED:-1}"
https_enabled="${https_enabled,,}"

if [[ "${https_enabled}" == "1" || "${https_enabled}" == "true" || "${https_enabled}" == "yes" ]]; then
    export OTA_HTTPS_ENABLED=1
    export OTA_SERVER_URL="${OTA_SERVER_URL:-https://127.0.0.1:8080}"
    export OTA_PUBLIC_BASE_URL="${OTA_PUBLIC_BASE_URL:-https://127.0.0.1:8080}"
else
    export OTA_HTTPS_ENABLED=0
    export OTA_SERVER_URL="${OTA_SERVER_URL:-http://127.0.0.1:8080}"
    export OTA_PUBLIC_BASE_URL="${OTA_PUBLIC_BASE_URL:-http://127.0.0.1:8080}"
fi
export OTA_STATUS_URL="${OTA_STATUS_URL:-${OTA_SERVER_URL}/status}"
export OTA_DEMO_QUIET="${quiet}"

case "${transport,,}" in
    doip)
        transport_choice="2"
        transport_label="DoIP"
        ;;
    vcan)
        transport_choice="1"
        transport_label="VCAN"
        ;;
    *)
        echo "Usage: $0 [doip|vcan] [zonal|direct]" >&2
        exit 2
        ;;
esac

case "${zonal_mode,,}" in
    1|true|yes|zonal|zones)
        export OTA_USE_ZONAL_CONTROLLERS=1
        zonal_label="enabled"
        ;;
    deep|deep-zonal|zonal-deep|tcp)
        export OTA_USE_ZONAL_CONTROLLERS=1
        export OTA_ZONE_TRANSPORT=tcp
        zonal_label="enabled via TCP zone services"
        ;;
    0|false|no|direct|"")
        export OTA_USE_ZONAL_CONTROLLERS=0
        zonal_label="disabled"
        ;;
    *)
        echo "Usage: $0 [doip|vcan] [zonal|direct]" >&2
        exit 2
        ;;
esac

if [[ "${quiet,,}" == "1" || "${quiet,,}" == "true" || "${quiet,,}" == "yes" || "${quiet,,}" == "on" ]]; then
    mkdir -p "${log_dir}"
    scheduler_log="${log_dir}/campaign_scheduler.log"
    echo
    echo "============================================================"
    echo "AUTOMATED MQTT OTA DEMO"
    echo "============================================================"
    echo "Transport     : ${transport_label}"
    echo "Cloud link    : MQTT notify/status + ${OTA_SERVER_URL%%://*} campaign/artifact download"
    echo "Zonal routing : ${zonal_label}"
    echo "Quiet mode    : enabled"
    echo "Scheduler log : ${scheduler_log}"
    echo "============================================================"
    echo
    python -m ota_server.clear_mqtt_job_notification >/dev/null
else
    echo
    echo "============================================================"
    echo "AUTOMATED MQTT OTA DEMO"
    echo "============================================================"
    echo "Transport        : ${transport_label}"
    echo "Cloud link       : MQTT notify/status + ${OTA_SERVER_URL%%://*} campaign/artifact download"
    echo "Scheduler delay  : ${scheduler_delay}s"
    echo "Scheduler        : python -m ota_server.campaign_scheduler"
    echo "Zonal routing    : ${zonal_label}"
    if [[ "${transport_choice}" == "2" && "${OTA_USE_ZONAL_CONTROLLERS}" == "1" ]]; then
        echo "Gateway startup  : use 'bash scripts/start_demo.sh zonal|deep-zonal'"
        echo "                 : or terminal-pair scripts/run_gateway_zone_pair.sh plus ECU zone pairs"
    fi
    if [[ "${transport_choice}" == "1" && "${OTA_USE_ZONAL_CONTROLLERS}" == "1" ]]; then
        echo "Note             : VCAN mode talks to CAN zones directly; zonal gateway logs are visible only in DoIP mode."
    fi
    echo "============================================================"
    echo
    python -m ota_server.clear_mqtt_job_notification
fi

(
    sleep "${scheduler_delay}"
    if [[ "${quiet,,}" == "1" || "${quiet,,}" == "true" || "${quiet,,}" == "yes" || "${quiet,,}" == "on" ]]; then
        OTA_CAMPAIGN_PUBLISH_DELAY=0 python -u -m ota_server.campaign_scheduler >"${scheduler_log}" 2>&1
    else
        OTA_CAMPAIGN_PUBLISH_DELAY=0 python -u -m ota_server.campaign_scheduler 2>&1 \
            | sed -u 's/^/[SCHEDULER] /'
    fi
) &

scheduler_pid=$!

cleanup() {
    if kill -0 "${scheduler_pid}" >/dev/null 2>&1; then
        kill "${scheduler_pid}" >/dev/null 2>&1 || true
    fi
}
trap cleanup EXIT

if [[ "${transport_choice}" == "1" ]]; then
    export OTA_TRANSPORT=vcan
else
    export OTA_TRANSPORT=doip
fi
export OTA_CLOUD_CONTROL=mqtt

python -m tcu.main

wait "${scheduler_pid}" || true
