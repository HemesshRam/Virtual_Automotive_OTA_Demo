#!/usr/bin/env bash
set -euo pipefail

interfaces=(vcan_gate vcan_bcm vcan_clus)

sudo modprobe vcan

for iface in "${interfaces[@]}"; do
    if ! ip link show "$iface" >/dev/null 2>&1; then
        sudo ip link add dev "$iface" type vcan
    fi

    sudo ip link set "$iface" up
    echo "$iface is up"
done
