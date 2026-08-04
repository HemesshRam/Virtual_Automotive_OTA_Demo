import os
import time
import unittest
from unittest.mock import patch

from zones.base.zone_controller import ZoneController


class TestZoneHeartbeatPolicy(unittest.TestCase):
    def setUp(self):
        self.previous_env = {
            key: os.environ.get(key)
            for key in [
                "OTA_ZONE_HEARTBEAT_MONITOR_ENABLED",
                "OTA_ZONE_HEARTBEAT_TIMEOUT_SECONDS",
                "OTA_ZONE_HEARTBEAT_GRACE_SECONDS",
            ]
        }
        os.environ["OTA_ZONE_HEARTBEAT_MONITOR_ENABLED"] = "1"
        os.environ["OTA_ZONE_HEARTBEAT_TIMEOUT_SECONDS"] = "3.0"
        os.environ["OTA_ZONE_HEARTBEAT_GRACE_SECONDS"] = "5.0"

    def tearDown(self):
        for key, value in self.previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_target_is_starting_during_grace_period(self):
        controller = self._controller(started_seconds_ago=1.0)

        availability = controller._ecu_availability(0x1003)

        self.assertEqual("STARTING", availability["state"])

    def test_target_is_offline_after_heartbeat_timeout(self):
        controller = self._controller(started_seconds_ago=10.0)

        availability = controller._ecu_availability(0x1003)

        self.assertEqual("OFFLINE", availability["state"])

    def test_target_is_online_when_heartbeat_is_fresh(self):
        controller = self._controller(started_seconds_ago=10.0)
        controller.heartbeat_last_seen[0x203] = time.monotonic()

        availability = controller._ecu_availability(0x1003)

        self.assertEqual("ONLINE", availability["state"])

    def test_forwarding_rejects_target_after_missing_heartbeat(self):
        controller = self._controller(started_seconds_ago=10.0)
        controller.metrics = {"rejected": 0, "last_error": ""}

        with patch.object(controller, "_record_rejection") as record:
            with self.assertRaisesRegex(RuntimeError, "ECU_HEARTBEAT_TIMEOUT"):
                controller._enforce_target_online(0x1003)

        record.assert_called_once_with("ECU_HEARTBEAT_TIMEOUT:Cluster ECU")

    @staticmethod
    def _controller(started_seconds_ago: float):
        controller = ZoneController.__new__(ZoneController)
        controller.zone_id = "cluster_zone"
        controller.config = {"default_health": "AUTO"}
        controller.started_at = time.monotonic() - started_seconds_ago
        controller.heartbeat_last_seen = {}
        controller.ecus = {
            0x1003: {
                "ecu_name": "Cluster ECU",
                "can_id": 0x203,
            }
        }
        return controller


if __name__ == "__main__":
    unittest.main()
