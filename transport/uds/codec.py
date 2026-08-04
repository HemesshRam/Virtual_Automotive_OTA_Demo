"""
UDS codec helpers for DoIP and CAN transport paths.

The public functions stay intentionally small because the rest of the demo
depends on them. Internally, request payloads prefer udsoncan service builders
and fall back to explicit bytes if the library is unavailable.
"""

from __future__ import annotations

from transport.uds.security import derive_demo_security_key

try:
    from udsoncan import MemoryLocation
    from udsoncan.services import (
        DiagnosticSessionControl,
        ECUReset,
        ReadDataByIdentifier,
        RequestDownload,
        RequestTransferExit,
        RoutineControl,
        SecurityAccess,
        TesterPresent,
        TransferData,
    )

    UDSCAN_AVAILABLE = True
except ImportError:
    MemoryLocation = None
    DiagnosticSessionControl = None
    ECUReset = None
    ReadDataByIdentifier = None
    RequestDownload = None
    RequestTransferExit = None
    RoutineControl = None
    SecurityAccess = None
    TesterPresent = None
    TransferData = None
    UDSCAN_AVAILABLE = False


SID_DIAGNOSTIC_SESSION_CONTROL = 0x10
SID_ECU_RESET = 0x11
SID_READ_DATA_BY_IDENTIFIER = 0x22
SID_SECURITY_ACCESS = 0x27
SID_ROUTINE_CONTROL = 0x31
SID_REQUEST_DOWNLOAD = 0x34
SID_TRANSFER_DATA = 0x36
SID_REQUEST_TRANSFER_EXIT = 0x37
SID_TESTER_PRESENT = 0x3E

POS_RESPONSE_OFFSET = 0x40
SID_NEGATIVE_RESPONSE = 0x7F
NRC_RESPONSE_PENDING = 0x78
NRC_INCORRECT_LENGTH_OR_FORMAT = 0x13
NRC_CONDITIONS_NOT_CORRECT = 0x22
NRC_REQUEST_SEQUENCE_ERROR = 0x24
NRC_REQUEST_OUT_OF_RANGE = 0x31
NRC_SECURITY_ACCESS_DENIED = 0x33
NRC_INVALID_KEY = 0x35
NRC_EXCEED_NUMBER_OF_ATTEMPTS = 0x36
NRC_REQUIRED_TIME_DELAY_NOT_EXPIRED = 0x37
NRC_UPLOAD_DOWNLOAD_NOT_ACCEPTED = 0x70
NRC_WRONG_BLOCK_SEQUENCE_COUNTER = 0x73
NRC_SUBFUNCTION_NOT_SUPPORTED_IN_ACTIVE_SESSION = 0x7E
NRC_SERVICE_NOT_SUPPORTED_IN_ACTIVE_SESSION = 0x7F

DID_SOFTWARE_VERSION = 0xF188

DEFAULT_SESSION_PROGRAMMING = 0x02
DEFAULT_RESET_HARD = 0x01
SECURITY_ACCESS_REQUEST_SEED = 0x01
SECURITY_ACCESS_SEND_KEY = 0x02
ROUTINE_CONTROL_START = 0x01

ROUTINE_ERASE_MEMORY = 0xFF00
ROUTINE_VERIFY_IMAGE = 0xFF01
ROUTINE_ACTIVATE_IMAGE = 0xFF02


def _payload_from_request(request):
    return bytes(request.get_payload())


def build_diagnostic_session_control(session: int = DEFAULT_SESSION_PROGRAMMING) -> bytes:
    if UDSCAN_AVAILABLE:
        return _payload_from_request(
            DiagnosticSessionControl.make_request(session)
        )

    return bytes([SID_DIAGNOSTIC_SESSION_CONTROL, session & 0xFF])


def build_tester_present(suppress_response: bool = False) -> bytes:
    if UDSCAN_AVAILABLE and not suppress_response:
        return _payload_from_request(TesterPresent.make_request())

    subfunction = 0x80 if suppress_response else 0x00
    return bytes([SID_TESTER_PRESENT, subfunction])


def build_read_data_by_identifier(did: int = DID_SOFTWARE_VERSION) -> bytes:
    if UDSCAN_AVAILABLE:
        return _payload_from_request(
            ReadDataByIdentifier.make_request(did, didconfig=None)
        )

    return bytes([SID_READ_DATA_BY_IDENTIFIER]) + did.to_bytes(2, "big")


def build_security_access_request_seed(
    level: int = SECURITY_ACCESS_REQUEST_SEED,
) -> bytes:
    if UDSCAN_AVAILABLE:
        return _payload_from_request(
            SecurityAccess.make_request(level, SecurityAccess.Mode.RequestSeed)
        )

    return bytes([SID_SECURITY_ACCESS, level & 0xFF])


def build_security_access_send_key(
    level: int = SECURITY_ACCESS_SEND_KEY,
    key: bytes = b"",
) -> bytes:
    if UDSCAN_AVAILABLE:
        return _payload_from_request(
            SecurityAccess.make_request(level, SecurityAccess.Mode.SendKey, key)
        )

    return bytes([SID_SECURITY_ACCESS, level & 0xFF]) + key


