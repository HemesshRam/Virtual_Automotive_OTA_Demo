import unittest

from transport.can.can_sender import CANSender
from transport.doip.server import DoIPServer
from zones.base.zone_controller import ZoneController


class UDSResponseFilteringTest(unittest.TestCase):

    def test_filters_loopback_or_stale_payload_for_read_did(self):
        self.assertFalse(
            ZoneController._is_response_for_request(bytes.fromhex("0100"), 0x22)
        )
        self.assertFalse(
            DoIPServer._is_response_for_request(bytes.fromhex("0100"), 0x22)
        )
        self.assertFalse(
            CANSender._is_response_for_request(bytes.fromhex("0100"), 0x22)
        )

    def test_accepts_positive_read_did_response(self):
        payload = bytes.fromhex("62f188312e302e30")

        self.assertTrue(ZoneController._is_response_for_request(payload, 0x22))
        self.assertTrue(DoIPServer._is_response_for_request(payload, 0x22))
        self.assertTrue(CANSender._is_response_for_request(payload, 0x22))

    def test_accepts_matching_negative_response(self):
        payload = bytes.fromhex("7f2278")

        self.assertTrue(ZoneController._is_response_for_request(payload, 0x22))
        self.assertTrue(DoIPServer._is_response_for_request(payload, 0x22))
        self.assertTrue(CANSender._is_response_for_request(payload, 0x22))


if __name__ == "__main__":
    unittest.main()
