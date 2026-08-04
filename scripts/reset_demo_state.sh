#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "Resetting ECU demo state..."

if ! test -w "ecus/gateway" || ! test -w "ecus/bcm" || ! test -w "ecus/cluster"; then
    echo "Permission issue detected in ECU state directories." >&2
    echo "If Docker created files as another user, run:" >&2
    echo "  sudo chown -R $(id -u):$(id -g) ecus/gateway ecus/bcm ecus/cluster" >&2
fi

for ecu in gateway bcm cluster; do
    rm -f "ecus/${ecu}/version.json"
    rm -f "ecus/${ecu}/slot_state.json"
    rm -f "ecus/${ecu}/installed/"*.bin 2>/dev/null || true
    rm -f "ecus/${ecu}/downloads/"*.bin 2>/dev/null || true
    rm -f "ecus/${ecu}/slots/A/"* 2>/dev/null || true
    rm -f "ecus/${ecu}/slots/B/"* 2>/dev/null || true
    rm -f "ecus/${ecu}/runtime_control.json"
done

rm -f "runtime/scenarios/active_campaign_path.txt"
rm -f "runtime/scenarios/active_scenario_metadata.json"
rm -f "runtime/scenarios/active_prepared_scenario.json"
rm -f "runtime/scenarios/active_tcu_env.sh"
rm -f "runtime/mender/active_scenario.json"

echo "All ECU state files, staged images, and emulated flash partitions cleared."
echo "Cleared canonical active scenario state for direct-run and Mender demos."
echo "Ready for a fresh OTA demo."
