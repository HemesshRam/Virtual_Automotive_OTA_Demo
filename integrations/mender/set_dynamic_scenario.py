#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from common.active_scenario import activate_scenario, current_scenario_fields
from integrations.mender.build_payload_dir import DEFAULT_PROFILE_PATH, load_profiles


DEFAULT_ACTIVE_SCENARIO_FILE = PROJECT_ROOT / "runtime" / "mender" / "active_scenario.json"


def _load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as fp:
        return json.load(fp)


def _base_profile(name: str, profiles: dict) -> dict:
    if name not in profiles:
        raise SystemExit(f"Unknown profile: {name}")
    profile = dict(profiles[name])
    profile.pop("description", None)
    profile.pop("use_active_scenario", None)
    profile.pop("active_scenario_file", None)
    return profile


def _normalized_offline_ecus(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _scenario_payload(args: argparse.Namespace, profiles: dict) -> dict:
    payload = {
        "scenario": "scenarios/dynamic_demo_template.json",
        "scenario_name": args.scenario_name,
        "transport": "doip",
        "topology_mode": "default",
        "dependency_mode": "topology_default",
        "offline_ecus": [],
        "ecu_state_preset": "keep_current",
        "offline_feature": args.offline_feature,
        "server_url": args.server_url,
        "cloud_control": "http",
        "quiet": 1,
        "tls_verify": args.tls_verify,
    }

    if args.profile:
        payload.update(_base_profile(args.profile, profiles))

    if args.transport:
        payload["transport"] = args.transport
    if args.topology_mode:
        payload["topology_mode"] = args.topology_mode
    if args.dependency_mode:
        payload["dependency_mode"] = args.dependency_mode
    if args.offline_ecus is not None:
        payload["offline_ecus"] = _normalized_offline_ecus(args.offline_ecus)
    if args.ecu_state_preset:
        payload["ecu_state_preset"] = args.ecu_state_preset
    if args.campaign:
        payload["base_campaign"] = args.campaign

    return payload


def _canonical_fields_from_payload(payload: dict) -> dict:
    fields = current_scenario_fields()
    fields.update(
        {
            "scenario_name": payload.get("scenario_name", fields["scenario_name"]),
            "base_scenario": payload.get("scenario", fields["base_scenario"]),
            "base_campaign": payload.get(
                "base_campaign",
                fields.get("base_campaign", "campaigns/campaign_v1.default.json"),
            ),
            "transport": payload.get("transport", fields["transport"]),
            "topology_mode": payload.get("topology_mode", fields["topology_mode"]),
            "dependency_mode": payload.get("dependency_mode", fields["dependency_mode"]),
            "offline_ecus": list(payload.get("offline_ecus", [])),
            "offline_feature": payload.get("offline_feature", fields["offline_feature"]),
            "runtime": payload.get("runtime", fields["runtime"]),
            "ecu_state_preset": payload.get(
                "ecu_state_preset",
                fields["ecu_state_preset"],
            ),
            "server_url": payload.get("server_url", fields["server_url"]),
            "public_base_url": payload.get(
                "public_base_url",
                payload.get("server_url", fields["public_base_url"]),
            ),
            "status_url": payload.get("status_url", fields["status_url"]),
            "tls_verify": payload.get("tls_verify", fields.get("tls_verify", "")),
            "quiet": int(payload.get("quiet", fields.get("quiet", 1))),
            "source": "mender_dynamic",
        }
    )
    return fields


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Set the active dynamic Mender OTA scenario for the generic TCU artifact"
    )
    parser.add_argument("--profile", help="Named profile from deployment_profiles.json")
    parser.add_argument("--transport", choices=["doip", "vcan"])
    parser.add_argument("--topology-mode", choices=["default", "body_two_ecus"])
    parser.add_argument(
        "--dependency-mode",
        choices=[
            "topology_default",
            "cluster_depends_gateway",
            "bcm_before_gateway",
            "bcm_before_cluster_before_gateway",
            "partial_skip_cluster",
        ],
    )
    parser.add_argument("--offline-ecus", help="Comma-separated ECU names")
    parser.add_argument(
        "--ecu-state-preset",
        choices=[
            "keep_current",
            "fresh_baseline",
            "gateway_bcm_updated_cluster_pending",
            "gateway_cluster_updated_bcm_pending",
            "bcm_cluster_updated_gateway_pending",
        ],
    )
    parser.add_argument("--offline-feature", choices=["heartbeat", "diagnostics", "programming"], default="heartbeat")
    parser.add_argument("--campaign", help="Override base campaign path relative to repo root")
    parser.add_argument("--scenario-name", default="mender_dynamic_demo")
    parser.add_argument("--server-url", default="https://127.0.0.1:8080")
    parser.add_argument("--tls-verify", default="docker/tls/demo-ca.crt")
    parser.add_argument("--active-scenario-file", default=str(DEFAULT_ACTIVE_SCENARIO_FILE))
    parser.add_argument("--show", action="store_true", help="Print the active scenario file")
    parser.add_argument("--reset", action="store_true", help="Reset to default dynamic scenario")
    parser.add_argument("--list-profiles", action="store_true")
    args = parser.parse_args(argv)

    profiles = load_profiles(DEFAULT_PROFILE_PATH)
    if args.list_profiles:
        for name, profile in profiles.items():
            print(f"{name}: {profile.get('description', '')}")
        return 0

    target_path = Path(args.active_scenario_file).expanduser()
    if not target_path.is_absolute():
        target_path = (PROJECT_ROOT / target_path).resolve()

    if args.show:
        if not target_path.exists():
            raise SystemExit(f"Active scenario file not found: {target_path}")
        print(target_path)
        print(json.dumps(_load_json(target_path), indent=2))
        return 0

    if args.reset:
        args.profile = args.profile or "default_doip"
        args.transport = args.transport or "doip"

    payload = _scenario_payload(args, profiles)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with open(target_path, "w", encoding="utf-8") as fp:
        json.dump(payload, fp, indent=2)
        fp.write("\n")

    activate_scenario(_canonical_fields_from_payload(payload))

    print(f"Dynamic Mender scenario written: {target_path}")
    print(f"Scenario name                 : {payload['scenario_name']}")
    print(f"Transport                     : {payload['transport']}")
    print(f"Topology mode                 : {payload['topology_mode']}")
    print(f"Dependency mode               : {payload['dependency_mode']}")
    print(f"Offline ECUs                  : {', '.join(payload['offline_ecus']) or 'None'}")
    print(f"ECU state preset              : {payload.get('ecu_state_preset', 'keep_current')}")
    if payload.get("base_campaign"):
        print(f"Base campaign                 : {payload['base_campaign']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
