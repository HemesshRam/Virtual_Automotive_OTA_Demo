import time
import unittest

from ecus.base.uds_can_programmer import UDSCanProgrammer
from transport.uds.codec import (
    DEFAULT_SESSION_PROGRAMMING,
    NRC_EXCEED_NUMBER_OF_ATTEMPTS,
    NRC_INCORRECT_LENGTH_OR_FORMAT,
    NRC_REQUIRED_TIME_DELAY_NOT_EXPIRED,
    NRC_REQUEST_OUT_OF_RANGE,
    NRC_REQUEST_SEQUENCE_ERROR,
    NRC_SERVICE_NOT_SUPPORTED_IN_ACTIVE_SESSION,
    NRC_WRONG_BLOCK_SEQUENCE_COUNTER,
    SID_REQUEST_DOWNLOAD,
    SID_SECURITY_ACCESS,
    SID_REQUEST_TRANSFER_EXIT,
    SID_TRANSFER_DATA,
    build_request_download,
    build_security_access_send_key,
    build_transfer_data,
)


class DummyBus:

    def send(self, message):
        return None


class DummyCan:

    def __init__(self):
        self.bus = DummyBus()

    def send(self, message):
        return None


class DummyVersionManager:

    def get_current_version(self):
        return "1.0.0"


class DummyReceiver:

    def __init__(self):
        self.buffer = bytearray()
        self.chunk_count = 0
        self.expected_size = None

    def clear(self):
        self.buffer = bytearray()
        self.chunk_count = 0
        self.expected_size = None

    def set_expected_size(self, size):
        self.expected_size = size

    def save(self, filename):
        return filename

    def verify(self, original_path):
        return True, "", "", 0, 0


class CaptureProgrammer(UDSCanProgrammer):

    def __init__(self):
        super().__init__(
            DummyCan(),
            0x201,
            "gateway",
            DummyVersionManager(),
            DummyReceiver(),
            "dummy.bin",
            "orig.bin",
            "2.0.0",
        )
        self.sent_payloads = []

    def _send(self, payload):
        self.sent_payloads.append(payload)


class UDSProgrammerStateTest(unittest.TestCase):

    def test_session_timeout_rejects_programming_service(self):
        programmer = CaptureProgrammer()
        programmer.current_session = DEFAULT_SESSION_PROGRAMMING
        programmer.session_started_at = (
            time.monotonic() - programmer.SESSION_TIMEOUT_SECONDS - 1.0
        )

        programmer._handle_uds(build_request_download(16))

        self.assertEqual(
            programmer.sent_payloads[-1],
            bytes([0x7F, SID_REQUEST_DOWNLOAD, NRC_SERVICE_NOT_SUPPORTED_IN_ACTIVE_SESSION]),
        )

    def test_transfer_data_rejects_wrong_sequence(self):
        programmer = CaptureProgrammer()
        programmer.current_session = DEFAULT_SESSION_PROGRAMMING
        programmer.session_started_at = time.monotonic()
        programmer.security_unlocked = True
        programmer.erase_completed = True
        programmer.download_requested = True
        programmer.expected_size = 8
        programmer.expected_transfer_sequence = 1

        programmer._handle_uds(build_transfer_data(2, b"abcd"))

        self.assertEqual(
            programmer.sent_payloads[-1],
            bytes([0x7F, SID_TRANSFER_DATA, NRC_WRONG_BLOCK_SEQUENCE_COUNTER]),
        )

    def test_security_lockout_after_invalid_keys(self):
        programmer = CaptureProgrammer()
        programmer.current_session = DEFAULT_SESSION_PROGRAMMING
        programmer.session_started_at = time.monotonic()
        programmer.pending_seed = bytes.fromhex("12345678")

        wrong_key_request = build_security_access_send_key(key=b"\x00\x00\x00\x00")

        programmer._handle_uds(wrong_key_request)
        programmer.pending_seed = bytes.fromhex("12345678")
        programmer._handle_uds(wrong_key_request)
        programmer.pending_seed = bytes.fromhex("12345678")
        programmer._handle_uds(wrong_key_request)

        self.assertEqual(
            programmer.sent_payloads[-1],
            bytes([0x7F, SID_SECURITY_ACCESS, NRC_EXCEED_NUMBER_OF_ATTEMPTS]),
        )

        programmer.pending_seed = b""
        programmer._handle_uds(bytes([SID_SECURITY_ACCESS, 0x01]))

        self.assertEqual(
            programmer.sent_payloads[-1],
            bytes([0x7F, SID_SECURITY_ACCESS, NRC_REQUIRED_TIME_DELAY_NOT_EXPIRED]),
        )

    def test_transfer_data_rejects_without_request_download(self):
        programmer = CaptureProgrammer()
        programmer.current_session = DEFAULT_SESSION_PROGRAMMING
        programmer.session_started_at = time.monotonic()
        programmer.security_unlocked = True
        programmer.erase_completed = True

        programmer._handle_uds(build_transfer_data(1, b"abcd"))

        self.assertEqual(
            programmer.sent_payloads[-1],
            bytes([0x7F, SID_TRANSFER_DATA, NRC_REQUEST_SEQUENCE_ERROR]),
        )

    def test_transfer_exit_rejects_without_request_download(self):
        programmer = CaptureProgrammer()
        programmer.current_session = DEFAULT_SESSION_PROGRAMMING
        programmer.session_started_at = time.monotonic()
        programmer.security_unlocked = True

        programmer._handle_uds(bytes([SID_REQUEST_TRANSFER_EXIT]))

        self.assertEqual(
            programmer.sent_payloads[-1],
            bytes([0x7F, SID_REQUEST_TRANSFER_EXIT, NRC_REQUEST_SEQUENCE_ERROR]),
        )

    def test_request_download_rejects_invalid_format_identifier(self):
        programmer = CaptureProgrammer()
        programmer.current_session = DEFAULT_SESSION_PROGRAMMING
        programmer.session_started_at = time.monotonic()
        programmer.security_unlocked = True
        programmer.erase_completed = True

        programmer._handle_uds(
            bytes([SID_REQUEST_DOWNLOAD, 0x00, 0x24]) + (0x08000000).to_bytes(4, "big") + (16).to_bytes(4, "big")
        )

        self.assertEqual(
            programmer.sent_payloads[-1],
            bytes([0x7F, SID_REQUEST_DOWNLOAD, NRC_REQUEST_OUT_OF_RANGE]),
        )

    def test_request_download_rejects_short_payload(self):
        programmer = CaptureProgrammer()
        programmer.current_session = DEFAULT_SESSION_PROGRAMMING
        programmer.session_started_at = time.monotonic()
        programmer.security_unlocked = True
        programmer.erase_completed = True

        programmer._handle_uds(bytes([SID_REQUEST_DOWNLOAD, 0x00]))

        self.assertEqual(
            programmer.sent_payloads[-1],
            bytes([0x7F, SID_REQUEST_DOWNLOAD, NRC_INCORRECT_LENGTH_OR_FORMAT]),
        )


if __name__ == "__main__":
    unittest.main()
