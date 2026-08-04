#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

print_header() {
    echo
    echo "============================================================"
    echo "$1"
    echo "============================================================"
}

show_ecu() {
    local ecu="$1"
    print_header "${ecu^^} STATE"

    if [[ -f "ecus/${ecu}/version.json" ]]; then
        echo "[version.json]"
        cat "ecus/${ecu}/version.json"
    else
        echo "Missing ecus/${ecu}/version.json"
    fi

    if [[ -f "ecus/${ecu}/slot_state.json" ]]; then
        echo
        echo "[slot_state.json]"
        cat "ecus/${ecu}/slot_state.json"
    else
        echo "Missing ecus/${ecu}/slot_state.json"
    fi

    for slot in A B; do
        local slot_dir="ecus/${ecu}/slots/${slot}"
        if [[ -d "${slot_dir}" ]]; then
            echo
            echo "[slot ${slot}]"
            [[ -f "${slot_dir}/flash_layout.json" ]] && { echo "flash_layout.json"; cat "${slot_dir}/flash_layout.json"; }
            [[ -f "${slot_dir}/flash_journal.json" ]] && { echo; echo "flash_journal.json"; cat "${slot_dir}/flash_journal.json"; }
            [[ -f "${slot_dir}/activation_control.json" ]] && { echo; echo "activation_control.json"; cat "${slot_dir}/activation_control.json"; }
            if [[ -f "${slot_dir}/flash_memory.bin" ]]; then
                echo
                echo "full_partition_sha256"
                sha256sum "${slot_dir}/flash_memory.bin"
                if [[ -f "${slot_dir}/flash_layout.json" ]]; then
                    echo
                    echo "payload_region_sha256"
                    python3 - "${slot_dir}/flash_memory.bin" "${slot_dir}/flash_layout.json" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

flash_path = Path(sys.argv[1])
layout_path = Path(sys.argv[2])
layout = json.loads(layout_path.read_text(encoding="utf-8"))
payload_size = int(layout.get("payload_size", 0))
payload = flash_path.read_bytes()[:payload_size]
print(hashlib.sha256(payload).hexdigest(), flash_path)
print("expected_payload_sha256", layout.get("payload_sha256", ""))
PY
                fi
            fi
            find "${slot_dir}" -maxdepth 1 -name '*.bin' -type f -print
        fi
    done
}

for ecu in gateway bcm cluster; do
    show_ecu "${ecu}"
done
