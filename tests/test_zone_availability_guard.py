import os
import unittest
from unittest.mock import patch

from tcu.zone_availability_guard import ZoneAvailabilityGuard


class TestZoneAvailabilityGuard(unittest.TestCase):
    def setUp(self):
        self.previous = {
            "OTA_USE_ZONAL_CONTROLLERS": os.environ.get("OTA_USE_ZONAL_CONTROLLERS"),
            "OTA_VCAN_ZONE_GUARD_ENABLED": os.environ.get("OTA_VCAN_ZONE_GUARD_ENABLED"),
        }
        os.environ["OTA_USE_ZONAL_CONTROLLERS"] = "1"
        os.environ["OTA_VCAN_ZONE_GUARD_ENABLED"] = "1"

    def tearDown(self):
        for key, value in self.previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_allows_online_ecu(self):
        guard = ZoneAvailabilityGuard()
        with patch.object(
            guard,
            "ecu_availability",
            return_value={"state": "ONLINE"},
        ):
            guard.require_ecu_online("Cluster ECU")

    def test_rejects_offline_ecu(self):
        guard = ZoneAvailabilityGuard()
        with patch.object(
            guard,
            "ecu_availability",
            return_value={
                "state": "OFFLINE",
                "reason": "ZONE_OFFLINE",
            },
        ):
            with self.assertRaisesRegex(RuntimeError, "Zone heartbeat gate rejected"):
                guard.require_ecu_online("Cluster ECU")

    def test_disabled_when_zonal_controllers_disabled(self):
        os.environ["OTA_USE_ZONAL_CONTROLLERS"] = "0"
        self.assertFalse(ZoneAvailabilityGuard.enabled())


if __name__ == "__main__":
    unittest.main()
