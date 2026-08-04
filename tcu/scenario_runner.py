import argparse
import json
import os
import sys
from copy import deepcopy
from pathlib import Path

from common.demo_state_presets import apply_preset, expected_versions_for_preset, list_presets
from ecus.base.runtime_control import DEFAULT_RUNTIME_CONTROL, save_runtime_control
from vehicle.topology_loader import VehicleTopology


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCENARIO_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "scenarios"
SERVER_CAMPAIGN_POINTER = SCENARIO_RUNTIME_DIR / "active_campaign_path.txt"
DEFAULT_SCENARIO_PATH = PROJECT_ROOT / "scenarios" / "default_https_mqtt.json"

ECU_ENV_MAP = {
    "Gateway ECU": "OTA_ECU_GATEWAY_CAN_CHANNEL",
    "BCM ECU": "OTA_ECU_BCM_CAN_CHANNEL",
    "Cluster ECU": "OTA_ECU_CLUSTER_CAN_CHANNEL",
}

ECU_RUNTIME_KEYS = {
    "Gateway ECU": "gateway",
    "BCM ECU": "bcm",
    "Cluster ECU": "cluster",
}

TOPOLOGY_MODE_DEFINITIONS = {
    "default": {
        "zone_assignments": {},
    },
    "body_two_ecus": {
        "zone_assignments": {
            "Cluster ECU": "body_zone",
        },
    },
}

DEPENDENCY_MODE_DEFINITIONS = {
    "topology_default": {
        "dependency_overrides": None,
        "target_overrides": {},
    },
    "cluster_depends_gateway": {
        "dependency_overrides": {
            "Gateway ECU": [],
            "BCM ECU": ["Gateway ECU"],
            "Cluster ECU": ["Gateway ECU"],
        },
        "target_overrides": {},
    },
    "bcm_before_gateway": {
        "dependency_overrides": {
            "BCM ECU": [],
            "Gateway ECU": ["BCM ECU"],
            "Cluster ECU": ["Gateway ECU"],
        },
        "target_overrides": {},
    },
    "bcm_before_cluster_before_gateway": {
        "dependency_overrides": {
            "BCM ECU": [],
            "Cluster ECU": ["BCM ECU"],
            "Gateway ECU": ["Cluster ECU"],
        },
        "target_overrides": {},
    },
    "partial_skip_cluster": {
        "dependency_overrides": None,
        "target_overrides": {
            "Cluster ECU": {
                "mandatory": False,
                "minimum_bootloader": "9.9.0",
            }
        },
    },
}


