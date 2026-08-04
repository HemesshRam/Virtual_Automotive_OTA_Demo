import hashlib
import os
from pathlib import Path

from firmware.image_format import parse_firmware_image
from tcu.firmware_manifest import FirmwareManifest
from common.utils import normalize_transport
from common.utils import version_lt
from common.utils import version_eq
from common.utils import version_gte


class FirmwareCompatibilityValidator:
    """
    Validates firmware packages against discovered ECUs.

    Returns a list of eligible updates, each containing
    the ECU and its matched firmware package.
    """

    def validate(
        self,
        vehicle,
        campaign,
        require_downloaded_files: bool = True,
        target_names=None,
    ):

        manifest_path = Path(
            "firmware"
        ) / "releases" / str(campaign.release_version) / "manifest.json"

        manifest = FirmwareManifest(manifest_path).load(verify_trust=True)
        trusted_targets = manifest.get("_trusted_targets", {})

        eligible_updates = []
        approved_targets = set(getattr(campaign, "approved_targets", []))
        skipped_targets = {
            ecu_name: reason
            for ecu_name, reason in getattr(campaign, "skipped_optional_targets", [])
        }

        print()
        print("=" * 60)
        if require_downloaded_files:
            print("FIRMWARE COMPATIBILITY VALIDATION")
        else:
            print("FIRMWARE ELIGIBILITY PLANNING")
        print("=" * 60)

        selected_targets = {
            str(name).strip()
            for name in (target_names or [])
            if str(name).strip()
        }

        for ecu in vehicle.get_all_ecus():

            print()
            print("-" * 60)
            print(ecu.ecu_name)

            if selected_targets and ecu.ecu_name not in selected_targets:
                print("✗ Not Selected For This OTA Run")
                continue

            if approved_targets and ecu.ecu_name not in approved_targets:
                reason = skipped_targets.get(ecu.ecu_name, "NOT_APPROVED_BY_CAMPAIGN")
                print(f"✗ Skipped By Campaign Policy ({reason})")
                continue

            package = None

            # Find matching firmware package
            for p in manifest["packages"]:
                if p["ecu_name"] == ecu.ecu_name:
                    package = p
                    break

            if package is None:
                print("✗ No firmware package found")
                continue

            print("✓ Firmware Package Found")

            firmware_path = os.path.join(
                "firmware",
                "releases",
                manifest["release_version"],
                package["file"],
            )

            trusted_target = trusted_targets.get(package["file"])
            if trusted_target is None:
                print("✗ Trusted Metadata Missing")
                continue

            if trusted_target["custom"].get("ecu_name") != ecu.ecu_name:
                print("✗ Trusted ECU Binding Mismatch")
                continue

            if trusted_target["custom"].get("hardware_variant") != package["hardware_variant"]:
                print("✗ Trusted Hardware Binding Mismatch")
                continue

            if trusted_target["custom"].get("target_version") != package["target_version"]:
                print("✗ Trusted Target Version Mismatch")
                continue

            manifest_sha256 = package.get("sha256")
            if manifest_sha256 and trusted_target["sha256"] != manifest_sha256:
                print("✗ Manifest and Trusted Hash Mismatch")
                continue

            print("✓ Trusted Metadata Verified")

            actual_size = trusted_target["length"]

            if require_downloaded_files:
                if not os.path.exists(firmware_path):
                    print("✗ Firmware file missing")
                    continue

                print("✓ Firmware File Exists")

                firmware_bytes = Path(firmware_path).read_bytes()

                try:
                    image_metadata = parse_firmware_image(firmware_bytes)
                except Exception as exc:
                    print(f"✗ Firmware Image Parse Failed ({exc})")
                    continue

                if image_metadata.ecu_name != package["ecu_name"]:
                    print("✗ Firmware Header ECU Mismatch")
                    continue

                if image_metadata.target_version != package["target_version"]:
                    print("✗ Firmware Header Target Version Mismatch")
                    continue

                package_flash_address = package.get("flash_address")
                if package_flash_address is not None:
                    expected_flash_address = int(str(package_flash_address), 16)
                    if image_metadata.flash_address != expected_flash_address:
                        print("✗ Firmware Header Flash Address Mismatch")
                        continue

                package_part_number = package.get("part_number")
                if package_part_number and image_metadata.part_number != package_part_number:
                    print("✗ Firmware Header Part Number Mismatch")
                    continue

                print("✓ Firmware Header Metadata Verified")

                actual_size = len(firmware_bytes)
                if trusted_target["length"] != actual_size:
                    print("✗ Trusted Length Mismatch")
                    continue

                actual_sha256 = hashlib.sha256(firmware_bytes).hexdigest()
                if actual_sha256 != trusted_target["sha256"]:
                    print("✗ Downloaded Artifact Hash Mismatch")
                    continue

                print("✓ Downloaded Artifact Hash Verified")
            else:
                print("✓ Artifact Download Deferred Until Execution Plan")

            if ecu.hardware_variant != package["hardware_variant"]:
                print("✗ Hardware Variant Mismatch")
                continue

            print("✓ Hardware Variant Compatible")

            if version_lt(ecu.bootloader_version, package["minimum_bootloader"]):
                print("✗ Bootloader Too Old")
                continue

            print("✓ Bootloader Compatible")

            supported_transports = package.get("transport_support")
            if supported_transports is None:
                supported_transports = [package["transport"]]

            supported_transports = {
                normalize_transport(value) for value in supported_transports
            }

            selected_transport = normalize_transport(campaign.transport)

            if selected_transport not in supported_transports:
                print("✗ Transport Not Supported")
                continue

            print("✓ Transport Compatible")

            if version_eq(ecu.current_version, package["target_version"]):
                print("✗ ECU Already At Target Version")
                print("→ REJECT (target is already satisfied)")
                continue

            if version_gte(ecu.current_version, package["target_version"]):
                print("✗ Downgrade Rejected")
                print("→ REJECT (target is not newer)")
                continue

            print(f"✓ Upgrade Available : {ecu.current_version} -> {package['target_version']}")

            size = actual_size

            if size <= 0:
                print("✗ Invalid Firmware Size")
                continue

            print(f"✓ Firmware Size : {size} bytes")

            eligible_updates.append(
                {
                    "ecu": ecu,
                    "package": package,
                    "manifest": manifest,
                    "firmware_path": firmware_path,
                    "signature_status": "VERIFIED",
                    "trusted_target": trusted_target,
                    "size": size,
                }
            )

            print("RESULT : ELIGIBLE")

        print()
        print("=" * 60)
        print(f"Eligible ECUs : {len(eligible_updates)}")
        print("=" * 60)

        return eligible_updates