def build_routine_control_start(
    routine_id: int,
    data: bytes = b"",
) -> bytes:
    if UDSCAN_AVAILABLE:
        return _payload_from_request(
            RoutineControl.make_request(
                routine_id,
                RoutineControl.ControlType.startRoutine,
                data,
            )
        )

    return (
        bytes([SID_ROUTINE_CONTROL, ROUTINE_CONTROL_START])
        + routine_id.to_bytes(2, "big")
        + data
    )


def build_request_download(
    memory_size: int,
    memory_address: int = 0x00000000,
) -> bytes:
    """
    Encode a simple 4-byte address + 4-byte size RequestDownload.
    """

    if UDSCAN_AVAILABLE:
        location = MemoryLocation(
            address=memory_address,
            memorysize=memory_size,
            address_format=32,
            memorysize_format=32,
        )
        return _payload_from_request(
            RequestDownload.make_request(location)
        )

    data_format_identifier = 0x00
    address_and_length_format = 0x44

    return (
        bytes([SID_REQUEST_DOWNLOAD, data_format_identifier, address_and_length_format])
        + memory_address.to_bytes(4, "big")
        + memory_size.to_bytes(4, "big")
    )


def build_transfer_data(sequence_number: int, payload: bytes) -> bytes:
    if UDSCAN_AVAILABLE:
        return _payload_from_request(
            TransferData.make_request(sequence_number, payload)
        )

    return bytes([SID_TRANSFER_DATA, sequence_number & 0xFF]) + payload


def build_request_transfer_exit() -> bytes:
    if UDSCAN_AVAILABLE:
        return _payload_from_request(RequestTransferExit.make_request())

    return bytes([SID_REQUEST_TRANSFER_EXIT])


def parse_request_download_max_block_length(payload: bytes) -> int | None:
    """
    Extract the demo max-number-of-block-length from a positive
    RequestDownload response.

    This repo currently uses a simplified response shape:
    [0x74, 0x00, 0x44, block_len_hi, block_len_lo]
    """

    if not payload or payload[0] != positive_response_sid(SID_REQUEST_DOWNLOAD):
        return None
    if len(payload) < 5:
        return None

    max_block_length = int.from_bytes(payload[-2:], "big")
    return max_block_length if max_block_length > 0 else None


def build_ecu_reset(reset_type: int = DEFAULT_RESET_HARD) -> bytes:
    if UDSCAN_AVAILABLE:
        return _payload_from_request(ECUReset.make_request(reset_type))

    return bytes([SID_ECU_RESET, reset_type & 0xFF])


def positive_response_sid(request_sid: int) -> int:
    return (request_sid + POS_RESPONSE_OFFSET) & 0xFF


def is_negative_response(payload: bytes) -> bool:
    return len(payload) >= 3 and payload[0] == SID_NEGATIVE_RESPONSE


def is_response_pending(payload: bytes, request_sid: int | None = None) -> bool:
    if not is_negative_response(payload):
        return False

    if request_sid is not None and payload[1] != request_sid:
        return False

    return payload[2] == NRC_RESPONSE_PENDING


_NRC_NAMES = {
    NRC_INCORRECT_LENGTH_OR_FORMAT: "incorrectLengthOrInvalidFormat",
    NRC_CONDITIONS_NOT_CORRECT: "conditionsNotCorrect",
    NRC_REQUEST_SEQUENCE_ERROR: "requestSequenceError",
    NRC_REQUEST_OUT_OF_RANGE: "requestOutOfRange",
    NRC_SECURITY_ACCESS_DENIED: "securityAccessDenied",
    NRC_INVALID_KEY: "invalidKey",
    NRC_EXCEED_NUMBER_OF_ATTEMPTS: "exceedNumberOfAttempts",
    NRC_REQUIRED_TIME_DELAY_NOT_EXPIRED: "requiredTimeDelayNotExpired",
    NRC_UPLOAD_DOWNLOAD_NOT_ACCEPTED: "uploadDownloadNotAccepted",
    NRC_WRONG_BLOCK_SEQUENCE_COUNTER: "wrongBlockSequenceCounter",
    NRC_RESPONSE_PENDING: "responsePending",
    NRC_SUBFUNCTION_NOT_SUPPORTED_IN_ACTIVE_SESSION: "subFunctionNotSupportedInActiveSession",
    NRC_SERVICE_NOT_SUPPORTED_IN_ACTIVE_SESSION: "serviceNotSupportedInActiveSession",
}


def nrc_name(code: int) -> str:
    return _NRC_NAMES.get(code, f"unknownNRC_0x{code:02X}")


def parse_software_version(payload: bytes) -> str | None:
    if len(payload) < 3 or payload[0] != positive_response_sid(SID_READ_DATA_BY_IDENTIFIER):
        return None

    did = int.from_bytes(payload[1:3], "big")
    if did != DID_SOFTWARE_VERSION:
        return None

    version_bytes = payload[3:]
    return version_bytes.decode("utf-8", errors="ignore").strip("\x00")


def parse_security_access_seed(payload: bytes) -> bytes | None:
    if len(payload) < 3 or payload[0] != positive_response_sid(SID_SECURITY_ACCESS):
        return None

    if payload[1] != SECURITY_ACCESS_REQUEST_SEED:
        return None

    return payload[2:]