class ScenarioRunner:
    def __init__(
        self,
        scenario_path: str | Path,
        transport_override: str | None = None,
        quiet_override: int | None = None,
        scenario_overrides: dict | None = None,
    ):
        self.scenario_path = Path(scenario_path)
        self.scenario = self._load_json(self.scenario_path)
        scenario_name_override = os.getenv("OTA_SCENARIO_NAME_OVERRIDE", "").strip()
        if scenario_name_override:
            self.scenario["scenario_name"] = scenario_name_override
        if transport_override:
            self.scenario["transport"] = transport_override.lower()
        if quiet_override is not None:
            self.scenario["quiet"] = int(quiet_override)
        if scenario_overrides:
            self.scenario.update(scenario_overrides)
        self.runtime_dir = SCENARIO_RUNTIME_DIR / self.scenario["scenario_name"]
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.runtime_topology_path = self.runtime_dir / "active_topology.json"
        self.runtime_campaign_path = self.runtime_dir / "active_campaign.json"

    def prepare(self) -> dict[str, str]:
        self._apply_ecu_state_preset()
        topology_path = self._compile_topology()
        campaign_path = self._compile_campaign()
        self._apply_runtime_controls()
        env = self._build_environment(topology_path, campaign_path)
        self._apply_environment(env)
        return env

    def _apply_ecu_state_preset(self) -> None:
        preset_name = self.scenario.get("ecu_state_preset", "").strip()
        if not preset_name:
            return
        description = apply_preset(preset_name)
        self.scenario["_ecu_state_preset_description"] = description
        self.scenario["_ecu_state_expected_versions"] = expected_versions_for_preset(preset_name)

    def _compile_topology(self) -> Path:
        base_path = PROJECT_ROOT / self.scenario.get("base_topology", "vehicle/topology.json")
        topology = VehicleTopology(base_path).data
        compiled = self._apply_topology_mutations(topology)

        validation_errors = VehicleTopology(self._write_temp_json(compiled, self.runtime_topology_path)).validate()
        if validation_errors:
            raise RuntimeError(
                "Scenario topology validation failed: " + "; ".join(validation_errors)
            )

        return self.runtime_topology_path

    def _compile_campaign(self) -> Path:
        base_path = PROJECT_ROOT / self.scenario.get("base_campaign", "campaigns/campaign_v1.default.json")
        campaign = self._load_json(base_path)

        dependency_mode = self.scenario.get("dependency_mode", "topology_default")
        dependency_profile = DEPENDENCY_MODE_DEFINITIONS.get(dependency_mode)
        if dependency_profile is None:
            raise RuntimeError(f"Unknown dependency_mode: {dependency_mode}")

        dependency_overrides = self.scenario.get(
            "dependency_overrides",
            dependency_profile["dependency_overrides"],
        )
        if dependency_overrides is not None:
            campaign["dependency_overrides"] = {
                ecu_name: list(dependencies)
                for ecu_name, dependencies in dependency_overrides.items()
            }
        else:
            campaign.pop("dependency_overrides", None)

        target_overrides = deepcopy(dependency_profile.get("target_overrides", {}))
        target_overrides.update(deepcopy(self.scenario.get("target_overrides", {})))
        if target_overrides:
            for target in campaign.get("targets", []):
                overrides = target_overrides.get(target["ecu_name"])
                if overrides:
                    target.update(overrides)

        if "campaign_id_suffix" in self.scenario:
            campaign["campaign_id"] = (
                f"{campaign['campaign_id']}_{self.scenario['campaign_id_suffix']}"
            )

        campaign["transport"] = self.scenario.get("transport", "DOIP").upper()
        campaign_path = self._write_temp_json(campaign, self.runtime_campaign_path)
        SERVER_CAMPAIGN_POINTER.parent.mkdir(parents=True, exist_ok=True)
        SERVER_CAMPAIGN_POINTER.write_text(str(campaign_path), encoding="utf-8")
        return campaign_path

    def _apply_runtime_controls(self) -> None:
        configured = deepcopy(self.scenario.get("ecu_runtime", {}))
        offline_feature = self.scenario.get("offline_feature", "heartbeat").lower()
        feature_key = self._offline_feature_key(offline_feature)
        offline_ecus = self.scenario.get("offline_ecus", [])

        for ecu_name, ecu_key in ECU_RUNTIME_KEYS.items():
            control = dict(DEFAULT_RUNTIME_CONTROL)
            control.update(configured.get(ecu_name, {}))
            if ecu_name in offline_ecus:
                control[feature_key] = False
            save_runtime_control(ecu_key, control)

    def _build_environment(self, topology_path: Path, campaign_path: Path) -> dict[str, str]:
        topology = VehicleTopology(topology_path)
        ecu_registry = topology.ecu_registry()
        transport = self.scenario.get("transport", "doip").lower()
        zonal_mode = self.scenario.get("zonal_mode", "deep-zonal").lower()
        platform_definition = topology.data.get("platform_definition", "")
        runtime_mapping = topology.data.get("runtime_mapping", "")

        env = {
            "OTA_SCENARIO_NAME": self.scenario["scenario_name"],
            "OTA_VEHICLE_TOPOLOGY": str(topology_path),
            "OTA_PLATFORM_DEFINITION": str(platform_definition),
            "OTA_RUNTIME_MAPPING": str(runtime_mapping),
            "OTA_CAMPAIGN_FILE": str(campaign_path),
            "OTA_TRANSPORT": transport,
            "OTA_CLOUD_CONTROL": "mqtt",
            "OTA_HTTPS_ENABLED": "1",
            "OTA_SERVER_URL": self.scenario.get("server_url", "https://127.0.0.1:8080"),
            "OTA_PUBLIC_BASE_URL": self.scenario.get("public_base_url", "https://127.0.0.1:8080"),
            "OTA_STATUS_URL": self.scenario.get("status_url", "https://127.0.0.1:8080/status"),
            "OTA_USE_ZONAL_CONTROLLERS": "1" if zonal_mode != "direct" else "0",
            "OTA_ZONE_TRANSPORT": "tcp" if zonal_mode in {"deep", "deep-zonal", "tcp"} else "in_process",
            "OTA_DEMO_QUIET": str(self.scenario.get("quiet", 1)),
            "OTA_SCENARIO_TOPOLOGY_MODE": self.scenario.get("topology_mode", "default"),
            "OTA_SCENARIO_DEPENDENCY_MODE": self.scenario.get("dependency_mode", "topology_default"),
            "OTA_SCENARIO_OFFLINE_ECUS": ",".join(self.scenario.get("offline_ecus", [])),
            "OTA_SCENARIO_ECU_STATE_PRESET": self.scenario.get("ecu_state_preset", ""),
            "OTA_SCENARIO_ECU_STATE_PRESET_DESCRIPTION": self.scenario.get("_ecu_state_preset_description", ""),
            "OTA_SCENARIO_ECU_STATE_EXPECTED_VERSIONS": json.dumps(
                self.scenario.get("_ecu_state_expected_versions", {}),
                sort_keys=True,
            ),
        }

        for ecu_name, env_key in ECU_ENV_MAP.items():
            channel = ecu_registry[ecu_name]["can_channel"]
            env[env_key] = channel

        return env

    def _apply_topology_mutations(self, topology: dict) -> dict:
        compiled = deepcopy(topology)
        topology_mode = self.scenario.get("topology_mode", "default")
        topology_profile = TOPOLOGY_MODE_DEFINITIONS.get(topology_mode)
        if topology_profile is None:
            raise RuntimeError(f"Unknown topology_mode: {topology_mode}")
        zone_assignments = deepcopy(topology_profile.get("zone_assignments", {}))
        zone_assignments.update(self.scenario.get("zone_assignments", {}))
        drop_empty = bool(self.scenario.get("drop_empty_zones", True))

        all_ecus = {}
        zone_templates = {}

        for zone in compiled.get("zones", []):
            zone_id = zone["zone_id"]
            zone_templates[zone_id] = zone
            for ecu in zone.get("ecus", []):
                all_ecus[ecu["ecu_name"]] = deepcopy(ecu)

        for zone in compiled.get("zones", []):
            zone["ecus"] = []

        original_zone_by_ecu = self._original_zone_by_ecu(topology)
        target_zone_by_ecu = {}
        for ecu_name in all_ecus:
            target_zone_by_ecu[ecu_name] = zone_assignments.get(
                ecu_name,
                original_zone_by_ecu[ecu_name],
            )

        zone_index = {zone["zone_id"]: zone for zone in compiled.get("zones", [])}
        for ecu_name, ecu in all_ecus.items():
            target_zone = target_zone_by_ecu[ecu_name]
            if target_zone not in zone_index:
                raise RuntimeError(f"Scenario assigns {ecu_name} to unknown zone {target_zone}")
            zone_index[target_zone]["ecus"].append(ecu)

        zone_overrides = self.scenario.get("zone_overrides", {})
        for zone_id, overrides in zone_overrides.items():
            if zone_id not in zone_index:
                raise RuntimeError(f"Unknown zone override target: {zone_id}")
            zone = zone_index[zone_id]
            network_overrides = overrides.get("network", {})
            if network_overrides:
                zone.setdefault("network", {}).update(network_overrides)
            policy_overrides = overrides.get("policy", {})
            if policy_overrides:
                zone.setdefault("policy", {}).update(policy_overrides)

        for zone in compiled.get("zones", []):
            zone["ecus"] = sorted(zone["ecus"], key=lambda ecu: ecu["ecu_name"])

        if drop_empty:
            compiled["zones"] = [
                zone for zone in compiled.get("zones", [])
                if zone.get("ecus")
            ]

        return compiled

    @staticmethod
    def _original_zone_by_ecu(topology: dict) -> dict[str, str]:
        mapping = {}
        for zone in topology.get("zones", []):
            for ecu in zone.get("ecus", []):
                mapping[ecu["ecu_name"]] = zone["zone_id"]
        return mapping

    @staticmethod
    def _load_json(path: Path) -> dict:
        with open(path, "r", encoding="utf-8") as fp:
            return json.load(fp)

    @staticmethod
    def _offline_feature_key(feature: str) -> str:
        mapping = {
            "heartbeat": "heartbeat_enabled",
            "diagnostics": "diagnostics_enabled",
            "programming": "programming_enabled",
        }
        if feature not in mapping:
            raise RuntimeError(
                f"Unknown offline_feature: {feature}. Expected heartbeat, diagnostics, or programming"
            )
        return mapping[feature]

    @staticmethod
    def _write_temp_json(payload: dict, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fp:
            json.dump(payload, fp, indent=2)
            fp.write("\n")
        return path

    @staticmethod
    def _apply_environment(env: dict[str, str]) -> None:
        for key, value in env.items():
            os.environ[key] = value


def _print_summary(env: dict[str, str]) -> None:
    print()
    print("=" * 60)
    print("SCENARIO PREPARED")
    print("=" * 60)
    print(f"Scenario      : {env['OTA_SCENARIO_NAME']}")
    print(f"Campaign file : {env['OTA_CAMPAIGN_FILE']}")
    print(f"Topology file : {env['OTA_VEHICLE_TOPOLOGY']}")
    if env.get("OTA_PLATFORM_DEFINITION"):
        print(f"Platform file : {env['OTA_PLATFORM_DEFINITION']}")
    if env.get("OTA_RUNTIME_MAPPING"):
        print(f"Runtime file  : {env['OTA_RUNTIME_MAPPING']}")
    print(f"Transport     : {env['OTA_TRANSPORT'].upper()}")
    print("Cloud control : HTTPS artifacts + MQTT notify")
    print(f"Topology mode : {env['OTA_SCENARIO_TOPOLOGY_MODE']}")
    print(f"Dependency    : {env['OTA_SCENARIO_DEPENDENCY_MODE']}")
    print(f"Zonal mode    : {env['OTA_ZONE_TRANSPORT']}")
    print(f"Offline ECUs  : {env['OTA_SCENARIO_OFFLINE_ECUS'] or 'None'}")
    if env.get("OTA_SCENARIO_ECU_STATE_PRESET"):
        description = env.get("OTA_SCENARIO_ECU_STATE_PRESET_DESCRIPTION") or env["OTA_SCENARIO_ECU_STATE_PRESET"]
        print(f"ECU state     : {description}")
    print(
        "ECU channels  : "
        f"Gateway={env['OTA_ECU_GATEWAY_CAN_CHANNEL']} "
        f"BCM={env['OTA_ECU_BCM_CAN_CHANNEL']} "
        f"Cluster={env['OTA_ECU_CLUSTER_CAN_CHANNEL']}"
    )
    print("=" * 60)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Prepare and run a dynamic OTA demo scenario"
    )
    parser.add_argument(
        "scenario",
        nargs="?",
        default=str(DEFAULT_SCENARIO_PATH),
        help="Path to scenario JSON",
    )
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="Generate runtime campaign/topology and apply controls without running TCU",
    )
    parser.add_argument(
        "--transport",
        choices=["doip", "vcan"],
        help="Override scenario transport",
    )
    parser.add_argument(
        "--quiet",
        choices=["0", "1"],
        help="Override scenario quiet mode",
    )
    parser.add_argument(
        "--topology-mode",
        choices=sorted(TOPOLOGY_MODE_DEFINITIONS),
        help="Override scenario topology mode",
    )
    parser.add_argument(
        "--dependency-mode",
        choices=sorted(DEPENDENCY_MODE_DEFINITIONS),
        help="Override scenario dependency mode",
    )
    parser.add_argument(
        "--offline-ecus",
        help="Comma-separated ECU names to force offline",
    )
    parser.add_argument(
        "--offline-feature",
        choices=["heartbeat", "diagnostics", "programming"],
        help="Which runtime control to disable for offline ECUs",
    )
    parser.add_argument(
        "--ecu-state-preset",
        choices=sorted(list_presets()),
        help="Apply a predefined ECU version/slot preset before running the scenario",
    )
    args = parser.parse_args(argv)

    scenario_overrides = {}
    if args.topology_mode:
        scenario_overrides["topology_mode"] = args.topology_mode
    if args.dependency_mode:
        scenario_overrides["dependency_mode"] = args.dependency_mode
    if args.offline_ecus is not None:
        scenario_overrides["offline_ecus"] = [
            value.strip()
            for value in args.offline_ecus.split(",")
            if value.strip()
        ]
    if args.offline_feature:
        scenario_overrides["offline_feature"] = args.offline_feature
    if args.ecu_state_preset:
        scenario_overrides["ecu_state_preset"] = args.ecu_state_preset

    runner = ScenarioRunner(
        args.scenario,
        transport_override=args.transport,
        quiet_override=int(args.quiet) if args.quiet is not None else None,
        scenario_overrides=scenario_overrides or None,
    )
    env = runner.prepare()
    _print_summary(env)

    if args.prepare_only:
        return 0

    from tcu.main import main as tcu_main

    return int(tcu_main() or 0)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
