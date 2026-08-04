import struct
import unittest

from common.logical_addresses import GATEWAY_ADDRESS
from transport.doip.packet import parse_packet
from transport.doip.protocol import VEHICLE_IDENT_RESPONSE
from transport.doip.server import DoIPServer


class DoIPServerVehicleIdentificationTest(unittest.TestCase):

    def test_vehicle_identification_response_shape(self):
        packet = DoIPServer._build_vehicle_identification_response()
        payload_type, payload = parse_packet(packet)

        self.assertEqual(payload_type, VEHICLE_IDENT_RESPONSE)
        self.assertEqual(len(payload), 32)
        self.assertEqual(payload[:17], b"TESTVIN1234567890")
        self.assertEqual(
            struct.unpack("!H", payload[17:19])[0],
            GATEWAY_ADDRESS,
        )


if __name__ == "__main__":
    unittest.main()
