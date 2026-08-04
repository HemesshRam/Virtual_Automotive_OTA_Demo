import unittest

from tcu.dependency_manager import DependencyGraphBuilder, TopologicalUpdatePlanner
from tcu.models.campaign import Campaign
from tcu.models.ecu import ECU


class TopologyDependencyPlannerTest(unittest.TestCase):

    def test_builder_uses_topology_dependencies(self):
        ecus = [
            ECU(0x203, "Cluster ECU", "1.0.0", "VCAN", dependencies=[]),
            ECU(0x202, "BCM ECU", "1.0.0", "VCAN", dependencies=[]),
            ECU(0x201, "Gateway ECU", "1.0.0", "VCAN", dependencies=[]),
        ]

        graph = DependencyGraphBuilder().build(ecus)
        update_order = TopologicalUpdatePlanner().plan(
            graph,
            priority={
                "Gateway ECU": 1,
                "BCM ECU": 2,
                "Cluster ECU": 3,
            },
        )

        self.assertLess(
            update_order.index("Gateway ECU"),
            update_order.index("BCM ECU"),
        )
        self.assertLess(
            update_order.index("BCM ECU"),
            update_order.index("Cluster ECU"),
        )

    def test_campaign_dependency_override_changes_order_constraints(self):
        ecus = [
            ECU(0x203, "Cluster ECU", "1.0.0", "VCAN", dependencies=[]),
            ECU(0x202, "BCM ECU", "1.0.0", "VCAN", dependencies=[]),
            ECU(0x201, "Gateway ECU", "1.0.0", "VCAN", dependencies=[]),
        ]
        campaign = Campaign(
            campaign_id="OTA_TEST",
            vehicle_model="Virtual Vehicle",
            release_version="2.0.0",
            priority="HIGH",
            transport="VCAN",
            rollback_enabled=True,
            created_by="test",
            targets=[],
            dependency_overrides={
                "Gateway ECU": [],
                "BCM ECU": ["Gateway ECU"],
                "Cluster ECU": ["Gateway ECU"],
            },
        )

        graph = DependencyGraphBuilder().build(ecus, campaign=campaign)
        update_order = TopologicalUpdatePlanner().plan(graph)

        self.assertLess(
            update_order.index("Gateway ECU"),
            update_order.index("BCM ECU"),
        )
        self.assertLess(
            update_order.index("Gateway ECU"),
            update_order.index("Cluster ECU"),
        )
        self.assertNotIn(
            "Cluster ECU",
            graph.children("BCM ECU"),
        )
        self.assertEqual(update_order, ["Gateway ECU", "BCM ECU", "Cluster ECU"])

    def test_campaign_dependency_override_rejects_unknown_ecu(self):
        ecus = [
            ECU(0x201, "Gateway ECU", "1.0.0", "VCAN", dependencies=[]),
        ]
        campaign = Campaign(
            campaign_id="OTA_TEST",
            vehicle_model="Virtual Vehicle",
            release_version="2.0.0",
            priority="HIGH",
            transport="VCAN",
            rollback_enabled=True,
            created_by="test",
            targets=[],
            dependency_overrides={"Gateway ECU": ["Missing ECU"]},
        )

        errors = DependencyGraphBuilder().validate_campaign_dependencies(
            ecus,
            campaign=campaign,
        )

        self.assertIn("Gateway ECU depends on unknown ECU: Missing ECU", errors)

    def test_campaign_dependency_override_can_make_bcm_gateway_cluster_chain(self):
        ecus = [
            ECU(0x203, "Cluster ECU", "1.0.0", "VCAN", dependencies=[]),
            ECU(0x202, "BCM ECU", "1.0.0", "VCAN", dependencies=[]),
            ECU(0x201, "Gateway ECU", "1.0.0", "VCAN", dependencies=[]),
        ]
        campaign = Campaign(
            campaign_id="OTA_TEST",
            vehicle_model="Virtual Vehicle",
            release_version="2.0.0",
            priority="HIGH",
            transport="VCAN",
            rollback_enabled=True,
            created_by="test",
            targets=[],
            dependency_overrides={
                "BCM ECU": [],
                "Gateway ECU": ["BCM ECU"],
                "Cluster ECU": ["Gateway ECU"],
            },
        )

        graph = DependencyGraphBuilder().build(ecus, campaign=campaign)
        update_order = TopologicalUpdatePlanner().plan(graph)

        self.assertEqual(update_order, ["BCM ECU", "Gateway ECU", "Cluster ECU"])


if __name__ == "__main__":
    unittest.main()
