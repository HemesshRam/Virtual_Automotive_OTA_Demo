#!/usr/bin/env python3
"""
Generate binary OTA firmware images for the demo repository.

This script converts the release manifest into structured binary images and
updates the manifest with image metadata so the rest of the stack can treat the
artifacts like real ECU firmware packages.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from firmware.image_format import (
    FirmwareImageSpec,
    build_firmware_image,
    looks_like_firmware_image,
    parse_firmware_image,
)
from scripts.refresh_demo_trust_metadata import refresh_demo_trust_metadata


RELEASE_DIR = REPO_ROOT / "firmware" / "releases" / "2.0.0"
MANIFEST_PATH = RELEASE_DIR / "manifest.json"


# ~50 MB payload sizes for realistic large-file OTA transfer testing.
# Each ECU has a slightly different size to keep the variation pattern.
_50MB = 50 * 1024 * 1024  # 52,428,800 bytes

PACKAGE_SPECS = {
    "Gateway ECU": {
        "ecu_id": 1,
        "part_number": "GWY-HW-A1",
        "flash_address": 0x08000000,
        "payload_size": _50MB,
        # Optional:
        # "payload_file": REPO_ROOT / "artifacts" / "gateway_real.bin",
    },
    "BCM ECU": {
        "ecu_id": 2,
        "part_number": "BCM-HW-A1",
        "flash_address": 0x08010000,
        "payload_size": _50MB - (512 * 1024),  # ~49.5 MB
        # Optional:
        # "payload_file": REPO_ROOT / "artifacts" / "bcm_real.bin",
    },
    "Cluster ECU": {
        "ecu_id": 3,
        "part_number": "CLU-HW-A1",
        "flash_address": 0x08020000,
        "payload_size": _50MB - (256 * 1024),  # ~49.75 MB
        # Optional:
        # "payload_file": REPO_ROOT / "artifacts" / "cluster_real.bin",
    },
}


def _load_payload_bytes(spec_data: dict) -> tuple[bytes | None, int, Path | None]:
    payload_file = spec_data.get("payload_file")
    if payload_file is None:
        return None, int(spec_data["payload_size"]), None

    payload_path = Path(payload_file)
    if not payload_path.is_absolute():
        payload_path = (REPO_ROOT / payload_path).resolve()

    if not payload_path.exists():
        raise FileNotFoundError(f"Payload file not found: {payload_path}")
    if not payload_path.is_file():
        raise ValueError(f"Payload path is not a regular file: {payload_path}")

    payload_data = payload_path.read_bytes()
    if not payload_data:
        raise ValueError(f"Payload file is empty: {payload_path}")
    return payload_data, len(payload_data), payload_path


def _payload_source_label(spec_data: dict) -> str:
    payload_file = spec_data.get("payload_file")
    if payload_file is None:
        return "deterministic-generated"
    payload_path = Path(payload_file)
    if not payload_path.is_absolute():
        payload_path = (REPO_ROOT / payload_path).resolve()
    try:
        return str(payload_path.relative_to(REPO_ROOT))
    except ValueError:
        return str(payload_path)


def build_images() -> dict[str, dict]:
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(f"Manifest not found: {MANIFEST_PATH}")

    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    updates = {}

    for package in manifest["packages"]:
        ecu_name = package["ecu_name"]
        spec_data = PACKAGE_SPECS.get(ecu_name)
        if spec_data is None:
            raise ValueError(f"No firmware spec defined for {ecu_name}")

        image_path = RELEASE_DIR / package["file"]
        payload_data, payload_size, payload_path = _load_payload_bytes(spec_data)
        if payload_path is not None and payload_path.resolve() == image_path.resolve():
            if looks_like_firmware_image(payload_data):
                raise ValueError(
                    f"Payload file for {ecu_name} already looks like a packaged OTA image: {payload_path}. "
                    "Use a raw source binary as payload input, or move the source file to a different path."
                )

        spec = FirmwareImageSpec(
            ecu_name=ecu_name,
            ecu_id=spec_data["ecu_id"],
            part_number=spec_data["part_number"],
            current_version=package["current_version"],
            target_version=package["target_version"],
            build_date="20260715",
            build_number=24071501,
            flash_address=spec_data["flash_address"],
            payload_size=payload_size,
            image_format="RAW",
            payload_data=payload_data,
        )

        image = build_firmware_image(spec)
        image_path.write_bytes(image)

        metadata = parse_firmware_image(image)
        if metadata.ecu_name != ecu_name:
            raise ValueError(
                f"Packaged image ECU mismatch for {ecu_name}: header={metadata.ecu_name}"
            )
        if metadata.target_version != package["target_version"]:
            raise ValueError(
                f"Packaged image target version mismatch for {ecu_name}: "
                f"header={metadata.target_version} manifest={package['target_version']}"
            )
        if metadata.flash_address != spec_data["flash_address"]:
            raise ValueError(
                f"Packaged image flash address mismatch for {ecu_name}: "
                f"header=0x{metadata.flash_address:08X} spec=0x{spec_data['flash_address']:08X}"
            )
        if metadata.part_number != spec_data["part_number"]:
            raise ValueError(
                f"Packaged image part number mismatch for {ecu_name}: "
                f"header={metadata.part_number} spec={spec_data['part_number']}"
            )

        updates[ecu_name] = {
            "ecu_id": metadata.ecu_id,
            "part_number": metadata.part_number,
            "image_size": metadata.image_size,
            "payload_size": metadata.payload_size,
            "build_number": metadata.build_number,
            "build_date": metadata.build_date,
            "flash_address": f"0x{metadata.flash_address:08X}",
            "payload_sha256": metadata.payload_sha256,
            "crc32": f"0x{metadata.crc32:08X}",
            "image_format": metadata.image_format,
            "payload_source": _payload_source_label(spec_data),
            "sha256": hashlib.sha256(image).hexdigest(),
        }

        package.update(updates[ecu_name])

    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=4)
        f.write("\n")

    refresh_demo_trust_metadata(RELEASE_DIR)

    return updates


def main() -> None:
    updates = build_images()

    print("Generated firmware images:")
    for ecu_name, meta in updates.items():
        print(
            f"- {ecu_name}: "
            f"size={meta['image_size']} "
            f"payload={meta['payload_size']} "
            f"sha256={meta['sha256'][:16]}..."
        )


if __name__ == "__main__":
    main()
