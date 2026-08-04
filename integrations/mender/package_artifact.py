#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from integrations.mender.build_payload_dir import PROJECT_ROOT, build_payload_dir, load_profiles


def _load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as fp:
        return json.load(fp)


def _normalize_artifact_name(name: str) -> str:
    return name.replace("_", "-")


def _artifact_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build_artifact_command(
    artifact_name: str,
    output_artifact: Path,
    device_type: str,
    payload_dir: Path,
    software_name: str,
    software_version: str,
    *,
    mender_artifact_bin: str = "mender-artifact",
) -> list[str]:
    files_dir = sorted(str(path) for path in payload_dir.iterdir() if path.is_file())
    command = [
        mender_artifact_bin,
        "write",
        "module-image",
        "-T",
        "tcu-ota-module",
        "-n",
        artifact_name,
        "-o",
        str(output_artifact),
        "-t",
        device_type,
        "--software-name",
        software_name,
        "--software-version",
        software_version,
        "-p",
        f"ota.release.version:{software_version}",
        "-p",
        f"ota.artifact.name:{artifact_name}",
    ]
    for file_path in files_dir:
        command.extend(["-f", file_path])
    return command


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Package a Mender Artifact for the TCU OTA update module")
    parser.add_argument("output_artifact", help="Path to the output .mender file")
    parser.add_argument("--device-type", required=True, help="Mender device type")
    parser.add_argument("--profile", default="default_doip", help="Named deployment profile")
    parser.add_argument("--campaign", default="campaigns/campaign_v1.default.json")
    parser.add_argument("--artifact-name", help="Artifact name; defaults to profile name")
    parser.add_argument("--payload-dir", help="Optional prebuilt payload directory")
    parser.add_argument("--mender-artifact-bin", default="mender-artifact")
    parser.add_argument("--keep-payload-dir", action="store_true")
    parser.add_argument("--print-only", action="store_true")
    args = parser.parse_args(argv)

    profiles = load_profiles()
    if args.profile not in profiles:
        raise SystemExit(f"Unknown profile: {args.profile}")
    profile = profiles[args.profile]

    output_artifact = Path(args.output_artifact).resolve()

    if args.payload_dir:
        payload_dir = Path(args.payload_dir).resolve()
    else:
        payload_dir = output_artifact.parent / f"{_normalize_artifact_name(args.profile)}.payload"
        campaign_path = (PROJECT_ROOT / args.campaign).resolve()
        build_payload_dir(
            payload_dir,
            campaign_path,
            transport=profile["transport"],
            topology_mode=profile["topology_mode"],
            dependency_mode=profile["dependency_mode"],
            offline_ecus=profile.get("offline_ecus", []),
        )

    deployment_data = _load_json(payload_dir / "deployment.json")
    software_version = deployment_data.get("release_version", "2.0.0")
    artifact_name = args.artifact_name or (
        f"virtual-ota-{_normalize_artifact_name(args.profile)}-"
        f"r{software_version}-{_artifact_timestamp()}"
    )
    software_name = "virtual-ota"

    deployment_data.update(
        {
            "artifact_name": artifact_name,
            "software_name": software_name,
            "software_version": software_version,
        }
    )
    with open(payload_dir / "deployment.json", "w", encoding="utf-8") as fp:
        json.dump(deployment_data, fp, indent=2)
        fp.write("\n")

    command = build_artifact_command(
        artifact_name,
        output_artifact,
        args.device_type,
        payload_dir,
        software_name=software_name,
        software_version=software_version,
        mender_artifact_bin=args.mender_artifact_bin,
    )

    if args.print_only:
        print(" ".join(command))
        return 0

    if shutil.which(args.mender_artifact_bin) is None:
        raise SystemExit(
            f"{args.mender_artifact_bin} not found in PATH. Install mender-artifact "
            "or rerun with --print-only."
        )

    subprocess.run(command, check=True)
    print(f"Mender Artifact created: {output_artifact}")
    print(f"Payload directory      : {payload_dir}")

    if not args.keep_payload_dir:
        shutil.rmtree(payload_dir, ignore_errors=True)
        print("Payload directory removed after packaging")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
