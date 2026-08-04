import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from ecus.base.runtime_control import (
    DEFAULT_RUNTIME_CONTROL,
    load_runtime_control,
    save_runtime_control,
)


ECU_ALIASES = {
    "gateway": "gateway",
    "gate": "gateway",
    "bcm": "bcm",
    "body": "bcm",
    "cluster": "cluster",
    "clus": "cluster",
}

FEATURES = {
    "heartbeat": "heartbeat_enabled",
    "diagnostics": "diagnostics_enabled",
    "programming": "programming_enabled",
}


def parse_bool(value: str) -> bool:
    normalized = value.lower()
    if normalized in {"on", "online", "enable", "enabled", "1", "true"}:
        return True
    if normalized in {"off", "offline", "disable", "disabled", "0", "false"}:
        return False
    raise argparse.ArgumentTypeError(
        "state must be one of: on/off, online/offline, enable/disable"
    )


def reset_all() -> int:
    for ecu_key in sorted(set(ECU_ALIASES.values())):
        path = save_runtime_control(ecu_key, DEFAULT_RUNTIME_CONTROL)
        print(f"[OK] {ecu_key}: reset runtime control -> {path}")
    return 0


def show_all() -> int:
    for ecu_key in sorted(set(ECU_ALIASES.values())):
        control = load_runtime_control(ecu_key)
        print(f"{ecu_key}: {control}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Toggle simulated ECU runtime faults without restarting containers"
    )
    parser.add_argument(
        "ecu",
        help="gateway, bcm, cluster, all, or status",
    )
    parser.add_argument(
        "feature",
        nargs="?",
        choices=sorted(FEATURES),
        help="heartbeat, diagnostics, or programming",
    )
    parser.add_argument(
        "state",
        nargs="?",
        type=parse_bool,
        help="on/off",
    )
    args = parser.parse_args()

    ecu_arg = args.ecu.lower()
    if ecu_arg == "status":
        return show_all()
    if ecu_arg == "all" and args.feature == "heartbeat" and args.state is True:
        return reset_all()

    if ecu_arg not in ECU_ALIASES:
        parser.error("ecu must be one of: gateway, bcm, cluster, all, status")

    if args.feature is None or args.state is None:
        parser.error("feature and state are required unless ecu is 'status'")

    ecu_key = ECU_ALIASES[ecu_arg]
    field = FEATURES[args.feature]
    control = load_runtime_control(ecu_key)
    control[field] = args.state
    path = save_runtime_control(ecu_key, control)

    state_text = "enabled" if args.state else "disabled"
    print(f"[OK] {ecu_key} {args.feature} {state_text}")
    print(f"[OK] Runtime control updated: {path}")
    print(control)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
