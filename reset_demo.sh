#!/bin/bash
#
# Reset ECU versions to 1.0.0 for a fresh OTA demo
#
# Usage:
#   ./reset_demo.sh
#

echo "Resetting ECU versions..."

rm -f ecus/gateway/version.json
rm -f ecus/bcm/version.json
rm -f ecus/cluster/version.json

rm -f ecus/gateway/installed/*.bin
rm -f ecus/bcm/installed/*.bin
rm -f ecus/cluster/installed/*.bin

rm -f ecus/gateway/downloads/*.bin
rm -f ecus/bcm/downloads/*.bin
rm -f ecus/cluster/downloads/*.bin

echo "All ECUs reset to version 1.0.0"
echo "Ready for a fresh OTA demo"
