import json
import os
import shlex
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tcu.scenario_runner import ScenarioRunner


DEFAULT_BASE_SCENARIO = PROJECT_ROOT / "scenarios" / "default_https_mqtt.json"
ACTIVE_SCENARIO_PATH = PROJECT_ROOT / "runtime" / "scenarios" / "active_prepared_scenario.json"
ACTIVE_ENV_PATH = PROJECT_ROOT / "runtime" / "scenarios" / "active_tcu_env.sh"
ACTIVE_MENDER_SCENARIO_PATH = PROJECT_ROOT / "runtime" / "mender" / "active_scenario.json"

MANAGED_ENV_KEYS = {
    "OTA_CAMPAIGN_FILE",
    "OTA_CLOUD_CONTROL",
    "OTA_DEMO_QUIET",
    "OTA_ECU_BCM_CAN_CHANNEL",
    "OTA_ECU_CLUSTER_CAN_CHANNEL",
    "OTA_ECU_GATEWAY_CAN_CHANNEL",
    "OTA_HTTPS_ENABLED",
    "OTA_PLATFORM_DEFINITION",
    "OTA_PUBLIC_BASE_URL",
    "OTA_RUNTIME_MAPPING",
    "OTA_SCENARIO_DEPENDENCY_MODE",
    "OTA_SCENARIO_ECU_STATE_EXPECTED_VERSIONS",
    "OTA_SCENARIO_ECU_STATE_PRESET",
    "OTA_SCENARIO_ECU_STATE_PRESET_DESCRIPTION",
    "OTA_SCENARIO_NAME",
    "OTA_SCENARIO_OFFLINE_ECUS",
    "OTA_SCENARIO_RUNTIME",
    "OTA_SCENARIO_TOPOLOGY_MODE",
    "OTA_SERVER_URL",
    "OTA_STATUS_URL",
    "OTA_TLS_VERIFY",
    "OTA_TRANSPORT",
    "OTA_USE_ZONAL_CONTROLLERS",
    "OTA_VEHICLE_TOPOLOGY",
    "OTA_ZONE_TRANSPORT",
}

DEFAULT_SCENARIO_FIELDS = {
    "scenario_name": "direct_run_manual",
    "base_scenario": "scenarios/default_https_mqtt.json",
    "base_campaign": "campaigns/campaign_v1.default.json",
    "transport": "vcan",
    "topology_mode": "default",
    "dependency_mode": "topology_default",
    "offline_ecus": [],
    "offline_feature": "heartbeat",
    "optional_targets": [],
    "runtime": "python",
    "ecu_state_preset": "keep_current",
    "server_url": "https://127.0.0.1:8080",
    "public_base_url": "https://127.0.0.1:8080",
    "status_url": "https://127.0.0.1:8080/status",
    "quiet": 1,
    "zonal_mode": "deep-zonal",
    "source": "manual",
}


def _resolve_path(path_value: str | Path, default_relative: str | Path) -> Path:
    candidate = Path(path_value or default_relative)
    if candidate.is_absolute():
        return candidate
    return (PROJECT_ROOT / candidate).resolve()


def load_active_scenario() -> dict:
    if not ACTIVE_SCENARIO_PATH.exists():
        return {}
    with open(ACTIVE_SCENARIO_PATH, "r", encoding="utf-8") as fp:
        return json.load(fp)


def current_scenario_fields() -> dict:
    data = dict(DEFAULT_SCENARIO_FIELDS)
    data.update(load_active_scenario())
    return data


def write_env_file(path: Path, env: dict[str, str]) -> None:
    lines = [
        "#!/usr/bin/env bash",
        "# Generated from the canonical active scenario state",
        "set -a",
    ]
    for key in sorted(env):
        lines.append(f"export {key}={shlex.quote(str(env[key]))}")
    lines.append("set +a")
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    path.chmod(0o755)


