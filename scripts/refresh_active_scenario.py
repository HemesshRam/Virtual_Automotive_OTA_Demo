#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from common.active_scenario import activate_scenario, current_scenario_fields


def _normalize_offline_ecus(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def _default_scenario_name(fields: dict) -> str:
    offline_names = fields.get("offline_ecus", [])
    if not offline_names:
        offline_slug = "none"
    else:
        offline_slug = "_".join(
            name.lower().replace(" ecu", "").replace(" ", "_")
            for name in offline_names
        )
    parts = [
        "prepared",
        fields.get("transport", "vcan"),
        fields.get("topology_mode", "default"),
        fields.get("dependency_mode", "topology_default"),
        offline_slug,
        fields.get("ecu_state_preset", "keep_current"),
    ]
    return "_".join(part.replace("-", "_") for part in parts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Refresh the canonical active scenario and regenerate compiled runtime files"
    )
    parser.add_argument("--scenario-name")
    parser.add_argument("--base-scenario")
    parser.add_argument("--base-campaign")
    parser.add_argument("--transport", choices=["doip", "vcan"])
    parser.add_argument("--topology-mode", choices=["default", "body_two_ecus", "midsize_demo"])
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
        "--offline-feature",
        choices=["heartbeat", "diagnostics", "programming"],
    )
    parser.add_argument("--runtime", choices=["python", "docker"])
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
    parser.add_argument("--server-url")
    parser.add_argument("--public-base-url")
    parser.add_argument("--status-url")
    parser.add_argument("--tls-verify")
    parser.add_argument("--quiet", choices=["0", "1"])
    parser.add_argument("--source")
    args = parser.parse_args(argv)

    fields = current_scenario_fields()

    if args.base_scenario:
        fields["base_scenario"] = args.base_scenario
    if args.base_campaign:
        fields["base_campaign"] = args.base_campaign
    if args.transport:
        fields["transport"] = args.transport
    if args.topology_mode:
        fields["topology_mode"] = args.topology_mode
    if args.dependency_mode:
        fields["dependency_mode"] = args.dependency_mode
    if args.offline_ecus is not None:
        fields["offline_ecus"] = _normalize_offline_ecus(args.offline_ecus)
    if args.offline_feature:
        fields["offline_feature"] = args.offline_feature
    if args.runtime:
        fields["runtime"] = args.runtime
    if args.ecu_state_preset:
        fields["ecu_state_preset"] = args.ecu_state_preset
    if args.server_url:
        fields["server_url"] = args.server_url
    if args.public_base_url:
        fields["public_base_url"] = args.public_base_url
    if args.status_url:
        fields["status_url"] = args.status_url
    if args.tls_verify:
        fields["tls_verify"] = args.tls_verify
    if args.quiet is not None:
        fields["quiet"] = int(args.quiet)
    if args.source:
        fields["source"] = args.source

    if args.scenario_name:
        fields["scenario_name"] = args.scenario_name
    else:
        fields["scenario_name"] = _default_scenario_name(fields)

    canonical, _env = activate_scenario(fields)
    print(f"Active scenario refreshed : {canonical['scenario_name']}")
    print(f"Transport                 : {canonical['transport']}")
    print(f"Topology                  : {canonical['topology_mode']}")
    print(f"Dependency                : {canonical['dependency_mode']}")
    print(f"Offline ECUs              : {', '.join(canonical.get('offline_ecus', [])) or 'None'}")
    print(f"Runtime                   : {canonical['runtime']}")
    print(f"ECU state preset          : {canonical['ecu_state_preset']}")
    print(f"Campaign file             : {canonical['campaign_file']}")
    print(f"Topology file             : {canonical['topology_file']}")
    print(f"Env file                  : {canonical['env_file']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
