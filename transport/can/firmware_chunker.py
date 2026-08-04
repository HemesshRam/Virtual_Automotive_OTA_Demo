from pathlib import Path

from common.message_types import MessageType


class FirmwareChunker:
    """
    Legacy raw-frame firmware chunker.

    The production-style demo path uses UDS over ISO-TP on CAN FD. This helper is
    kept for inspecting the older custom OTA frame format without affecting the
    real-protocol transport path.

    Each payload contains:
        Byte0    -> Message Type (FIRMWARE_DATA)
        Byte1    -> Sequence Number
        Byte2-7  -> Firmware Bytes (6 bytes)
    """

    PAYLOAD_SIZE = 6

    def __init__(self, firmware_path: str):
        self.firmware_path = Path(firmware_path)

    def chunks(self):

        with open(self.firmware_path, "rb") as f:
            firmware = f.read()

        sequence = 0

        for index in range(0, len(firmware), self.PAYLOAD_SIZE):

            payload = firmware[index:index + self.PAYLOAD_SIZE]

            frame = bytes([
                MessageType.FIRMWARE_DATA,
                sequence
            ]) + payload

            yield frame

            sequence = (sequence + 1) % 256

    def total_chunks(self):

        size = self.firmware_path.stat().st_size

        count = size // self.PAYLOAD_SIZE

        if size % self.PAYLOAD_SIZE != 0:
            count += 1

        return count

    def firmware_size(self):

        return self.firmware_path.stat().st_size
