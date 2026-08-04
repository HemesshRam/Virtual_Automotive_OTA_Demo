import json
import os
from pathlib import Path


DEFAULT_RUNTIME_CONTROL = {
    "heartbeat_enabled": True,
    "diagnostics_enabled": True,
    "programming_enabled": True,
}


def runtime_control_path(ecu_key: str) -> Path:
    return Path("ecus") / ecu_key / "runtime_control.json"


def load_runtime_control(ecu_key: str) -> dict:
    path = runtime_control_path(ecu_key)
    if not path.exists():
        return dict(DEFAULT_RUNTIME_CONTROL)

    try:
        with open(path, "r", encoding="utf-8") as fp:
            data = json.load(fp)
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULT_RUNTIME_CONTROL)

    control = dict(DEFAULT_RUNTIME_CONTROL)
    control.update(
        {
            key: bool(data[key])
            for key in DEFAULT_RUNTIME_CONTROL
            if key in data
        }
    )
    return control


def save_runtime_control(ecu_key: str, control: dict) -> Path:
    path = runtime_control_path(ecu_key)
    path.parent.mkdir(parents=True, exist_ok=True)

    normalized = dict(DEFAULT_RUNTIME_CONTROL)
    normalized.update(
        {
            key: bool(control[key])
            for key in DEFAULT_RUNTIME_CONTROL
            if key in control
        }
    )

    try:
        with open(path, "w", encoding="utf-8") as fp:
            json.dump(normalized, fp, indent=2)
            fp.write("\n")
    except PermissionError as exc:
        raise PermissionError(
            f"Unable to write runtime control file: {path}. "
            "This usually happens after Docker-created state files are owned by a different user. "
            "Fix with: sudo chown -R $(id -u):$(id -g) ecus/gateway ecus/bcm ecus/cluster"
        ) from exc

    return path
