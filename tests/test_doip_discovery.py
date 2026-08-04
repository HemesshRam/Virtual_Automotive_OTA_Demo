import unittest
from unittest.mock import patch

from tcu.ecu_discovery import ECUDiscovery


class FakeDoIPClient:

    def __init__(self):
        self.calls = []

    def connect(self):
        self.calls.append("connect")

    def discover_vehicle(self):
        self.calls.append("discover_vehicle")

    def activate(self):
        self.calls.append("activate")

    def read_version_by_address(self, logical_address, timeout=None):
        mapping = {
            0x1001: "1.0.0",
            0x1002: "1.0.0",
            0x1003: "1.0.0",
        }
        self.calls.append(("read_version_by_address", logical_address))
        return mapping[logical_address]

    def shutdown(self):
        self.calls.append("shutdown")


class DoIPDiscoveryTest(unittest.TestCase):

    @patch("transport.doip.library_client.PythonDoIPClient", object())
    @patch("transport.doip.library_client.LibraryDoIPClient", FakeDoIPClient)
    def test_doip_mode_discovers_ecus_without_can_broadcast(self):
        discovery = ECUDiscovery.__new__(ECUDiscovery)
        discovery.can_interfaces = []

        vehicle = ECUDiscovery.discover(discovery, transport="DOIP")

        ecus = vehicle.get_all_ecus()
        self.assertEqual(len(ecus), 3)
        self.assertEqual(
            sorted((ecu.ecu_name, ecu.current_version, ecu.can_channel) for ecu in ecus),
            [
                ("BCM ECU", "1.0.0", "doip"),
                ("Cluster ECU", "1.0.0", "doip"),
                ("Gateway ECU", "1.0.0", "doip"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
