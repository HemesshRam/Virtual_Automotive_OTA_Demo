import unittest
from unittest.mock import patch

from tcu.models.ecu import ECU
from tcu.models.vehicle import Vehicle
from tcu.update_scheduler import UpdateScheduler


class UpdateSchedulerStatusTest(unittest.TestCase):

    def test_scheduler_stops_at_pending_commit(self):
        scheduler = UpdateScheduler("firmware/releases/2.0.0", "VCAN")

        ecu = ECU(
            ecu_id=0x201,
            ecu_name="Gateway ECU",
            current_version="1.0.0",
            transport="VCAN",
        )
        package = {
            "ecu_name": "Gateway ECU",
            "file": "gateway_v2.bin",
            "target_version": "2.0.0",
        }
        eligible_updates = [{"ecu": ecu, "package": package}]

        with patch.object(
            scheduler.firmware_manager,
            "verify_repository",
            return_value=True,
        ), patch.object(
            scheduler.firmware_manager,
            "build_inventory",
            return_value={},
        ), patch.object(
            scheduler.firmware_manager,
            "campaign_id",
            return_value="OTA_2026_001",
        ), patch.object(
            scheduler.transport,
            "send_firmware",
            return_value=True,
        ), patch(
            "tcu.update_scheduler.reporter.report"
        ) as report_mock, patch.object(
            scheduler.transport,
            "shutdown",
            return_value=None,
        ):
            success = scheduler.execute(eligible_updates, ["Gateway ECU"])

        self.assertTrue(success)
        self.assertEqual(ecu.current_version, "1.0.0")
        self.assertEqual(ecu.update_status, "PENDING_COMMIT")
        self.assertEqual(report_mock.call_args_list[-1].args[3], "2.0.0")
        self.assertEqual(report_mock.call_args_list[-1].args[1], "PENDING_COMMIT")

    def test_discovered_dependency_without_update_is_satisfied(self):
        scheduler = UpdateScheduler("firmware/releases/2.0.0", "VCAN")

        gateway = ECU(
            ecu_id=0x201,
            ecu_name="Gateway ECU",
            current_version="2.0.0",
            transport="VCAN",
        )
        bcm = ECU(
            ecu_id=0x202,
            ecu_name="BCM ECU",
            current_version="1.0.0",
            transport="VCAN",
            dependencies=["Gateway ECU"],
        )
        vehicle = Vehicle()
        vehicle.add_ecu(gateway)
        vehicle.add_ecu(bcm)

        package = {
            "ecu_name": "BCM ECU",
            "file": "bcm_v2.bin",
            "target_version": "2.0.0",
        }
        eligible_updates = [{"ecu": bcm, "package": package}]

        with patch.object(
            scheduler.firmware_manager,
            "verify_repository",
            return_value=True,
        ), patch.object(
            scheduler.firmware_manager,
            "build_inventory",
            return_value={},
        ), patch.object(
            scheduler.firmware_manager,
            "campaign_id",
            return_value="OTA_2026_001",
        ), patch.object(
            scheduler.transport,
            "send_firmware",
            return_value=True,
        ), patch(
            "tcu.update_scheduler.reporter.report"
        ), patch.object(
            scheduler.transport,
            "shutdown",
            return_value=None,
        ):
            success = scheduler.execute(
                eligible_updates,
                ["Gateway ECU", "BCM ECU"],
                vehicle=vehicle,
            )

        self.assertTrue(success)
        self.assertEqual(bcm.update_status, "PENDING_COMMIT")


if __name__ == "__main__":
    unittest.main()
