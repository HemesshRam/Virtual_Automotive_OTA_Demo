#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROFILE_PATH = PROJECT_ROOT / "integrations" / "mender" / "deployment_profiles.json"


def load_profiles(path: Path = DEFAULT_PROFILE_PATH) -> dict:
    with open(path, "r", encoding="utf-8") as fp:
        return json.load(fp)


def _load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as fp:
        return json.load(fp)


def build_payload_dir(
    output_dir: Path,
    campaign_path: Path,
    *,
    scenario: str = "scenarios/dynamic_demo_template.json",
    transport: str = "doip",
    topology_mode: str = "default",
    dependency_mode: str = "topology_default",
    offline_ecus: list[str] | None = None,
    server_url: str = "https://127.0.0.1:8080",
    tls_verify: str = "docker/tls/demo-ca.crt",
    use_active_scenario: bool = False,
    active_scenario_file: str = "runtime/mender/active_scenario.json",
    runtime: str = "docker",
    auto_start_runtime: bool = True,
    ensure_vcan: bool = True,
    restart_runtime: bool = True,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    target_campaign = output_dir / "campaign.json"
    shutil.copyfile(campaign_path, target_campaign)
    campaign_data = _load_json(campaign_path)
    release_version = campaign_data.get("release_version", "")
    campaign_id = campaign_data.get("campaign_id", "")

    deployment = {
        "scenario": scenario,
        "scenario_name": output_dir.name,
        "campaign_id": campaign_id,
        "release_version": release_version,
        "transport": transport,
        "topology_mode": topology_mode,
        "dependency_mode": dependency_mode,
        "offline_ecus": list(offline_ecus or []),
        "server_url": server_url,
        "cloud_control": "http",
        "quiet": 1,
        "campaign_file": "campaign.json",
        "tls_verify": tls_verify,
        "use_active_scenario": bool(use_active_scenario),
        "active_scenario_file": active_scenario_file,
        "runtime": runtime,
        "auto_start_runtime": bool(auto_start_runtime),
        "ensure_vcan": bool(ensure_vcan),
        "restart_runtime": bool(restart_runtime),
    }
    with open(output_dir / "deployment.json", "w", encoding="utf-8") as fp:
        json.dump(deployment, fp, indent=2)
        fp.write("\n")
    return output_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a local Mender payload directory for the TCU bridge")
    parser.add_argument("output_dir", help="Destination directory")
    parser.add_argument("--campaign", default="campaigns/campaign_v1.default.json")
    parser.add_argument("--profile", help="Named deployment profile from deployment_profiles.json")
    parser.add_argument("--scenario", default="scenarios/dynamic_demo_template.json")
    parser.add_argument("--transport", choices=["doip", "vcan"], default="doip")
    parser.add_argument("--topology-mode", default="default")
    parser.add_argument("--dependency-mode", default="topology_default")
    parser.add_argument("--offline-ecus", default="", help="Comma-separated ECU names")
    parser.add_argument("--server-url", default="https://127.0.0.1:8080")
    parser.add_argument("--tls-verify", default="docker/tls/demo-ca.crt")
    parser.add_argument("--use-active-scenario", action="store_true")
    parser.add_argument("--active-scenario-file", default="runtime/mender/active_scenario.json")
    parser.add_argument("--runtime", choices=["docker", "python"], default="docker")
    parser.add_argument("--list-profiles", action="store_true")
    args = parser.parse_args(argv)

    profiles = load_profiles()
    if args.list_profiles:
        for name, profile in profiles.items():
            print(f"{name}: {profile.get('description', '')}")
        return 0

    transport = args.transport
    topology_mode = args.topology_mode
    dependency_mode = args.dependency_mode
    offline_ecus = [
        value.strip()
        for value in args.offline_ecus.split(",")
        if value.strip()
    ]
    use_active_scenario = bool(args.use_active_scenario)
    active_scenario_file = args.active_scenario_file

    if args.profile:
        if args.profile not in profiles:
            raise SystemExit(f"Unknown profile: {args.profile}")
        profile = profiles[args.profile]
        transport = profile.get("transport", transport)
        topology_mode = profile.get("topology_mode", topology_mode)
        dependency_mode = profile.get("dependency_mode", dependency_mode)
        offline_ecus = list(profile.get("offline_ecus", offline_ecus))
        use_active_scenario = bool(profile.get("use_active_scenario", use_active_scenario))
        active_scenario_file = profile.get("active_scenario_file", active_scenario_file)

    output_dir = Path(args.output_dir).resolve()
    campaign_path = (PROJECT_ROOT / args.campaign).resolve()
    build_payload_dir(
        output_dir,
        campaign_path,
        scenario=args.scenario,
        transport=transport,
        topology_mode=topology_mode,
        dependency_mode=dependency_mode,
        offline_ecus=offline_ecus,
        server_url=args.server_url,
        tls_verify=args.tls_verify,
        use_active_scenario=use_active_scenario,
        active_scenario_file=active_scenario_file,
        runtime=args.runtime,
    )
    print(f"Payload directory created: {output_dir}")
    print(f"Deployment file          : {output_dir / 'deployment.json'}")
    print(f"Campaign file            : {output_dir / 'campaign.json'}")
    if args.profile:
        print(f"Deployment profile       : {args.profile}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
