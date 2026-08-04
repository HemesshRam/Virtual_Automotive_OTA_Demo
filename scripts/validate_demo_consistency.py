#!/usr/bin/env python3
import json
from pathlib import Path
import sys


ECUS = ("gateway", "bcm", "cluster")


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as fp:
        return json.load(fp)


def validate_ecu(ecu: str) -> list[str]:
    errors = []
    ecu_root = Path("ecus") / ecu
    version = load_json(ecu_root / "version.json")
    slot_state = load_json(ecu_root / "slot_state.json")

    if version["active_slot"] != slot_state["active_slot"]:
        errors.append("active_slot mismatch between version.json and slot_state.json")
    if version["confirmed_slot"] != slot_state["confirmed_slot"]:
        errors.append("confirmed_slot mismatch between version.json and slot_state.json")

    active_slot = version["active_slot"]
    slot_dir = ecu_root / "slots" / active_slot
    layout_path = slot_dir / "flash_layout.json"
    journal_path = slot_dir / "flash_journal.json"
    control_path = slot_dir / "activation_control.json"

    for path in (layout_path, journal_path, control_path):
        if not path.exists():
            errors.append(f"missing {path.name} in active slot {active_slot}")

    if errors:
        return errors

    journal = load_json(journal_path)
    control = load_json(control_path)
    layout = load_json(layout_path)

    if journal.get("state") not in {"CONFIRMED", "BOOTED_PENDING", "VERIFIED", "PENDING_ACTIVATION"}:
        errors.append(f"unexpected journal state {journal.get('state')}")
    if control.get("active") is not True:
        errors.append("activation_control active flag is not true for active slot")
    if control.get("confirmed") != (version.get("pending_commit") is False):
        errors.append("activation_control confirmed flag inconsistent with pending_commit")
    if layout.get("payload_sha256") != control.get("payload_sha256"):
        errors.append("flash_layout payload_sha256 does not match activation_control payload_sha256")
    if layout.get("payload_size") != control.get("payload_size"):
        errors.append("flash_layout payload_size does not match activation_control payload_size")
    if layout.get("payload_address") != control.get("flash_address"):
        errors.append("flash_layout payload_address does not match activation_control flash_address")

    return errors


def main():
    overall_errors = []
    for ecu in ECUS:
        errors = validate_ecu(ecu)
        if errors:
            overall_errors.append((ecu, errors))

    if overall_errors:
        for ecu, errors in overall_errors:
            print(f"[FAIL] {ecu}")
            for error in errors:
                print(f"  - {error}")
        sys.exit(1)

    for ecu in ECUS:
        print(f"[OK] {ecu}")


if __name__ == "__main__":
    main()
