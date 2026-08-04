import time
import os
from dataclasses import dataclass
from typing import Iterator


@dataclass
class IsoTpFrame:
    payload: bytes
    sequence_number: int = 0


class IsoTpAdapter:
    """
    Minimal ISO-TP helper for CAN FD transport.

    This module keeps the protocol structure explicit so that the TCU
    can evolve from simulator-style messaging into UDS-over-ISO-TP.
    """

    MAX_CAN_FD_DATA = 64
    SF_MAX_PAYLOAD = 62
    FF_MAX_PAYLOAD = 62
    CF_MAX_PAYLOAD = 63
    FLOW_CONTROL_TIMEOUT = 2.0
    MAX_WAIT_FRAMES = 8

    FLOW_STATUS_CONTINUE = 0x0
    FLOW_STATUS_WAIT = 0x1
    FLOW_STATUS_OVERFLOW = 0x2

    def __init__(self, bus):
        self.bus = bus

    def segment(self, payload: bytes) -> Iterator[bytes]:
        if len(payload) <= self.SF_MAX_PAYLOAD:
            yield self._single_frame(payload)
            return

        total_length = len(payload)
        first = self._first_frame(total_length, payload[:self.FF_MAX_PAYLOAD])
        yield first

        remaining = payload[self.FF_MAX_PAYLOAD :]
        sequence = 1

        while remaining:
            chunk = remaining[: self.CF_MAX_PAYLOAD]
            remaining = remaining[self.CF_MAX_PAYLOAD :]
            yield self._consecutive_frame(sequence, chunk)
            sequence = (sequence + 1) % 16

    def send(self, arbitration_id: int, payload: bytes):
        if len(payload) <= self.SF_MAX_PAYLOAD:
            self.bus.send(self._wrap_frame(arbitration_id, self._single_frame(payload)))
            return

        total_length = len(payload)
        first_payload = payload[: self.FF_MAX_PAYLOAD]
        self.bus.send(
            self._wrap_frame(
                arbitration_id,
                self._first_frame(total_length, first_payload),
            )
        )

        remaining = payload[self.FF_MAX_PAYLOAD :]
        sequence = 1
        block_counter = 0

        block_size, stmin_seconds = self._wait_for_flow_control(arbitration_id)

        while remaining:
            if block_size and block_counter >= block_size:
                block_size, stmin_seconds = self._wait_for_flow_control(arbitration_id)
                block_counter = 0

            chunk = remaining[: self.CF_MAX_PAYLOAD]
            remaining = remaining[self.CF_MAX_PAYLOAD :]

            self.bus.send(
                self._wrap_frame(
                    arbitration_id,
                    self._consecutive_frame(sequence, chunk),
                )
            )

            sequence = (sequence + 1) % 16
            block_counter += 1

            if remaining and stmin_seconds > 0:
                time.sleep(stmin_seconds)

    def _single_frame(self, payload: bytes) -> bytes:
        if len(payload) > self.SF_MAX_PAYLOAD:
            raise ValueError("Single frame payload too large")

        if len(payload) <= 0x0F:
            pci = bytes([(0x0 << 4) | len(payload)])
            return pci + payload

        return bytes([0x00, len(payload)]) + payload

    def _first_frame(self, total_length: int, payload: bytes) -> bytes:
        if total_length > 0xFFF:
            raise ValueError("ISO-TP payload too large for simple adapter")
        pci = bytes([
            (0x1 << 4) | ((total_length >> 8) & 0x0F),
            total_length & 0xFF,
        ])
        return pci + payload

    def _consecutive_frame(self, sequence: int, payload: bytes) -> bytes:
        pci = bytes([(0x2 << 4) | (sequence & 0x0F)])
        return pci + payload

    @classmethod
    def build_flow_control(
        cls,
        flow_status: int = FLOW_STATUS_CONTINUE,
        block_size: int = 8,
        stmin: int = 0,
    ) -> bytes:
        return bytes([
            (0x3 << 4) | (flow_status & 0x0F),
            block_size & 0xFF,
            stmin & 0xFF,
        ])

    @classmethod
    def parse_flow_control(cls, frame: bytes):
        if len(frame) < 3 or (frame[0] >> 4) != 0x3:
            return None

        flow_status = frame[0] & 0x0F
        block_size = frame[1]
        stmin_byte = frame[2]

        if stmin_byte <= 0x7F:
            stmin_seconds = stmin_byte / 1000.0
        elif 0xF1 <= stmin_byte <= 0xF9:
            stmin_seconds = (stmin_byte - 0xF0) / 10000.0
        else:
            stmin_seconds = 0.0

        return flow_status, block_size, stmin_seconds

    def _wait_for_flow_control(self, arbitration_id: int):
        deadline = time.time() + self.FLOW_CONTROL_TIMEOUT
        wait_count = 0

        while time.time() < deadline:
            message = self.bus.recv(timeout=max(0.01, deadline - time.time()))
            if message is None or message.arbitration_id != arbitration_id:
                continue

            parsed = self.parse_flow_control(bytes(message.data))
            if parsed is None:
                continue

            flow_status, block_size, stmin_seconds = parsed

            if flow_status == self.FLOW_STATUS_WAIT:
                wait_count += 1
                if wait_count > self.MAX_WAIT_FRAMES:
                    raise TimeoutError("ISO-TP receiver stayed in WAIT too long")
                continue

            if flow_status == self.FLOW_STATUS_OVERFLOW:
                raise RuntimeError("ISO-TP receiver reported overflow")

            if flow_status != self.FLOW_STATUS_CONTINUE:
                raise RuntimeError(
                    f"Unsupported ISO-TP flow status 0x{flow_status:X}"
                )

            return block_size, stmin_seconds

        raise TimeoutError("Timed out waiting for ISO-TP FlowControl")

    @staticmethod
    def _wrap_frame(arbitration_id: int, payload: bytes):
        import can

        if len(payload) > IsoTpAdapter.MAX_CAN_FD_DATA:
            raise ValueError("Frame exceeds CAN FD max length")

        return can.Message(
            arbitration_id=arbitration_id,
            data=payload,
            is_extended_id=False,
            is_fd=True,
            bitrate_switch=True,
        )


