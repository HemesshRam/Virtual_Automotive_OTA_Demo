import unittest

from transport.can.can_sender import CANSender
from transport.doip.library_client import LibraryDoIPClient
from transport.uds.codec import positive_response_sid


class DummyEcu:
    ecu_id = 0x201


class PendingCANTransport(CANSender):

    def __init__(self, responses):
        super().__init__()
        self._responses = list(responses)

    def _receive_uds_response(self, ecu, timeout=5.0, request_sid=None):
        if not self._responses:
            raise TimeoutError("no response")
        return self._responses.pop(0)


class ResponsePendingTest(unittest.TestCase):

    def test_can_sender_accepts_response_pending_before_positive(self):
        transport = PendingCANTransport(
            [
                bytes([0x7F, 0x31, 0x78]),
                bytes([positive_response_sid(0x31), 0x01, 0xFF, 0x00]),
            ]
        )

        response = transport._expect_positive_response(DummyEcu(), 0x31)
        self.assertEqual(response, bytes([0x71, 0x01, 0xFF, 0x00]))

    def test_doip_client_accepts_response_pending_before_positive(self):
        client = LibraryDoIPClient()
        queued = iter(
            [
                bytes([0x7F, 0x37, 0x78]),
                bytes([positive_response_sid(0x37)]),
            ]
        )

        client._receive_raw_diagnostic = lambda timeout=None: next(queued)

        response = client._expect_positive_response(bytes([0x7F, 0x37, 0x78]), 0x37)
        self.assertEqual(response, bytes([0x77]))


if __name__ == "__main__":
    unittest.main()
