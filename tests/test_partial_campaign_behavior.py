import unittest
from unittest.mock import patch

from tcu.models.campaign import Campaign, CampaignTarget
from tcu.models.ecu import ECU
from tcu.models.vehicle import Vehicle
from tcu.compatibility.validator import CompatibilityValidator
from tcu.firmware_compatibility import FirmwareCompatibilityValidator
from tcu.update_scheduler import UpdateScheduler


class PartialCampaignBehaviorTest(unittest.TestCase):

    def test_optional_incompatible_target_does_not_reject_campaign(self):
        vehicle = Vehicle()
        vehicle.add_ecu(
            ECU(
                ecu_id=0x201,
                ecu_name="Gateway ECU",
                current_version="1.0.0",
                transport="VCAN",
            )
        )

        campaign = Campaign(
            campaign_id="OTA_TEST",
            vehicle_model="Virtual Vehicle",
            release_version="2.0.0",
            priority="HIGH",
            transport="VCAN",
            rollback_enabled=True,
            created_by="test",
            targets=[
                CampaignTarget(
                    ecu_name="Gateway ECU",
                    target_version="2.0.0",
                    minimum_supported_version="1.0.0",
                    hardware_variant="GENERIC",
                    minimum_bootloader="1.0.0",
                    mandatory=True,
                    priority=1,
                    requires_reboot=True,
                ),
                CampaignTarget(
                    ecu_name="BCM ECU",
                    target_version="2.0.0",
                    minimum_supported_version="1.0.0",
                    hardware_variant="GENERIC",
                    minimum_bootloader="1.0.0",
                    mandatory=False,
                    priority=2,
                    requires_reboot=True,
                ),
            ],
        )

        self.assertTrue(CompatibilityValidator().validate(vehicle, campaign))

    def test_topology_optional_cluster_missing_is_skipped_even_if_campaign_mandatory(self):
        vehicle = Vehicle()
        vehicle.add_ecu(
            ECU(
                ecu_id=0x201,
                ecu_name="Gateway ECU",
                current_version="1.0.0",
                transport="DOIP",
            )
        )
        vehicle.add_ecu(
            ECU(
                ecu_id=0x202,
                ecu_name="BCM ECU",
                current_version="1.0.0",
                transport="DOIP",
            )
        )

        campaign = Campaign(
            campaign_id="OTA_TEST",
            vehicle_model="Virtual Vehicle",
            release_version="2.0.0",
            priority="HIGH",
            transport="DOIP",
            rollback_enabled=True,
            created_by="test",
            targets=[
                CampaignTarget(
                    ecu_name="Gateway ECU",
                    target_version="2.0.0",
                    minimum_supported_version="1.0.0",
                    hardware_variant="GENERIC",
                    minimum_bootloader="1.0.0",
                    mandatory=True,
                    priority=1,
                    requires_reboot=True,
                ),
                CampaignTarget(
                    ecu_name="BCM ECU",
                    target_version="2.0.0",
                    minimum_supported_version="1.0.0",
                    hardware_variant="GENERIC",
                    minimum_bootloader="1.0.0",
                    mandatory=True,
                    priority=2,
                    requires_reboot=True,
                ),
                CampaignTarget(
                    ecu_name="Cluster ECU",
                    target_version="2.0.0",
                    minimum_supported_version="1.0.0",
                    hardware_variant="GENERIC",
                    minimum_bootloader="1.0.0",
                    mandatory=True,
                    priority=3,
                    requires_reboot=True,
                ),
            ],
        )

        self.assertTrue(CompatibilityValidator().validate(vehicle, campaign))
        self.assertIn(("Cluster ECU", "ECU_NOT_FOUND"), campaign.skipped_optional_targets)
        self.assertEqual(campaign.approved_targets, ["Gateway ECU", "BCM ECU"])

    def test_topology_critical_bcm_missing_still_rejects_campaign(self):
        vehicle = Vehicle()
        vehicle.add_ecu(
            ECU(
                ecu_id=0x201,
                ecu_name="Gateway ECU",
                current_version="1.0.0",
                transport="DOIP",
            )
        )

        campaign = Campaign(
            campaign_id="OTA_TEST",
            vehicle_model="Virtual Vehicle",
            release_version="2.0.0",
            priority="HIGH",
            transport="DOIP",
            rollback_enabled=True,
            created_by="test",
            targets=[
                CampaignTarget(
                    ecu_name="Gateway ECU",
                    target_version="2.0.0",
                    minimum_supported_version="1.0.0",
                    hardware_variant="GENERIC",
                    minimum_bootloader="1.0.0",
                    mandatory=True,
                    priority=1,
                    requires_reboot=True,
                ),
                CampaignTarget(
                    ecu_name="BCM ECU",
                    target_version="2.0.0",
                    minimum_supported_version="1.0.0",
                    hardware_variant="GENERIC",
                    minimum_bootloader="1.0.0",
                    mandatory=True,
                    priority=2,
                    requires_reboot=True,
                ),
            ],
        )

        self.assertFalse(CompatibilityValidator().validate(vehicle, campaign))

    def test_scheduler_skips_dependent_ecu_after_failure(self):
        scheduler = UpdateScheduler("firmware/releases/2.0.0", "VCAN")

        gateway = ECU(
            ecu_id=0x201,
            ecu_name="Gateway ECU",
            current_version="1.0.0",
            transport="VCAN",
            dependencies=[],
        )
        bcm = ECU(
            ecu_id=0x202,
            ecu_name="BCM ECU",
            current_version="1.0.0",
            transport="VCAN",
            dependencies=["Gateway ECU"],
        )

        eligible_updates = [
            {
                "ecu": gateway,
                "package": {
                    "ecu_name": "Gateway ECU",
                    "file": "gateway_v2.bin",
                    "target_version": "2.0.0",
                },
            },
            {
                "ecu": bcm,
                "package": {
                    "ecu_name": "BCM ECU",
                    "file": "bcm_v2.bin",
                    "target_version": "2.0.0",
                },
            },
        ]

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
            side_effect=[False, False],
        ), patch(
            "tcu.update_scheduler.reporter.report"
        ) as report_mock, patch.object(
            scheduler.transport,
            "shutdown",
            return_value=None,
        ):
            success = scheduler.execute(eligible_updates, ["Gateway ECU", "BCM ECU"])

        self.assertFalse(success)
        self.assertTrue(
            any(call.args[1] == "SKIPPED" for call in report_mock.call_args_list)
        )

    def test_firmware_compatibility_honors_campaign_approved_targets(self):
        vehicle = Vehicle()
        vehicle.add_ecu(
            ECU(
                ecu_id=0x201,
                ecu_name="Gateway ECU",
                current_version="1.0.0",
                transport="VCAN",
            )
        )
        vehicle.add_ecu(
            ECU(
                ecu_id=0x203,
                ecu_name="Cluster ECU",
                current_version="1.0.0",
                transport="VCAN",
            )
        )

        campaign = Campaign(
            campaign_id="OTA_TEST",
            vehicle_model="Virtual Vehicle",
            release_version="2.0.0",
            priority="HIGH",
            transport="VCAN",
            rollback_enabled=True,
            created_by="test",
            targets=[
                CampaignTarget(
                    ecu_name="Gateway ECU",
                    target_version="2.0.0",
                    minimum_supported_version="1.0.0",
                    hardware_variant="GENERIC",
                    minimum_bootloader="1.0.0",
                    mandatory=True,
                    priority=1,
                    requires_reboot=True,
                ),
                CampaignTarget(
                    ecu_name="Cluster ECU",
                    target_version="2.0.0",
                    minimum_supported_version="1.0.0",
                    hardware_variant="GENERIC",
                    minimum_bootloader="9.9.0",
                    mandatory=False,
                    priority=3,
                    requires_reboot=True,
                ),
            ],
        )

        self.assertTrue(CompatibilityValidator().validate(vehicle, campaign))
        eligible = FirmwareCompatibilityValidator().validate(vehicle, campaign)
        self.assertEqual([entry["ecu"].ecu_name for entry in eligible], ["Gateway ECU"])


if __name__ == "__main__":
    unittest.main()
