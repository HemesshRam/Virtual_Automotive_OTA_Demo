import unittest
from unittest.mock import patch

from tcu.firmware_compatibility import FirmwareCompatibilityValidator
from tcu.models.ecu import ECU
from tcu.models.vehicle import Vehicle


class VersionPolicyTest(unittest.TestCase):

    def _campaign(self):
        class Campaign:
            release_version = "2.0.0"
            transport = "VCAN"
            approved_targets = []
            skipped_optional_targets = []

        return Campaign()

    @patch("tcu.firmware_compatibility.FirmwareManifest")
    def test_same_version_is_already_current(self, manifest_cls):
        manifest_cls.return_value.load.return_value = self._manifest("2.0.0")
        vehicle = Vehicle()
        vehicle.add_ecu(ECU(0x201, "Gateway ECU", "2.0.0", "VCAN"))

        eligible = FirmwareCompatibilityValidator().validate(vehicle, self._campaign())

        self.assertEqual(eligible, [])

    @patch("tcu.firmware_compatibility.FirmwareManifest")
    def test_higher_version_rejects_downgrade(self, manifest_cls):
        manifest_cls.return_value.load.return_value = self._manifest("2.0.0")
        vehicle = Vehicle()
        vehicle.add_ecu(ECU(0x201, "Gateway ECU", "3.0.0", "VCAN"))

        eligible = FirmwareCompatibilityValidator().validate(vehicle, self._campaign())

        self.assertEqual(eligible, [])

    @staticmethod
    def _manifest(target_version):
        return {
            "release_version": "2.0.0",
            "packages": [
                {
                    "ecu_name": "Gateway ECU",
                    "file": "gateway_v2.bin",
                    "hardware_variant": "GENERIC",
                    "minimum_bootloader": "1.0.0",
                    "target_version": target_version,
                    "transport": "VCAN",
                    "transport_support": ["VCAN"],
                }
            ],
            "_trusted_targets": {
                "gateway_v2.bin": {
                    "length": 4256,
                    "sha256": "",
                    "custom": {
                        "ecu_name": "Gateway ECU",
                        "hardware_variant": "GENERIC",
                        "target_version": target_version,
                    },
                }
            },
        }


if __name__ == "__main__":
    unittest.main()
