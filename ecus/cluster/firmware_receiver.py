import os
import hashlib
from pathlib import Path


class FirmwareReceiver:
    """
    Firmware download buffer and storage for an ECU.

    Receives firmware chunks, reconstructs the binary,
    verifies integrity via SHA-256, and writes to disk.
    """

    def __init__(self, download_directory: str):

        self.download_directory = Path(download_directory)
        self.buffer = bytearray()
        self.chunk_count = 0
        self.expected_size = None

    def clear(self):

        self.buffer = bytearray()
        self.chunk_count = 0
        self.expected_size = None

    def set_expected_size(self, size):

        self.expected_size = size

    def append_chunk(self, frame: bytes):
        """
        Frame format:
            Byte0    -> Message Type (FIRMWARE_DATA)
            Byte1    -> Sequence Number
            Byte2-7  -> Firmware Bytes
        """

        sequence = frame[1]

        payload = frame[2:]

        self.buffer.extend(payload)

        self.chunk_count += 1

        return sequence, payload

    def save(self, filename):

        os.makedirs(self.download_directory, exist_ok=True)

        output = self.download_directory / filename

        with open(output, "wb") as f:
            f.write(self._firmware_data())

        return output

    def downloaded_size(self):

        return len(self._firmware_data())

    def sha256(self):

        return hashlib.sha256(self._firmware_data()).hexdigest()

    def _firmware_data(self):

        if self.expected_size is None:
            return bytes(self.buffer)

        return bytes(self.buffer[:self.expected_size])

    def verify(self, original_path):
        """
        Compare the downloaded firmware against the original.

        Returns (passed, expected_sha, actual_sha, expected_size, actual_size)
        """

        with open(original_path, "rb") as f:
            original_data = f.read()

        expected_sha = hashlib.sha256(original_data).hexdigest()
        actual_sha = self.sha256()

        expected_size = len(original_data)
        actual_size = self.downloaded_size()

        passed = (expected_sha == actual_sha)

        return passed, expected_sha, actual_sha, expected_size, actual_size
