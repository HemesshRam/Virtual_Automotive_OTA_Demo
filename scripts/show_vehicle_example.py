#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from vehicle.topology_loader import VehicleTopology


def main(argv: list[str] | None = None) -> int:
    args = argv or sys.argv[1:]
    topology_path = Path(args[0] if args else "vehicle/topology.json")
    topology = VehicleTopology(topology_path)
    data = topology.data

    print("=" * 60)
    print("VEHICLE NETWORK EXAMPLE")
    print("=" * 60)
    print(f"Topology file : {topology_path}")
    if data.get("platform_definition"):
        print(f"Platform file : {data['platform_definition']}")
    if data.get("runtime_mapping"):
        print(f"Runtime file  : {data['runtime_mapping']}")
    print(f"Vehicle       : {data['vehicle'].get('model', 'UNKNOWN')}")
    print(f"Architecture  : {data['vehicle'].get('architecture', 'UNKNOWN')}")
    print(f"Gateway       : {data['central_gateway'].get('name', 'UNKNOWN')}")
    print()

    for zone in data.get("zones", []):
        network = zone.get("network", {})
        print(f"{zone['zone_id']} | {zone['display_name']}")
        print(
            f"  Network : {network.get('type', 'UNKNOWN')} "
            f"channel={network.get('channel', 'n/a')}"
        )
        for ecu in zone.get("ecus", []):
            deps = ", ".join(ecu.get("dependencies", [])) or "None"
            print(
                f"  - {ecu['ecu_name']} "
                f"(role={ecu.get('ecu_role', 'unknown')} "
                f"LA={ecu['logical_address']} CAN={ecu['can_id']} "
                f"deps={deps})"
            )
        print()

    print("JSON summary")
    print("-" * 60)
    print(json.dumps(data, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
