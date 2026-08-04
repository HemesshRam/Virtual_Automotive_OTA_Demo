#!/usr/bin/env python3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from zones.zone_transport_client import ZoneTransportClient


def main():
    client = ZoneTransportClient()
    inventories = client.inventory()
    for inventory in inventories:
        ecu_names = ", ".join(ecu["ecu_name"] for ecu in inventory["ecus"])
        health = inventory["health"]
        policy = inventory["policy"]
        metrics = inventory["metrics"]
        print(
            f"[OK] {inventory['zone_id']} service online -> "
            f"{inventory['can_channel']} -> {ecu_names} -> "
            f"health={health['state']} programming_allowed={policy['programming_allowed']} "
            f"requests={metrics['requests']} rejected={metrics['rejected']}"
        )


if __name__ == "__main__":
    main()
