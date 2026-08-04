import struct
import unittest

from common.logical_addresses import GATEWAY_ADDRESS, TESTER_ADDRESS
from transport.doip.server import DoIPServer
from transport.doip.protocol import DIAGNOSTIC_MESSAGE


class FakeClient:

    def __init__(self):
        self.sent = []

    def sendall(self, payload):
        self.sent.append(payload)


class DoIPServerStrictModeTest(unittest.TestCase):

    def test_non_uds_payload_is_rejected_by_default(self):
        server = DoIPServer.__new__(DoIPServer)
        server._routes = {
            GATEWAY_ADDRESS: {
                "ecu_name": "Gateway ECU",
                "can_id": 0x201,
                "channel": "vcan_gate",
            }
        }
        server.ecus = {GATEWAY_ADDRESS: object()}
        server.allow_legacy_ota_payloads = False

        client = FakeClient()
        payload = (
            struct.pack("!HH", TESTER_ADDRESS, GATEWAY_ADDRESS)
            + b'{"type":"FIRMWARE_START"}'
        )

        server.process(client, DIAGNOSTIC_MESSAGE, payload)

        self.assertEqual(client.sent, [])


if __name__ == "__main__":
    unittest.main()
