import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from zones.zone_registry import ZONE_REGISTRY


def main():
    print("[OK] Zonal controller registry loaded")

    for zone_id, zone in ZONE_REGISTRY.items():
        ecu_names = ", ".join(
            info["ecu_name"]
            for info in zone["ecus"].values()
        )
        print(
            f"[OK] {zone_id} -> {zone['can_channel']} -> "
            f"{zone['service_host']}:{zone['service_port']} -> {ecu_names}"
        )


if __name__ == "__main__":
    main()