class IsoTpReassembler:
    """
    Minimal ISO-TP reassembler for CAN FD single, first, and consecutive frames.
    """

    DEFAULT_BLOCK_SIZE = int(os.getenv("OTA_ISOTP_BLOCK_SIZE", "0"))
    DEFAULT_STMIN = int(os.getenv("OTA_ISOTP_STMIN", "0"))

    def __init__(self, block_size: int = DEFAULT_BLOCK_SIZE, stmin: int = DEFAULT_STMIN):
        self.expected_length = None
        self.buffer = bytearray()
        self.next_sequence = 1
        self.block_size = block_size
        self.stmin = stmin
        self._frames_until_next_flow_control = 0
        self._pending_flow_control = None

    def feed(self, frame: bytes) -> bytes | None:
        if not frame:
            return None

        frame_type = frame[0] >> 4

        if frame_type == 0x0:
            return self._single_frame(frame)

        if frame_type == 0x1:
            return self._first_frame(frame)

        if frame_type == 0x2:
            return self._consecutive_frame(frame)

        if frame_type == 0x3:
            return None

        return None

    def _single_frame(self, frame: bytes) -> bytes | None:
        length = frame[0] & 0x0F

        if length == 0:
            if len(frame) < 2:
                return None
            length = frame[1]
            start = 2
        else:
            start = 1

        if len(frame) < start + length:
            return None

        self.reset()
        return bytes(frame[start:start + length])

    def _first_frame(self, frame: bytes) -> bytes | None:
        if len(frame) < 2:
            return None

        self.expected_length = ((frame[0] & 0x0F) << 8) | frame[1]
        if self.expected_length == 0:
            self.reset()
            return None
        self.buffer = bytearray(frame[2:])
        self.next_sequence = 1
        self._frames_until_next_flow_control = self.block_size
        self._pending_flow_control = IsoTpAdapter.build_flow_control(
            block_size=self.block_size,
            stmin=self.stmin,
        )

        if len(self.buffer) >= self.expected_length:
            payload = bytes(self.buffer[:self.expected_length])
            self.reset()
            return payload

        return None

    def _consecutive_frame(self, frame: bytes) -> bytes | None:
        if self.expected_length is None:
            return None

        sequence = frame[0] & 0x0F
        if sequence != self.next_sequence:
            self.reset()
            return None

        if len(frame) < 2:
            self.reset()
            return None

        self.buffer.extend(frame[1:])
        self.next_sequence = (self.next_sequence + 1) & 0x0F

        if self.block_size:
            self._frames_until_next_flow_control -= 1

        if len(self.buffer) < self.expected_length:
            if self.block_size and self._frames_until_next_flow_control == 0:
                self._pending_flow_control = IsoTpAdapter.build_flow_control(
                    block_size=self.block_size,
                    stmin=self.stmin,
                )
                self._frames_until_next_flow_control = self.block_size
            return None

        payload = bytes(self.buffer[:self.expected_length])
        self.reset()
        return payload

    def pop_flow_control_frame(self) -> bytes | None:
        frame = self._pending_flow_control
        self._pending_flow_control = None
        return frame

    def reset(self):
        self.expected_length = None
        self.buffer = bytearray()
        self.next_sequence = 1
        self._frames_until_next_flow_control = 0
        self._pending_flow_control = None
