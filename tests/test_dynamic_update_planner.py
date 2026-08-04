import unittest

from tcu.dynamic_update_planner import DynamicUpdatePlanner
from tcu.models.campaign import Campaign, CampaignTarget
from tcu.models.ecu import ECU
from tcu.models.vehicle import Vehicle


class DynamicUpdatePlannerTest(unittest.TestCase):
    def test_optional_skipped_target_removed_from_execution_order(self):
        vehicle = Vehicle()
        gateway = self._ecu(0x201, "Gateway ECU", "1.0.0")
        bcm = self._ecu(0x202, "BCM ECU", "1.0.0")
        cluster = self._ecu(0x203, "Cluster ECU", "1.0.0")
        vehicle.add_ecu(gateway)
        vehicle.add_ecu(bcm)
        vehicle.add_ecu(cluster)

        campaign = self._campaign()
        campaign.approved_targets = ["Gateway ECU", "BCM ECU"]
        campaign.skipped_optional_targets = [("Cluster ECU", "INCOMPATIBLE")]
        eligible = [
            {"ecu": gateway, "package": {"target_version": "2.0.0"}},
            {"ecu": bcm, "package": {"target_version": "2.0.0"}},
        ]

        plan = DynamicUpdatePlanner().plan(vehicle, campaign, eligible)

        self.assertTrue(plan.executable)
        self.assertEqual(["Gateway ECU", "BCM ECU"], plan.update_order)
        self.assertEqual(
            "SKIPPED_OPTIONAL:INCOMPATIBLE",
            plan.classifications["Cluster ECU"],
        )

    def test_campaign_override_changes_order(self):
        vehicle = Vehicle()
        gateway = self._ecu(0x201, "Gateway ECU", "1.0.0")
        bcm = self._ecu(0x202, "BCM ECU", "1.0.0")
        cluster = self._ecu(0x203, "Cluster ECU", "1.0.0")
        vehicle.add_ecu(gateway)
        vehicle.add_ecu(bcm)
        vehicle.add_ecu(cluster)

        campaign = self._campaign()
        campaign.dependency_overrides = {
            "Gateway ECU": ["BCM ECU"],
            "BCM ECU": [],
            "Cluster ECU": ["Gateway ECU"],
        }
        eligible = [
            {"ecu": gateway, "package": {"target_version": "2.0.0"}},
            {"ecu": bcm, "package": {"target_version": "2.0.0"}},
            {"ecu": cluster, "package": {"target_version": "2.0.0"}},
        ]

        plan = DynamicUpdatePlanner().plan(vehicle, campaign, eligible)

        self.assertTrue(plan.executable)
        self.assertEqual(["BCM ECU", "Gateway ECU", "Cluster ECU"], plan.update_order)
        self.assertEqual(
            "campaign_overrides",
            plan.dependency_sources["Gateway ECU"],
        )

    def test_mandatory_not_eligible_blocks_plan(self):
        vehicle = Vehicle()
        gateway = self._ecu(0x201, "Gateway ECU", "1.0.0")
        bcm = self._ecu(0x202, "BCM ECU", "1.0.0")
        cluster = self._ecu(0x203, "Cluster ECU", "1.0.0")
        vehicle.add_ecu(gateway)
        vehicle.add_ecu(bcm)
        vehicle.add_ecu(cluster)

        campaign = self._campaign()
        eligible = [
            {"ecu": bcm, "package": {"target_version": "2.0.0"}},
            {"ecu": cluster, "package": {"target_version": "2.0.0"}},
        ]

        plan = DynamicUpdatePlanner().plan(vehicle, campaign, eligible)

        self.assertFalse(plan.executable)
        self.assertEqual(
            "ABORT_REQUIRED:NOT_ELIGIBLE",
            plan.classifications["Gateway ECU"],
        )
        self.assertIn(
            "Gateway ECU is required but not eligible for update",
            plan.blocking_errors,
        )

    def test_already_updated_dependency_satisfies_dependent_ecu(self):
        vehicle = Vehicle()
        gateway = self._ecu(0x201, "Gateway ECU", "2.0.0")
        bcm = self._ecu(0x202, "BCM ECU", "1.0.0")
        cluster = self._ecu(0x203, "Cluster ECU", "1.0.0")
        vehicle.add_ecu(gateway)
        vehicle.add_ecu(bcm)
        vehicle.add_ecu(cluster)

        campaign = self._campaign()
        eligible = [
            {"ecu": bcm, "package": {"target_version": "2.0.0"}},
            {"ecu": cluster, "package": {"target_version": "2.0.0"}},
        ]

        plan = DynamicUpdatePlanner().plan(vehicle, campaign, eligible)

        self.assertTrue(plan.executable)
        self.assertEqual("ALREADY_SATISFIED", plan.classifications["Gateway ECU"])
        self.assertEqual(["BCM ECU", "Cluster ECU"], plan.update_order)

    @staticmethod
    def _ecu(ecu_id, name, version):
        return ECU(
            ecu_id=ecu_id,
            ecu_name=name,
            current_version=version,
            transport="DOIP",
            hardware_variant="GENERIC",
            bootloader_version="1.0.0",
            rollback_supported=True,
        )

    @staticmethod
    def _campaign():
        return Campaign(
            campaign_id="OTA_TEST",
            vehicle_model="Virtual Vehicle",
            release_version="2.0.0",
            priority="HIGH",
            transport="DOIP",
            rollback_enabled=True,
            created_by="test",
            targets=[
                CampaignTarget(
                    "Gateway ECU",
                    "2.0.0",
                    "1.0.0",
                    "GENERIC",
                    "1.0.0",
                    True,
                    1,
                    True,
                ),
                CampaignTarget(
                    "BCM ECU",
                    "2.0.0",
                    "1.0.0",
                    "GENERIC",
                    "1.0.0",
                    True,
                    2,
                    True,
                ),
                CampaignTarget(
                    "Cluster ECU",
                    "2.0.0",
                    "1.0.0",
                    "GENERIC",
                    "1.0.0",
                    False,
                    3,
                    True,
                ),
            ],
        )


if __name__ == "__main__":
    unittest.main()
