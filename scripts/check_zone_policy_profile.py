#!/usr/bin/env python3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from zones.zone_registry import OTA_ALLOWED_UDS_SERVICES, ZONE_REGISTRY


def main():
    required = {0x10, 0x11, 0x22, 0x27, 0x31, 0x34, 0x36, 0x37, 0x3E}
    configured = set(OTA_ALLOWED_UDS_SERVICES)
    if required != configured:
        missing = ", ".join(f"0x{item:02X}" for item in sorted(required - configured))
        extra = ", ".join(f"0x{item:02X}" for item in sorted(configured - required))
        raise SystemExit(f"[FAIL] UDS policy mismatch missing={missing} extra={extra}")

    print("[OK] Zone UDS service policy covers OTA programming flow")
    for zone_id, zone in ZONE_REGISTRY.items():
        if zone.get("default_health") != "ONLINE":
            raise SystemExit(f"[FAIL] {zone_id} default health is not ONLINE")
        if not zone.get("programming_allowed"):
            raise SystemExit(f"[FAIL] {zone_id} programming is not allowed by default")
        print(
            f"[OK] {zone_id} policy -> health={zone['default_health']} "
            f"programming_allowed={zone['programming_allowed']}"
        )


if __name__ == "__main__":
    main()
