import os
import unittest
from unittest.mock import Mock, patch

from tcu.ecu_discovery import ECUDiscovery
from transport.can.can_sender import CANSender
from tcu.models.ecu import ECU
from transport.uds.codec import build_read_data_by_identifier


class VcanZonalRoutingTest(unittest.TestCase):
    VERSION_RESPONSE = b"\x62\xF1\x88" + b"1.0.0"

    def setUp(self):
        self.previous = {
            "OTA_USE_ZONAL_CONTROLLERS": os.environ.get("OTA_USE_ZONAL_CONTROLLERS"),
            "OTA_ZONE_TRANSPORT": os.environ.get("OTA_ZONE_TRANSPORT"),
        }
        os.environ["OTA_USE_ZONAL_CONTROLLERS"] = "1"
        os.environ["OTA_ZONE_TRANSPORT"] = "tcp"

    def tearDown(self):
        for key, value in self.previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_can_sender_routes_uds_via_zone_controller_when_zonal_enabled(self):
        sender = CANSender()
        sender.zone_guard = Mock()
        sender.zone_client = Mock()
        sender.zone_client.forward_uds.return_value = [self.VERSION_RESPONSE]

        ecu = ECU(
            ecu_id=0x203,
            ecu_name="Cluster ECU",
            current_version="1.0.0",
            transport="VCAN",
            can_channel="vcan_clus",
        )

        sender._send_uds_request(ecu, build_read_data_by_identifier())

        sender.zone_guard.require_ecu_online.assert_called_once_with("Cluster ECU")
        sender.zone_client.forward_uds.assert_called_once()
        self.assertEqual(
            sender._receive_uds_response(ecu),
            self.VERSION_RESPONSE,
        )

    @patch("tcu.ecu_discovery.zone_service_available", return_value=True)
    def test_ecu_discovery_uses_zone_inventory_for_vcan_when_zonal_enabled(self, _available):
        discovery = ECUDiscovery()

        inventory = [
            {
                "zone_id": "gateway_zone",
                "can_channel": "vcan_gate",
                "ecus": [
                    {
                        "logical_address": "0x1001",
                        "ecu_name": "Gateway ECU",
                        "availability": {"state": "ONLINE"},
                    }
                ],
            },
            {
                "zone_id": "body_zone",
                "can_channel": "vcan_bcm",
                "ecus": [
                    {
                        "logical_address": "0x1002",
                        "ecu_name": "BCM ECU",
                        "availability": {"state": "ONLINE"},
                    },
                    {
                        "logical_address": "0x1003",
                        "ecu_name": "Cluster ECU",
                        "availability": {"state": "ONLINE"},
                    },
                ],
            },
        ]

        responses = {
            0x1001: [self.VERSION_RESPONSE],
            0x1002: [self.VERSION_RESPONSE],
            0x1003: [self.VERSION_RESPONSE],
        }

        with patch("tcu.ecu_discovery.ZoneTransportClient") as client_cls:
            client = client_cls.return_value
            client.inventory.return_value = inventory
            client.forward_uds.side_effect = lambda logical_address, _payload: responses[logical_address]

            vehicle = discovery.discover(transport="VCAN")

        ecu_names = [ecu.ecu_name for ecu in vehicle.get_all_ecus()]
        self.assertEqual(ecu_names, ["Gateway ECU", "BCM ECU", "Cluster ECU"])


if __name__ == "__main__":
    unittest.main()
