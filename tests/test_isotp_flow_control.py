import unittest

from transport.can.isotp_adapter import IsoTpAdapter, IsoTpReassembler


class FakeMessage:

    def __init__(self, arbitration_id, data):
        self.arbitration_id = arbitration_id
        self.data = data


class FakeBus:

    def __init__(self, flow_control_frames=None):
        self.sent = []
        self._rx = [
            FakeMessage(0x201, frame)
            for frame in (flow_control_frames or [])
        ]

    def send(self, message):
        self.sent.append(message)

    def recv(self, timeout=None):
        if self._rx:
            return self._rx.pop(0)
        return None


class IsoTpFlowControlTest(unittest.TestCase):

    def test_sender_waits_for_flow_control_blocks(self):
        bus = FakeBus(
            flow_control_frames=[
                IsoTpAdapter.build_flow_control(block_size=1, stmin=0),
                IsoTpAdapter.build_flow_control(block_size=1, stmin=0),
                IsoTpAdapter.build_flow_control(block_size=1, stmin=0),
            ]
        )
        adapter = IsoTpAdapter(bus)

        payload = bytes(range(190))
        adapter.send(0x201, payload)

        self.assertEqual(len(bus.sent), 4)
        self.assertEqual(bus.sent[0].data[0] >> 4, 0x1)
        self.assertEqual(bus.sent[1].data[0] >> 4, 0x2)
        self.assertEqual(bus.sent[2].data[0] >> 4, 0x2)
        self.assertEqual(bus.sent[3].data[0] >> 4, 0x2)

    def test_reassembler_requests_additional_flow_control(self):
        adapter = IsoTpAdapter(FakeBus())
        reassembler = IsoTpReassembler(block_size=1, stmin=0)

        payload = bytes(range(190))
        frames = list(adapter.segment(payload))

        self.assertIsNone(reassembler.feed(frames[0]))
        self.assertEqual(
            reassembler.pop_flow_control_frame(),
            IsoTpAdapter.build_flow_control(block_size=1, stmin=0),
        )

        self.assertIsNone(reassembler.feed(frames[1]))
        self.assertEqual(
            reassembler.pop_flow_control_frame(),
            IsoTpAdapter.build_flow_control(block_size=1, stmin=0),
        )

        self.assertIsNone(reassembler.feed(frames[2]))
        self.assertEqual(
            reassembler.pop_flow_control_frame(),
            IsoTpAdapter.build_flow_control(block_size=1, stmin=0),
        )

        completed = reassembler.feed(frames[3])
        self.assertEqual(completed, payload)
        self.assertIsNone(reassembler.pop_flow_control_frame())

    def test_sender_rejects_excessive_wait_flow_controls(self):
        bus = FakeBus(
            flow_control_frames=[
                IsoTpAdapter.build_flow_control(flow_status=IsoTpAdapter.FLOW_STATUS_WAIT)
                for _ in range(IsoTpAdapter.MAX_WAIT_FRAMES + 1)
            ]
        )
        adapter = IsoTpAdapter(bus)

        with self.assertRaises(TimeoutError):
            adapter.send(0x201, bytes(range(190)))

    def test_reassembler_rejects_empty_first_frame_length(self):
        reassembler = IsoTpReassembler()
        self.assertIsNone(reassembler.feed(bytes([0x10, 0x00])))

    def test_sender_rejects_overflow_flow_control(self):
        bus = FakeBus(
            flow_control_frames=[
                IsoTpAdapter.build_flow_control(
                    flow_status=IsoTpAdapter.FLOW_STATUS_OVERFLOW
                )
            ]
        )
        adapter = IsoTpAdapter(bus)

        with self.assertRaises(RuntimeError):
            adapter.send(0x201, bytes(range(190)))

    def test_flow_control_parses_microsecond_stmin(self):
        parsed = IsoTpAdapter.parse_flow_control(
            IsoTpAdapter.build_flow_control(block_size=4, stmin=0xF3)
        )
        self.assertEqual(parsed[0], IsoTpAdapter.FLOW_STATUS_CONTINUE)
        self.assertEqual(parsed[1], 4)
        self.assertAlmostEqual(parsed[2], 0.0003, places=6)

    def test_reassembler_resets_on_sequence_mismatch(self):
        adapter = IsoTpAdapter(FakeBus())
        reassembler = IsoTpReassembler(block_size=0, stmin=0)
        payload = bytes(range(190))
        frames = list(adapter.segment(payload))

        self.assertIsNone(reassembler.feed(frames[0]))
        self.assertIsNone(reassembler.feed(frames[2]))
        self.assertIsNone(reassembler.expected_length)
        self.assertEqual(reassembler.buffer, bytearray())


if __name__ == "__main__":
    unittest.main()
