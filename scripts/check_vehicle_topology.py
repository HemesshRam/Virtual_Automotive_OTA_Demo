#!/usr/bin/env python3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from vehicle.topology_loader import VehicleTopology


def main():
    topology = VehicleTopology()
    errors = topology.validate()
    if errors:
        for error in errors:
            print(f"[FAIL] {error}")
        raise SystemExit(1)

    ecu_registry = topology.ecu_registry()

    print(f"[OK] Vehicle topology loaded: {topology.path}")
    print("[OK] Vehicle topology schema and dependency graph validate")
    print(f"[OK] Vehicle architecture: {topology.data['vehicle']['architecture']}")
    print(f"[OK] Zones: {len(topology.zones)}")
    print(f"[OK] ECUs: {len(ecu_registry)}")

    for zone_id, zone in topology.build_zone_registry().items():
        ecu_names = ", ".join(
            ecu["ecu_name"]
            for ecu in zone["ecus"].values()
        )
        print(
            f"[OK] {zone_id} -> {zone['can_channel']} -> "
            f"{zone['service_host']}:{zone['service_port']} -> {ecu_names}"
        )

    print("[OK] Dependencies")
    for ecu_name, ecu in ecu_registry.items():
        dependencies = ecu.get("dependencies", [])
        print(
            f"[OK] {ecu_name} depends_on="
            f"{', '.join(dependencies) if dependencies else 'None'}"
        )


if __name__ == "__main__":
    main()
