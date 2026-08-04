import unittest
from unittest.mock import patch

from tcu.models.ecu import ECU
from tcu.update_scheduler import UpdateScheduler


class DynamicDependencyPolicyTest(unittest.TestCase):

    def _scheduler(self):
        scheduler = UpdateScheduler("firmware/releases/2.0.0", "VCAN")
        patches = [
            patch.object(scheduler.firmware_manager, "verify_repository", return_value=True),
            patch.object(scheduler.firmware_manager, "build_inventory", return_value={}),
            patch.object(scheduler.firmware_manager, "campaign_id", return_value="OTA_2026_001"),
            patch.object(scheduler.transport, "shutdown", return_value=None),
            patch("tcu.update_scheduler.reporter.report"),
        ]
        return scheduler, patches

    @staticmethod
    def _entry(ecu_name, ecu_id, dependencies=None):
        return {
            "ecu": ECU(
                ecu_id=ecu_id,
                ecu_name=ecu_name,
                current_version="1.0.0",
                transport="VCAN",
                dependencies=dependencies or [],
            ),
            "package": {
                "ecu_name": ecu_name,
                "file": "gateway_v2.bin",
                "target_version": "2.0.0",
            },
        }

    def test_optional_cluster_skips_when_bcm_dependency_missing(self):
        scheduler, patches = self._scheduler()
        cluster = self._entry("Cluster ECU", 0x203, ["BCM ECU"])

        with patches[0], patches[1], patches[2], patches[3], patches[4] as report_mock:
            success = scheduler.execute([cluster], ["Cluster ECU"])

        self.assertTrue(success)
        skipped_reports = [
            call for call in report_mock.call_args_list
            if call.args[1] == "SKIPPED"
        ]
        self.assertTrue(skipped_reports)
        self.assertEqual(skipped_reports[-1].kwargs["error"], "DEPENDENCY_UNAVAILABLE")

    def test_critical_bcm_missing_gateway_dependency_aborts_campaign(self):
        scheduler, patches = self._scheduler()
        bcm = self._entry("BCM ECU", 0x202, ["Gateway ECU"])

        with patches[0], patches[1], patches[2], patches[3], patches[4] as report_mock:
            success = scheduler.execute([bcm], ["BCM ECU"])

        self.assertFalse(success)
        skipped_reports = [
            call for call in report_mock.call_args_list
            if call.args[1] == "SKIPPED"
        ]
        self.assertTrue(skipped_reports)
        self.assertEqual(skipped_reports[-1].kwargs["error"], "DEPENDENCY_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
