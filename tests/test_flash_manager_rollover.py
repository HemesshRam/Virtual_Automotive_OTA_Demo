import unittest

from transport.uds.flash_manager import FlashManager


class RecordingTransport:

    def __init__(self, max_transfer_payload=4):
        self.max_transfer_payload = max_transfer_payload
        self.calls = []

    def transfer_data(self, sequence, payload):
        self.calls.append((sequence, payload))
        return True


class FlashManagerRolloverTest(unittest.TestCase):

    def test_transfer_data_rolls_sequence_counter_after_ff(self):
        transport = RecordingTransport(max_transfer_payload=1)
        manager = FlashManager(transport)

        manager.transfer_data(b"A" * 258)

        self.assertEqual(len(transport.calls), 258)
        self.assertEqual(transport.calls[0][0], 1)
        self.assertEqual(transport.calls[254][0], 255)
        self.assertEqual(transport.calls[255][0], 0)
        self.assertEqual(transport.calls[256][0], 1)
        self.assertEqual(transport.calls[257][0], 2)


if __name__ == "__main__":
    unittest.main()
