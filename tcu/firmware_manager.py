import hashlib
import json
from pathlib import Path

from firmware.image_format import parse_firmware_image


class FirmwareManager:
    """
    Production OTA Firmware Manager

    Responsibilities
    ----------------
    - Load OTA manifest
    - Validate firmware package
    - Calculate SHA-256 checksums
    - Provide firmware metadata for ECUs
    """

    def __init__(self, release_directory: str):

        self.release_directory = Path(release_directory)

        self.manifest_path = self.release_directory / "manifest.json"

        if not self.manifest_path.exists():
            raise FileNotFoundError(
                f"Manifest not found : {self.manifest_path}"
            )

        with open(self.manifest_path, "r", encoding="utf-8") as file:
            self.manifest = json.load(file)

        self.packages = self.manifest["packages"]

    # --------------------------------------------------

    def campaign_id(self):

        return self.manifest["campaign_id"]

    # --------------------------------------------------

    def release_version(self):

        return self.manifest.get("release_version") or self.manifest.get("release")

    # --------------------------------------------------

    def transport_priority(self):

        return self.manifest["transport_priority"]

    # --------------------------------------------------

    def transport_fallback(self):

        return self.manifest["transport_fallback"]

    # --------------------------------------------------

    def _selected_packages(self, target_names=None):

        if not target_names:
            return list(self.packages)

        selected = {
            str(name).strip()
            for name in target_names
            if str(name).strip()
        }

        return [
            package for package in self.packages
            if package["ecu_name"] in selected
        ]

    # --------------------------------------------------

    def verify_repository(self, target_names=None):

        print("\n========== VERIFYING OTA REPOSITORY ==========\n")

        valid = True

        for package in self._selected_packages(target_names):

            firmware = self.release_directory / package["file"]

            if firmware.exists():

                print(f"[OK] {package['file']}")

            else:

                print(f"[MISSING] {package['file']}")
                valid = False

        return valid

    # --------------------------------------------------

    def sha256(self, firmware_path: Path):

        digest = hashlib.sha256()

        with open(firmware_path, "rb") as file:

            while True:

                chunk = file.read(4096)

                if not chunk:
                    break

                digest.update(chunk)

        return digest.hexdigest()

    # --------------------------------------------------

    def build_inventory(self, target_names=None):

        """
        Computes firmware metadata.

        Returns

        {
            ecu_name :
            {
                ...
            }
        }
        """

        inventory = {}

        print("\n========== FIRMWARE INVENTORY ==========\n")

        for package in self._selected_packages(target_names):

            firmware = self.release_directory / package["file"]

            checksum = self.sha256(firmware)

            size = firmware.stat().st_size

            image_metadata = None
            try:
                image_metadata = parse_firmware_image(firmware.read_bytes())
            except Exception:
                image_metadata = None

            inventory[package["ecu_name"]] = {

                "ecu_name": package["ecu_name"],

                "file": str(firmware),

                "target_version": package["target_version"],

                "checksum": checksum,

                "size": size,
                "image_metadata": image_metadata,

            }

            print(package["ecu_name"])
            print(f"   Firmware : {package['file']}")
            print(f"   Size     : {size} bytes")
            print(f"   SHA256   : {checksum[:16]}...")
            if image_metadata is not None:
                print(f"   Format   : {image_metadata.image_format}")
                print(f"   Build    : {image_metadata.build_number}")
                print(
                    f"   Payload  : {image_metadata.payload_size} bytes"
                )
                print(
                    f"   Flash    : 0x{image_metadata.flash_address:08X}"
                )
            print()

        return inventory

    # --------------------------------------------------

    def get_package(self, ecu_name):
        for package in self.packages:
            if package["ecu_name"] == ecu_name:
                return package

        raise ValueError(
            f"Firmware package not found for ECU : {ecu_name}"
        )
