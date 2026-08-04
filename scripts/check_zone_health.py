import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from zones.zone_transport_client import ZoneTransportClient


def main() -> int:
    try:
        inventories = ZoneTransportClient().inventory()
    except Exception as exc:
        print(f"[FAIL] Could not query zone services: {exc}")
        return 1

    print()
    print("=" * 60)
    print("ZONE HEALTH / ECU AVAILABILITY")
    print("=" * 60)

    for inventory in inventories:
        health = inventory["health"]
        print(
            f"{inventory['zone_id']} | {health['state']} | "
            f"{inventory['can_channel']}"
        )
        print(f"  Reason: {health['reason'] or 'NONE'}")

        heartbeat = health.get("heartbeat_monitor", {})
        print(
            "  Heartbeat: "
            f"enabled={heartbeat.get('enabled')} "
            f"timeout={heartbeat.get('timeout_seconds')}s"
        )

        for ecu in inventory["ecus"]:
            availability = ecu.get("availability", {})
            age = availability.get("last_seen_age_seconds")
            age_text = "never" if age is None else f"{age}s ago"
            print(
                f"  {ecu['ecu_name']} "
                f"LA={ecu['logical_address']} CAN={ecu['can_id']} "
                f"state={availability.get('state')} last_seen={age_text}"
            )

    print("=" * 60)
    print(json.dumps(inventories, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
