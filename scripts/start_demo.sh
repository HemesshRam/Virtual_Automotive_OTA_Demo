#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

zonal_mode="${1:-${OTA_USE_ZONAL_CONTROLLERS:-0}}"
compose_profiles=()

case "${zonal_mode,,}" in
    default|stack|demo)
        export OTA_USE_ZONAL_CONTROLLERS=1
        export OTA_ZONE_TRANSPORT=tcp
        compose_profiles+=(--profile deep-zonal)
        zonal_label="enabled via default zonal stack"
        ;;
    1|true|yes|zonal|zones)
        export OTA_USE_ZONAL_CONTROLLERS=1
        export OTA_ZONE_TRANSPORT="${OTA_ZONE_TRANSPORT:-in_process}"
        zonal_label="enabled"
        ;;
    deep|deep-zonal|zonal-deep|tcp)
        export OTA_USE_ZONAL_CONTROLLERS=1
        export OTA_ZONE_TRANSPORT=tcp
        compose_profiles+=(--profile deep-zonal)
        zonal_label="enabled via TCP zone services"
        ;;
    0|false|no|direct|"")
        export OTA_USE_ZONAL_CONTROLLERS=0
        export OTA_ZONE_TRANSPORT="${OTA_ZONE_TRANSPORT:-in_process}"
        zonal_label="disabled"
        ;;
    *)
        echo "Usage: $0 [direct|zonal|default]" >&2
        exit 2
        ;;
esac

echo "[DEMO] Zonal controllers: ${zonal_label}"
echo "[DEMO] Gateway routing mode is controlled by OTA_USE_ZONAL_CONTROLLERS=${OTA_USE_ZONAL_CONTROLLERS}"
echo "[DEMO] Zone transport: ${OTA_ZONE_TRANSPORT}"

sudo ./scripts/setup_vcan_zones.sh
export LOCAL_UID="${LOCAL_UID:-$(id -u)}"
export LOCAL_GID="${LOCAL_GID:-$(id -g)}"

docker compose -f docker/docker-compose.ecus.yml --profile deep-zonal down --remove-orphans >/dev/null 2>&1 || true
docker rm -f virtual-ota-gateway virtual-ota-bcm virtual-ota-cluster virtual-ota-zone-gateway virtual-ota-zone-body virtual-ota-zone-cluster virtual-ota-zone-cockpit >/dev/null 2>&1 || true

docker compose -f docker/docker-compose.ecus.yml "${compose_profiles[@]}" up --build
