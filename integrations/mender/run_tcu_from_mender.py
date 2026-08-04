#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

def resolve_project_root() -> Path:
    env_root = os.getenv("OTA_PROJECT_ROOT", "").strip()
    candidates = []
    if env_root:
        candidates.append(Path(env_root).expanduser().resolve())

    cwd = Path.cwd().resolve()
    candidates.extend([cwd] + list(cwd.parents))
    home_repo = Path.home() / "virtual-automotive-ota"
    candidates.append(home_repo.resolve())

    for candidate in candidates:
        if (candidate / "vehicle" / "topology_loader.py").exists() and (
            candidate / "tcu" / "main.py"
        ).exists():
            return candidate

    raise RuntimeError(
        "Unable to locate project root. Set OTA_PROJECT_ROOT to the "
        "virtual-automotive-ota repository path."
    )


PROJECT_ROOT = resolve_project_root()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

from tcu.scenario_runner import ScenarioRunner
from tcu.main import main as tcu_main


DEFAULT_DEPLOYMENT_FILE = "deployment.json"
DEFAULT_EXECUTION_SUMMARY_PATH = PROJECT_ROOT / "tcu" / "state" / "mender_execution_summary.json"
DEFAULT_ACTIVE_SCENARIO_FILE = PROJECT_ROOT / "runtime" / "mender" / "active_scenario.json"


def _load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as fp:
        return json.load(fp)


def _resolve_payload_file(payload_dir: Path, filename: str) -> Path:
    direct_path = payload_dir / filename
    if direct_path.exists():
        return direct_path

    matches = sorted(
        candidate
        for candidate in payload_dir.rglob(filename)
        if candidate.is_file()
    )
    if matches:
        return matches[0]

    raise FileNotFoundError(
        f"Missing {filename} in Mender payload directory: {payload_dir}"
    )


def _resolve_repo_file(path_value: str, default_relative: str) -> Path:
    candidate = Path(path_value or default_relative)
    if candidate.is_absolute():
        return candidate
    return (PROJECT_ROOT / candidate).resolve()


def _load_active_scenario_config(config: dict) -> dict:
    if not config.get("use_active_scenario"):
        return {}

    path_value = (
        os.getenv("OTA_MENDER_ACTIVE_SCENARIO_FILE", "").strip()
        or config.get("active_scenario_file", "")
        or str(DEFAULT_ACTIVE_SCENARIO_FILE)
    )
    scenario_path = _resolve_repo_file(path_value, str(DEFAULT_ACTIVE_SCENARIO_FILE))
    if not scenario_path.exists():
        return {}
    return _load_json(scenario_path)


def _merged_runtime_config(config: dict) -> dict:
    merged = dict(config)
    active = _load_active_scenario_config(config)
    if active:
        merged.update(active)
    return merged


def _scenario_overrides(payload_dir: Path, config: dict) -> dict:
    overrides: dict = {}

    passthrough_keys = [
        "base_topology",
        "base_campaign",
        "topology_mode",
        "dependency_mode",
        "offline_feature",
        "ecu_state_preset",
        "zonal_mode",
        "scenario_name",
        "drop_empty_zones",
        "campaign_id_suffix",
        "zone_assignments",
        "zone_overrides",
        "dependency_overrides",
        "target_overrides",
    ]
    for key in passthrough_keys:
        if key in config:
            overrides[key] = config[key]

    if "offline_ecus" in config:
        overrides["offline_ecus"] = list(config["offline_ecus"])
    if "server_url" in config:
        overrides["server_url"] = config["server_url"]
        overrides["public_base_url"] = config.get("public_base_url", config["server_url"])
        overrides["status_url"] = config.get("status_url", config["server_url"].rstrip("/") + "/status")
    return overrides


def run_from_payload(payload_dir: Path) -> int:
    deployment_file = _resolve_payload_file(payload_dir, DEFAULT_DEPLOYMENT_FILE)
    config = _merged_runtime_config(_load_json(deployment_file))
    scenario_path = _resolve_repo_file(
        config.get("scenario", "scenarios/dynamic_demo_template.json"),
        "scenarios/dynamic_demo_template.json",
    )
    transport = config.get("transport", "doip")
    quiet = int(config.get("quiet", 1))
    overrides = _scenario_overrides(payload_dir, config)

    runner = ScenarioRunner(
        scenario_path,
        transport_override=transport,
        quiet_override=quiet,
        scenario_overrides=overrides or None,
    )
    runner.prepare()
    os.environ["OTA_EXECUTION_SUMMARY_PATH"] = str(DEFAULT_EXECUTION_SUMMARY_PATH)

    # Mender is the deployment trigger, so the TCU should not wait for MQTT.
    os.environ["OTA_CLOUD_CONTROL"] = config.get("cloud_control", "http")
    os.environ["OTA_MENDER_ARTIFACT_NAME"] = config.get("artifact_name", "")
    os.environ["OTA_MENDER_SOFTWARE_NAME"] = config.get("software_name", "")
    os.environ["OTA_MENDER_SOFTWARE_VERSION"] = config.get("software_version", "")

    campaign_file = config.get("campaign_file")
    if campaign_file:
        campaign_path = _resolve_payload_file(deployment_file.parent, campaign_file).resolve()
        os.environ["OTA_CAMPAIGN_URL"] = f"file://{campaign_path}"

    tls_verify = config.get("tls_verify")
    if tls_verify is not None:
        os.environ["OTA_TLS_VERIFY"] = str(
            _resolve_repo_file(str(tls_verify), str(tls_verify))
        )

    return int(tcu_main() or 0)


def main(argv: list[str] | None = None) -> int:
    args = argv or sys.argv[1:]
    payload_dir = Path(args[0] if args else ".").resolve()
    return run_from_payload(payload_dir)


if __name__ == "__main__":
    raise SystemExit(main())
