#!/usr/bin/env bash
set -euo pipefail

interfaces=(vcan_gate vcan_bcm vcan_clus)
missing=()

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

exec "$@"
