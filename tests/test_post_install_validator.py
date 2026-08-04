import unittest
from unittest.mock import patch

from tcu.models.campaign import Campaign, CampaignTarget
from tcu.models.ecu import ECU
from tcu.models.vehicle import Vehicle
from tcu.post_install_validator import PostInstallValidator


class PostInstallValidatorTest(unittest.TestCase):

    def _campaign(self):
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
        campaign.approved_targets = ["Gateway ECU", "BCM ECU"]
        campaign.skipped_optional_targets = [("Cluster ECU", "ECU_NOT_FOUND")]
        return campaign

    def test_skipped_offline_target_is_not_required_for_final_validation(self):
        vehicle = Vehicle()
        vehicle.add_ecu(
            ECU(
                ecu_id=0x201,
                ecu_name="Gateway ECU",
                current_version="2.0.0",
                transport="DOIP",
            )
        )
        vehicle.add_ecu(
            ECU(
                ecu_id=0x202,
                ecu_name="BCM ECU",
                current_version="2.0.0",
                transport="DOIP",
            )
        )

        validator = PostInstallValidator()
        validator.INITIAL_WAIT_SECONDS = 0

        with patch.object(
            validator,
            "_wait_for_expected_versions",
            return_value=vehicle,
        ), patch("tcu.post_install_validator.VersionManager") as version_manager, patch(
            "tcu.post_install_validator.SlotManager"
        ), patch("tcu.post_install_validator.reporter.report"):
            version_manager.return_value.has_pending_commit.return_value = False
            self.assertTrue(validator.validate(self._campaign(), transport="DOIP"))

    def test_skipped_but_discovered_target_is_reported_not_compared_to_unknown(self):
        vehicle = Vehicle()
        vehicle.add_ecu(
            ECU(
                ecu_id=0x201,
                ecu_name="Gateway ECU",
                current_version="2.0.0",
                transport="DOIP",
            )
        )
        vehicle.add_ecu(
            ECU(
                ecu_id=0x202,
                ecu_name="BCM ECU",
                current_version="2.0.0",
                transport="DOIP",
            )
        )
        vehicle.add_ecu(
            ECU(
                ecu_id=0x203,
                ecu_name="Cluster ECU",
                current_version="1.0.0",
                transport="DOIP",
            )
        )

        validator = PostInstallValidator()
        validator.INITIAL_WAIT_SECONDS = 0

        with patch.object(
            validator,
            "_wait_for_expected_versions",
            return_value=vehicle,
        ), patch("tcu.post_install_validator.VersionManager") as version_manager, patch(
            "tcu.post_install_validator.SlotManager"
        ), patch("tcu.post_install_validator.reporter.report"):
            version_manager.return_value.has_pending_commit.return_value = False
            self.assertTrue(validator.validate(self._campaign(), transport="DOIP"))


if __name__ == "__main__":
    unittest.main()