def mender_payload_from_fields(fields: dict) -> dict:
    return {
        "scenario": fields.get("base_scenario", DEFAULT_SCENARIO_FIELDS["base_scenario"]),
        "scenario_name": fields["scenario_name"],
        "transport": fields["transport"],
        "topology_mode": fields["topology_mode"],
        "dependency_mode": fields["dependency_mode"],
        "offline_ecus": list(fields.get("offline_ecus", [])),
        "offline_feature": fields.get("offline_feature", "heartbeat"),
        "optional_targets": list(fields.get("optional_targets", [])),
        "ecu_state_preset": fields.get("ecu_state_preset", "keep_current"),
        "server_url": fields.get("server_url", DEFAULT_SCENARIO_FIELDS["server_url"]),
        "public_base_url": fields.get(
            "public_base_url",
            fields.get("server_url", DEFAULT_SCENARIO_FIELDS["server_url"]),
        ),
        "status_url": fields.get(
            "status_url",
            DEFAULT_SCENARIO_FIELDS["status_url"],
        ),
        "tls_verify": fields.get("tls_verify", "docker/tls/demo-ca.crt"),
        "cloud_control": "http",
        "quiet": int(fields.get("quiet", 1)),
        "base_campaign": fields.get(
            "base_campaign",
            DEFAULT_SCENARIO_FIELDS["base_campaign"],
        ),
        "runtime": fields.get("runtime", "python"),
        "source": fields.get("source", "manual"),
    }


def activate_scenario(fields: dict) -> tuple[dict, dict]:
    merged = dict(DEFAULT_SCENARIO_FIELDS)
    merged.update(fields)

    base_scenario = _resolve_path(
        merged.get("base_scenario"),
        DEFAULT_SCENARIO_FIELDS["base_scenario"],
    )
    overrides = {
        "scenario_name": merged["scenario_name"],
        "transport": merged["transport"],
        "topology_mode": merged["topology_mode"],
        "dependency_mode": merged["dependency_mode"],
        "offline_ecus": list(merged.get("offline_ecus", [])),
        "offline_feature": merged.get("offline_feature", "heartbeat"),
        "target_overrides": merged.get("target_overrides", {}),
        "ecu_state_preset": merged.get("ecu_state_preset", "keep_current"),
        "server_url": merged.get("server_url", DEFAULT_SCENARIO_FIELDS["server_url"]),
        "public_base_url": merged.get(
            "public_base_url",
            merged.get("server_url", DEFAULT_SCENARIO_FIELDS["server_url"]),
        ),
        "status_url": merged.get(
            "status_url",
            DEFAULT_SCENARIO_FIELDS["status_url"],
        ),
        "quiet": int(merged.get("quiet", 1)),
        "zonal_mode": merged.get("zonal_mode", "deep-zonal"),
        "base_campaign": merged.get(
            "base_campaign",
            DEFAULT_SCENARIO_FIELDS["base_campaign"],
        ),
    }
    if merged.get("campaign_id_suffix"):
        overrides["campaign_id_suffix"] = merged["campaign_id_suffix"]

    runner = ScenarioRunner(
        base_scenario,
        transport_override=merged["transport"],
        quiet_override=int(merged.get("quiet", 1)),
        scenario_overrides=overrides,
    )
    env = runner.prepare()

    env["OTA_SCENARIO_RUNTIME"] = merged.get("runtime", "python")
    if merged.get("tls_verify"):
        env["OTA_TLS_VERIFY"] = str(
            _resolve_path(merged["tls_verify"], merged["tls_verify"])
        )

    env_file = Path(env["OTA_VEHICLE_TOPOLOGY"]).resolve().parent / "tcu_env.sh"
    write_env_file(env_file, env)
    write_env_file(ACTIVE_ENV_PATH, env)

    canonical = dict(merged)
    canonical.update(
        {
            "env_file": str(env_file),
            "campaign_file": env["OTA_CAMPAIGN_FILE"],
            "topology_file": env["OTA_VEHICLE_TOPOLOGY"],
            "platform_definition": env.get("OTA_PLATFORM_DEFINITION", ""),
            "runtime_mapping": env.get("OTA_RUNTIME_MAPPING", ""),
            "environment": dict(env),
            "mender_payload": mender_payload_from_fields(merged),
        }
    )

    ACTIVE_SCENARIO_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(ACTIVE_SCENARIO_PATH, "w", encoding="utf-8") as fp:
        json.dump(canonical, fp, indent=2)
        fp.write("\n")

    ACTIVE_MENDER_SCENARIO_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(ACTIVE_MENDER_SCENARIO_PATH, "w", encoding="utf-8") as fp:
        json.dump(canonical["mender_payload"], fp, indent=2)
        fp.write("\n")

    return canonical, env


def sync_process_environment_from_active(*, overwrite: bool = True) -> dict:
    active = load_active_scenario()
    env = active.get("environment", {})
    if not env:
        return {}

    for key, value in env.items():
        if key not in MANAGED_ENV_KEYS:
            continue
        if overwrite or key not in os.environ:
            os.environ[key] = str(value)
    return env


def active_campaign_path() -> str:
    active = load_active_scenario()
    return str(active.get("campaign_file", "")).strip()
