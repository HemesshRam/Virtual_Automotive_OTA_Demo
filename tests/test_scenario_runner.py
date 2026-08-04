import json
import tempfile
import unittest
from pathlib import Path

from ecus.base.runtime_control import load_runtime_control
from tcu.scenario_runner import ScenarioRunner
from vehicle.topology_loader import VehicleTopology


class ScenarioRunnerTest(unittest.TestCase):
    def test_default_scenario_generates_valid_runtime_files(self):
        runner = ScenarioRunner("scenarios/default_https_mqtt.json")
        env = runner.prepare()

        self.assertEqual(env["OTA_CLOUD_CONTROL"], "mqtt")
        self.assertEqual(env["OTA_HTTPS_ENABLED"], "1")
        self.assertTrue(Path(env["OTA_VEHICLE_TOPOLOGY"]).exists())
        self.assertTrue(Path(env["OTA_CAMPAIGN_FILE"]).exists())
        self.assertEqual(VehicleTopology(env["OTA_VEHICLE_TOPOLOGY"]).validate(), [])

    def test_body_two_ecu_scenario_moves_cluster_into_body_zone_dynamically(self):
        runner = ScenarioRunner("scenarios/body_two_ecus_https_mqtt.json")
        env = runner.prepare()
        topology = VehicleTopology(env["OTA_VEHICLE_TOPOLOGY"])

        self.assertEqual(topology.validate(), [])
        body_zone = topology.build_zone_registry()["body_zone"]
        self.assertEqual(
            sorted(ecu["ecu_name"] for ecu in body_zone["ecus"].values()),
            ["BCM ECU", "Cluster ECU"],
        )
        self.assertNotIn("cluster_zone", topology.build_zone_registry())
        self.assertEqual(env["OTA_ECU_CLUSTER_CAN_CHANNEL"], "vcan_bcm")
        self.assertEqual(env["OTA_SCENARIO_TOPOLOGY_MODE"], "body_two_ecus")

    def test_scenario_dependency_overrides_are_compiled_into_runtime_campaign(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            scenario_path = Path(temp_dir) / "scenario.json"
            scenario_path.write_text(
                json.dumps(
                    {
                        "scenario_name": "override_case",
                        "base_topology": "vehicle/topology.json",
                        "base_campaign": "campaigns/campaign_v1.default.json",
                        "transport": "doip",
                        "zonal_mode": "deep-zonal",
                        "dependency_overrides": {
                            "Gateway ECU": ["BCM ECU"],
                            "BCM ECU": [],
                            "Cluster ECU": ["Gateway ECU"]
                        },
                        "ecu_runtime": {}
                    }
                ),
                encoding="utf-8",
            )

            runner = ScenarioRunner(scenario_path)
            env = runner.prepare()
            with open(env["OTA_CAMPAIGN_FILE"], "r", encoding="utf-8") as fp:
                campaign = json.load(fp)

            self.assertEqual(
                campaign["dependency_overrides"]["Gateway ECU"],
                ["BCM ECU"],
            )

    def test_dependency_mode_compiles_campaign_overrides(self):
        runner = ScenarioRunner("scenarios/dependency_cluster_gateway_https_mqtt.json")
        env = runner.prepare()

        with open(env["OTA_CAMPAIGN_FILE"], "r", encoding="utf-8") as fp:
            campaign = json.load(fp)

        self.assertEqual(
            campaign["dependency_overrides"]["Cluster ECU"],
            ["Gateway ECU"],
        )
        self.assertEqual(env["OTA_SCENARIO_DEPENDENCY_MODE"], "cluster_depends_gateway")

    def test_offline_scenario_applies_runtime_controls(self):
        runner = ScenarioRunner("scenarios/cluster_offline_https_mqtt.json")
        env = runner.prepare()

        cluster_control = load_runtime_control("cluster")
        bcm_control = load_runtime_control("bcm")

        self.assertFalse(cluster_control["heartbeat_enabled"])
        self.assertTrue(bcm_control["heartbeat_enabled"])
        self.assertEqual(env["OTA_SCENARIO_OFFLINE_ECUS"], "Cluster ECU")

    def test_partial_skip_dependency_mode_marks_cluster_optional(self):
        runner = ScenarioRunner("scenarios/partial_skip_cluster_https_mqtt.json")
        env = runner.prepare()

        with open(env["OTA_CAMPAIGN_FILE"], "r", encoding="utf-8") as fp:
            campaign = json.load(fp)

        cluster_target = next(
            target for target in campaign["targets"]
            if target["ecu_name"] == "Cluster ECU"
        )
        self.assertFalse(cluster_target["mandatory"])
        self.assertEqual(cluster_target["minimum_bootloader"], "9.9.0")


if __name__ == "__main__":
    unittest.main()
