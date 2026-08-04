#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from common.demo_state_presets import apply_preset, normalize_slot
from common.demo_state_presets import version_payload, slot_state_payload
from common.demo_state_presets import _write_json as write_json  # reuse same writer
ECU_ROOT = PROJECT_ROOT / "ecus"


def set_ecu_state(ecu_key: str, version: str, slot: str) -> None:
    ecu_dir = ECU_ROOT / ecu_key
    write_json(ecu_dir / "version.json", version_payload(version, slot))
    write_json(ecu_dir / "slot_state.json", slot_state_payload(slot))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Set demo ECU versions to prove partial already-updated OTA scenarios."
    )
    parser.add_argument("--gateway-version", default="2.0.0")
    parser.add_argument("--bcm-version", default="2.0.0")
    parser.add_argument("--cluster-version", default="1.0.0")
    parser.add_argument("--gateway-slot", default="B")
    parser.add_argument("--bcm-slot", default="B")
    parser.add_argument("--cluster-slot", default="A")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if (
        args.gateway_version == "2.0.0"
        and args.bcm_version == "2.0.0"
        and args.cluster_version == "1.0.0"
        and args.gateway_slot.upper() == "B"
        and args.bcm_slot.upper() == "B"
        and args.cluster_slot.upper() == "A"
    ):
        apply_preset("gateway_bcm_updated_cluster_pending")
    else:
        set_ecu_state("gateway", args.gateway_version, normalize_slot(args.gateway_slot))
        set_ecu_state("bcm", args.bcm_version, normalize_slot(args.bcm_slot))
        set_ecu_state("cluster", args.cluster_version, normalize_slot(args.cluster_slot))

    print("Partial-update demo state applied")
    print(f"  Gateway ECU : {args.gateway_version} slot {args.gateway_slot.upper()}")
    print(f"  BCM ECU     : {args.bcm_version} slot {args.bcm_slot.upper()}")
    print(f"  Cluster ECU : {args.cluster_version} slot {args.cluster_slot.upper()}")
    print()
    print("Expected demo meaning:")
    print("  - Gateway ECU already satisfied")
    print("  - BCM ECU already satisfied")
    print("  - Cluster ECU still needs update")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
