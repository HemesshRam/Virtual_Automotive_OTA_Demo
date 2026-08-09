#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from common.active_scenario import ACTIVE_SCENARIO_PATH, activate_scenario
from integrations.mender.package_artifact import main as package_artifact_main

DEFAULT_BASE_SCENARIO = PROJECT_ROOT / "scenarios" / "dynamic_demo_template.json"
DEFAULT_ACTIVE_MENDER_SCENARIO = PROJECT_ROOT / "runtime" / "mender" / "active_scenario.json"
ACTIVE_TCU_ENV_FILE = PROJECT_ROOT / "runtime" / "scenarios" / "active_tcu_env.sh"
ACTIVE_SCENARIO_INFO_FILE = ACTIVE_SCENARIO_PATH

TOPOLOGY_CHOICES = {
    "default": {
        "topology_mode": "default",
        "display": "default",
    },
    "body-two": {
        "topology_mode": "body_two_ecus",
        "display": "body-two-ecus",
    },
}

DEPENDENCY_CHOICES = {
    "topology-default": "topology_default",
    "cluster-gateway": "cluster_depends_gateway",
    "bcm-gateway-cluster": "bcm_before_gateway",
    "bcm-cluster-gateway": "bcm_before_cluster_before_gateway",
    "partial-skip": "partial_skip_cluster",
}

OFFLINE_CHOICES = {
    "none": [],
    "gateway": ["Gateway ECU"],
    "bcm": ["BCM ECU"],
    "cluster": ["Cluster ECU"],
    "gateway-bcm": ["Gateway ECU", "BCM ECU"],
    "gateway-cluster": ["Gateway ECU", "Cluster ECU"],
    "bcm-cluster": ["BCM ECU", "Cluster ECU"],
}

ECU_STATE_CHOICES = {
    "keep-current": "keep_current",
    "fresh": "fresh_baseline",
    "gateway-bcm-updated": "gateway_bcm_updated_cluster_pending",
    "gateway-cluster-updated": "gateway_cluster_updated_bcm_pending",
    "bcm-cluster-updated": "bcm_cluster_updated_gateway_pending",
}

KNOWN_ECUS = {"Gateway ECU", "BCM ECU", "Cluster ECU"}


