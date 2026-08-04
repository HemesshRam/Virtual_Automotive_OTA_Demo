from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ECU_ROOT = PROJECT_ROOT / "ecus"


PRESET_DEFINITIONS = {
    "keep_current": {
        "description": "Keep current ECU versions as-is",
        "ecus": {},
    },
    "fresh_baseline": {
        "description": "All ECUs at 1.0.0",
        "ecus": {
            "gateway": {"version": "1.0.0", "slot": "A"},
            "bcm": {"version": "1.0.0", "slot": "A"},
            "cluster": {"version": "1.0.0", "slot": "A"},
        },
    },
    "gateway_bcm_updated_cluster_pending": {
        "description": "Gateway and BCM at 2.0.0, Cluster at 1.0.0",
        "ecus": {
            "gateway": {"version": "2.0.0", "slot": "B"},
            "bcm": {"version": "2.0.0", "slot": "B"},
            "cluster": {"version": "1.0.0", "slot": "A"},
        },
    },
    "gateway_cluster_updated_bcm_pending": {
        "description": "Gateway and Cluster at 2.0.0, BCM at 1.0.0",
        "ecus": {
            "gateway": {"version": "2.0.0", "slot": "B"},
            "bcm": {"version": "1.0.0", "slot": "A"},
            "cluster": {"version": "2.0.0", "slot": "B"},
        },
    },
    "bcm_cluster_updated_gateway_pending": {
        "description": "BCM and Cluster at 2.0.0, Gateway at 1.0.0",
        "ecus": {
            "gateway": {"version": "1.0.0", "slot": "A"},
            "bcm": {"version": "2.0.0", "slot": "B"},
            "cluster": {"version": "2.0.0", "slot": "B"},
        },
    },
}


def list_presets() -> dict[str, dict]:
    return PRESET_DEFINITIONS


def expected_versions_for_preset(preset_name: str) -> dict[str, str]:
    preset = PRESET_DEFINITIONS.get(preset_name, {})
    return {
        {
            "gateway": "Gateway ECU",
            "bcm": "BCM ECU",
            "cluster": "Cluster ECU",
        }[ecu_key]: state["version"]
        for ecu_key, state in preset.get("ecus", {}).items()
        if ecu_key in {"gateway", "bcm", "cluster"}
    }


def normalize_slot(slot: str) -> str:
    normalized = slot.strip().upper()
    if normalized not in {"A", "B"}:
        raise ValueError(f"Unsupported slot: {slot}")
    return normalized


def version_payload(version: str, slot: str) -> dict:
    return {
        "current_version": version,
        "confirmed_version": version,
        "pending_version": "",
        "active_slot": slot,
        "confirmed_slot": slot,
        "pending_slot": "",
        "pending_commit": False,
    }


def slot_state_payload(slot: str) -> dict:
    return {
        "active_slot": slot,
        "confirmed_slot": slot,
        "previous_slot": "B" if slot == "A" else "A",
        "pending_slot": "",
        "pending_file": "",
        "pending_version": "",
    }


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(payload, fp, indent=4)


def apply_preset(preset_name: str) -> str:
    if preset_name not in PRESET_DEFINITIONS:
        raise ValueError(f"Unknown ECU state preset: {preset_name}")

    preset = PRESET_DEFINITIONS[preset_name]
    for ecu_key, state in preset.get("ecus", {}).items():
        slot = normalize_slot(state["slot"])
        ecu_dir = ECU_ROOT / ecu_key
        _write_json(ecu_dir / "version.json", version_payload(state["version"], slot))
        _write_json(ecu_dir / "slot_state.json", slot_state_payload(slot))
    return preset["description"]
