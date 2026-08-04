import json
import tempfile
import unittest
from pathlib import Path

from vehicle.topology_loader import VehicleTopology


class VehicleTopologyValidationTest(unittest.TestCase):

    def _write_topology(self, data):
        temp_dir = tempfile.TemporaryDirectory()
        path = Path(temp_dir.name) / "topology.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        self.addCleanup(temp_dir.cleanup)
        return path

    def test_current_topology_validates(self):
        self.assertEqual(VehicleTopology().validate(), [])

    def test_composed_topology_exposes_runtime_mapping_and_gateway_endpoint(self):
        topology = VehicleTopology()

        self.assertEqual(topology.data["central_gateway"]["host"], "127.0.0.1")
        self.assertEqual(topology.data["central_gateway"]["doip_port"], 13400)
        self.assertEqual(topology.build_zone_registry()["body_zone"]["can_channel"], "vcan_bcm")
        self.assertEqual(
            topology.data["deployment_runtime"]["mapping_name"],
            "local_linux_demo",
        )

    def test_body_multi_ecu_zone_topology_validates(self):
        topology = VehicleTopology("vehicle/topology.body_multi_ecu.json")
        self.assertEqual(topology.validate(), [])

        body_zone = topology.build_zone_registry()["body_zone"]
        self.assertEqual(
            sorted(ecu["ecu_name"] for ecu in body_zone["ecus"].values()),
            ["BCM ECU", "Cluster ECU"],
        )
        self.assertEqual(body_zone["can_channel"], "vcan_bcm")

    def test_midsize_demo_topology_validates(self):
        topology = VehicleTopology("vehicle/topology.midsize_demo.json")
        self.assertEqual(topology.validate(), [])
        registry = topology.build_zone_registry()
        self.assertIn("cockpit_zone", registry)
        self.assertEqual(registry["cockpit_zone"]["can_channel"], "vcan_clus")
        self.assertEqual(
            sorted(ecu["ecu_name"] for ecu in registry["cockpit_zone"]["ecus"].values()),
            ["Cluster ECU", "HVAC ECU", "Infotainment ECU"],
        )

    def test_unknown_dependency_is_rejected(self):
        path = self._write_topology(
            {
                "vehicle": {"architecture": "zonal"},
                "ota_allowed_uds_services": ["0x10"],
                "zones": [
                    {
                        "zone_id": "body_zone",
                        "display_name": "Body Zone Controller",
                        "service_port": 15002,
                        "network": {"channel": "vcan_bcm"},
                        "ecus": [
                            {
                                "ecu_name": "BCM ECU",
                                "logical_address": "0x1002",
                                "can_id": "0x202",
                                "dependencies": ["Missing ECU"],
                            }
                        ],
                    }
                ],
            }
        )

        errors = VehicleTopology(path).validate()
        self.assertIn("BCM ECU depends on unknown ECU: Missing ECU", errors)

    def test_dependency_cycle_is_rejected(self):
        path = self._write_topology(
            {
                "vehicle": {"architecture": "zonal"},
                "ota_allowed_uds_services": ["0x10"],
                "zones": [
                    {
                        "zone_id": "gateway_zone",
                        "display_name": "Gateway Zone Controller",
                        "service_port": 15001,
                        "network": {"channel": "vcan_gate"},
                        "ecus": [
                            {
                                "ecu_name": "Gateway ECU",
                                "logical_address": "0x1001",
                                "can_id": "0x201",
                                "dependencies": ["BCM ECU"],
                            }
                        ],
                    },
                    {
                        "zone_id": "body_zone",
                        "display_name": "Body Zone Controller",
                        "service_port": 15002,
                        "network": {"channel": "vcan_bcm"},
                        "ecus": [
                            {
                                "ecu_name": "BCM ECU",
                                "logical_address": "0x1002",
                                "can_id": "0x202",
                                "dependencies": ["Gateway ECU"],
                            }
                        ],
                    },
                ],
            }
        )

        errors = VehicleTopology(path).validate()
        self.assertTrue(
            any(error.startswith("dependency cycle detected") for error in errors)
        )


if __name__ == "__main__":
    unittest.main()