def _parse_optional_targets(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []
    normalized: list[str] = []
    for item in str(raw_value).split(","):
        name = item.strip()
        if not name:
            continue
        if name not in KNOWN_ECUS:
            raise SystemExit(
                f"Unknown ECU in --optional-targets: {name}. "
                f"Known ECUs: {', '.join(sorted(KNOWN_ECUS))}"
            )
        if name not in normalized:
            normalized.append(name)
    return normalized


def _default_scenario_name(args: argparse.Namespace) -> str:
    optional_targets = _parse_optional_targets(getattr(args, "optional_targets", ""))
    parts = [
        "prepared",
        args.transport,
        TOPOLOGY_CHOICES[args.topology]["display"],
        args.dependency,
        args.offline,
        args.ecu_state,
    ]
    if optional_targets:
        optional_slug = "-".join(
            name.lower().replace(" ecu", "").replace(" ", "-")
            for name in optional_targets
        )
        parts.append(f"optional-{optional_slug}")
    return "_".join(part.replace("-", "_") for part in parts)


def _artifact_name(args: argparse.Namespace) -> str:
    parts = [
        "virtual-ota",
        args.transport,
        TOPOLOGY_CHOICES[args.topology]["display"],
        args.dependency,
        args.offline,
        args.runtime,
    ]
    return "-".join(part.replace("_", "-") for part in parts)


def _artifact_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _resolve_artifact_path(
    value: str | None,
    args: argparse.Namespace,
    artifact_basename: str,
) -> Path | None:
    if not value:
        return None
    if value == "auto":
        return Path("/tmp") / f"{artifact_basename}.mender"
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = (PROJECT_ROOT / candidate).resolve()
    return candidate


def _scenario_overrides(args: argparse.Namespace, scenario_name: str) -> dict:
    optional_targets = _parse_optional_targets(getattr(args, "optional_targets", ""))
    target_overrides = {
        ecu_name: {
            "skip_if_unavailable": True,
            "skip_if_incompatible": True,
        }
        for ecu_name in optional_targets
    }
    overrides = {
        "scenario_name": scenario_name,
        "transport": args.transport,
        "topology_mode": TOPOLOGY_CHOICES[args.topology]["topology_mode"],
        "dependency_mode": DEPENDENCY_CHOICES[args.dependency],
        "offline_ecus": OFFLINE_CHOICES[args.offline],
        "offline_feature": args.offline_feature,
        "optional_targets": optional_targets,
        "ecu_state_preset": ECU_STATE_CHOICES[args.ecu_state],
        "server_url": args.server_url,
        "public_base_url": args.server_url,
        "status_url": args.status_url or args.server_url.rstrip("/") + "/status",
        "quiet": int(args.quiet),
        "zonal_mode": "deep-zonal",
    }
    if target_overrides:
        overrides["target_overrides"] = target_overrides
    if args.campaign:
        overrides["base_campaign"] = args.campaign
    return overrides


def _runtime_commands(args: argparse.Namespace) -> list[str]:
    offline_ecus = set(OFFLINE_CHOICES.get(args.offline, []))
    if args.runtime == "docker":
        if args.topology == "body-two":
            return [
                "bash scripts/run_body_multi_gateway_pair.sh",
                "bash scripts/run_body_multi_body_zone.sh",
                *(
                    []
                    if "BCM ECU" in offline_ecus
                    else ["bash scripts/run_body_multi_bcm_ecu.sh"]
                ),
                *(
                    []
                    if "Cluster ECU" in offline_ecus
                    else ["bash scripts/run_body_multi_cluster_ecu.sh"]
                ),
                "bash scripts/run_ota_server_https.sh",
            ]
        commands = [
            "bash scripts/run_gateway_zone_pair.sh",
        ]
        if "BCM ECU" not in offline_ecus:
            commands.append("bash scripts/run_bcm_zone_pair.sh")
        if "Cluster ECU" not in offline_ecus:
            commands.append("bash scripts/run_cluster_zone_pair.sh")
        commands.append("bash scripts/run_ota_server_https.sh")
        return commands

    if args.topology == "body-two":
        commands = [
            "OTA_VEHICLE_TOPOLOGY=vehicle/topology.body_multi_ecu.json python3 run_gateway.py",
            "OTA_VEHICLE_TOPOLOGY=vehicle/topology.body_multi_ecu.json python3 -m zones.run_zone_service gateway_zone",
            "OTA_VEHICLE_TOPOLOGY=vehicle/topology.body_multi_ecu.json python3 -m zones.run_zone_service body_zone",
        ]
        if "BCM ECU" not in offline_ecus:
            commands.append("OTA_VEHICLE_TOPOLOGY=vehicle/topology.body_multi_ecu.json python3 run_bcm.py")
        if "Cluster ECU" not in offline_ecus:
            commands.append("OTA_VEHICLE_TOPOLOGY=vehicle/topology.body_multi_ecu.json OTA_ECU_CLUSTER_CAN_CHANNEL=vcan_bcm python3 run_cluster.py")
        commands.append("bash scripts/run_ota_server_https.sh")
        return commands

    commands = [
        "python3 run_gateway.py",
        "python3 -m zones.run_zone_service gateway_zone",
        "python3 -m zones.run_zone_service body_zone",
        "python3 -m zones.run_zone_service cluster_zone",
    ]
    if "BCM ECU" not in offline_ecus:
        commands.insert(1, "python3 run_bcm.py")
    if "Cluster ECU" not in offline_ecus:
        commands.insert(2 if "BCM ECU" not in offline_ecus else 1, "python3 run_cluster.py")
    commands.append("bash scripts/run_ota_server_https.sh")
    return commands


def _print_next_steps(
    args: argparse.Namespace,
    scenario_name: str,
    env_file: Path,
    artifact_path: Path | None,
) -> None:
    print()
    print("=" * 60)
    print("NEXT STEPS")
    print("=" * 60)
    print("Project root:")
    print("  export PROJECT_ROOT=\"$(pwd)\"")
    print()
    print("Reset:")
    print("  bash scripts/stop_demo.sh || true")
    print("  bash scripts/reset_demo_state.sh")
    print("  sudo ./scripts/setup_vcan_zones.sh")
    print()
    print("Vehicle runtime:")
    for index, command in enumerate(_runtime_commands(args), start=1):
        print(f"  Terminal {index}: {command}")
    print()
    print("Non-Mender TCU:")
    print(f"  source {env_file}")
    print("  python3 -m tcu.main")
    print()
    print("Mender:")
    print(f"  Active scenario file : {DEFAULT_ACTIVE_MENDER_SCENARIO}")
    if artifact_path:
        print(f"  Artifact             : {artifact_path}")
    else:
        print("  Artifact             : not built in this run")
        print("  Build one later with:")
        print(
            "    python3 scripts/prepare_ota_scenario.py "
            f"--transport {args.transport} "
            f"--topology {args.topology} "
            f"--dependency {args.dependency} "
            f"--offline {args.offline} "
            f"--runtime {args.runtime} "
            f"--ecu-state {args.ecu_state} "
            "--build-mender auto"
        )
    print()
    print(f"Prepared scenario name : {scenario_name}")
    print("=" * 60)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Prepare a non-interactive OTA scenario and optionally build a matching dynamic Mender artifact"
    )
    parser.add_argument("--transport", choices=["doip", "vcan"], required=True)
    parser.add_argument("--topology", choices=sorted(TOPOLOGY_CHOICES), required=True)
    parser.add_argument("--dependency", choices=sorted(DEPENDENCY_CHOICES), required=True)
    parser.add_argument("--offline", choices=sorted(OFFLINE_CHOICES), default="none")
    parser.add_argument("--offline-feature", choices=["heartbeat", "diagnostics", "programming"], default="heartbeat")
    parser.add_argument(
        "--optional-targets",
        help="Comma-separated ECU names that may be skipped if unavailable or incompatible in this run",
    )
    parser.add_argument("--runtime", choices=["docker", "python"], required=True)
    parser.add_argument("--ecu-state", choices=sorted(ECU_STATE_CHOICES), default="fresh")
    parser.add_argument("--scenario-name")
    parser.add_argument("--campaign", help="Override base campaign path relative to repo root")
    parser.add_argument("--base-scenario", default=str(DEFAULT_BASE_SCENARIO))
    parser.add_argument("--server-url", default="https://127.0.0.1:8080")
    parser.add_argument("--status-url")
    parser.add_argument("--tls-verify", default="docker/tls/demo-ca.crt")
    parser.add_argument("--quiet", choices=["0", "1"], default="1")
    parser.add_argument(
        "--build-mender",
        nargs="?",
        const="auto",
        help="Build a dynamic .mender artifact at the given path, or auto-generate one under /tmp",
    )
    parser.add_argument("--artifact-name", help="Optional Mender artifact name override")
    parser.add_argument("--device-type", default="virtual-ota-tcu")
    parser.add_argument("--keep-payload-dir", action="store_true")
    args = parser.parse_args(argv)

    scenario_name = args.scenario_name or _default_scenario_name(args)
    fields = {
        "scenario_name": scenario_name,
        "base_scenario": args.base_scenario,
        "base_campaign": args.campaign or "campaigns/campaign_v1.default.json",
        "transport": args.transport,
        "topology_mode": TOPOLOGY_CHOICES[args.topology]["topology_mode"],
        "dependency_mode": DEPENDENCY_CHOICES[args.dependency],
        "offline_ecus": OFFLINE_CHOICES[args.offline],
        "offline_feature": args.offline_feature,
        "optional_targets": _parse_optional_targets(args.optional_targets),
        "runtime": args.runtime,
        "ecu_state_preset": ECU_STATE_CHOICES[args.ecu_state],
        "server_url": args.server_url,
        "public_base_url": args.server_url,
        "status_url": args.status_url or args.server_url.rstrip("/") + "/status",
        "tls_verify": args.tls_verify,
        "quiet": int(args.quiet),
        "source": "prepare_ota_scenario",
    }
    if fields["optional_targets"]:
        fields["target_overrides"] = {
            ecu_name: {
                "skip_if_unavailable": True,
                "skip_if_incompatible": True,
            }
            for ecu_name in fields["optional_targets"]
        }
    canonical, env = activate_scenario(fields)

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
    if fields["optional_targets"]:
        print(f"Optional ECUs : {', '.join(fields['optional_targets'])}")
    print(
        f"ECU state     : "
        f"{env.get('OTA_SCENARIO_ECU_STATE_PRESET_DESCRIPTION') or env.get('OTA_SCENARIO_ECU_STATE_PRESET', '')}"
    )
    print(
        "ECU channels  : "
        f"Gateway={env['OTA_ECU_GATEWAY_CAN_CHANNEL']} "
        f"BCM={env['OTA_ECU_BCM_CAN_CHANNEL']} "
        f"Cluster={env['OTA_ECU_CLUSTER_CAN_CHANNEL']}"
    )
    print("=" * 60)

    artifact_basename = args.artifact_name or f"{_artifact_name(args)}-{_artifact_timestamp()}"
    artifact_path = _resolve_artifact_path(args.build_mender, args, artifact_basename)
    if artifact_path is not None:
        artifact_args = [
            str(artifact_path),
            "--device-type",
            args.device_type,
            "--profile",
            "dynamic_generic",
            "--campaign",
            env["OTA_CAMPAIGN_FILE"],
            "--artifact-name",
            artifact_basename,
        ]
        if args.keep_payload_dir:
            artifact_args.append("--keep-payload-dir")
        package_artifact_main(artifact_args)

    print()
    print(f"TCU env file written        : {canonical['env_file']}")
    print(f"Active env shortcut written : {ACTIVE_TCU_ENV_FILE}")
    print(f"Mender active scenario      : {DEFAULT_ACTIVE_MENDER_SCENARIO}")
    print(f"Prepared scenario info      : {ACTIVE_SCENARIO_PATH}")
    _print_next_steps(args, scenario_name, Path(canonical["env_file"]), artifact_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
