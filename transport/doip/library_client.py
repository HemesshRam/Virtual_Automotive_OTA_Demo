"""
LibraryDoIPClient

Wrapper around python-doipclient.

Keeps exactly the same interface as our current DoIPClient so the
TransportManager does not need to change.
"""

import os
import time

from common.demo_logging import demo_log

try:
    from doipclient import DoIPClient as PythonDoIPClient
except ImportError:
    PythonDoIPClient = None

from transport.doip.client import DoIPClient as CustomDoIPClient

from common.ecu_registry import ECU_REGISTRY
from common.logical_addresses import TESTER_ADDRESS

from transport.doip.message import OTAApplicationMessage
from transport.uds.security import derive_security_key
from transport.uds.codec import (
    build_diagnostic_session_control,
    build_ecu_reset,
    parse_request_download_max_block_length,
    build_read_data_by_identifier,
    build_request_download,
    build_request_transfer_exit,
    build_routine_control_start,
    build_security_access_request_seed,
    build_security_access_send_key,
    build_tester_present,
    build_transfer_data,
    NRC_WRONG_BLOCK_SEQUENCE_COUNTER,
    is_negative_response,
    is_response_pending,
    nrc_name,
    parse_software_version,
    positive_response_sid,
    SID_DIAGNOSTIC_SESSION_CONTROL,
    SID_ECU_RESET,
    SID_READ_DATA_BY_IDENTIFIER,
    SID_REQUEST_DOWNLOAD,
    SID_TRANSFER_DATA,
    SID_REQUEST_TRANSFER_EXIT,
    SID_ROUTINE_CONTROL,
    SID_SECURITY_ACCESS,
    SID_TESTER_PRESENT,
    ROUTINE_ACTIVATE_IMAGE,
    ROUTINE_ERASE_MEMORY,
    ROUTINE_VERIFY_IMAGE,
)


GATEWAY_IP = os.getenv("DOIP_GATEWAY_HOST", "127.0.0.1")
GATEWAY_PORT = int(os.getenv("DOIP_GATEWAY_PORT", "13400"))


class LibraryDoIPClient:

    # In the default DoIP gateway-proxy mode, flashing is handled inside the
    # gateway ECU context instead of forwarding every TransferData block over
    # the downstream CAN path. That allows a larger and faster Ethernet-side
    # block size than VCAN while still keeping a configurable cap for demo
    # stability.
    DEFAULT_TRANSFER_PAYLOAD = 8192
    MAX_GATEWAY_TRANSFER_PAYLOAD = 16384
    RESPONSE_TIMEOUT = 20.0
    RESPONSE_PENDING_TIMEOUT = 30.0
    TRANSFER_RETRY_LIMIT = 2
    QUIET_DOIP_ACKS = os.getenv("OTA_DOIP_LOG_ACKS", "0") != "1"

    def __init__(self):

        self.client = None
        self.current_ecu = None
        self.current_package = None
        self._active_target_address = None
        self.force_custom = os.getenv("OTA_USE_CUSTOM_DOIP", "0") == "1"
        self.using_library = PythonDoIPClient is not None and not self.force_custom
        self._transfer_chunk_count = 0
        self._transfer_total_size = 0
        self.max_transfer_payload = min(
            int(
                os.getenv(
                    "OTA_DOIP_TRANSFER_CHUNK_SIZE",
                    str(self.DEFAULT_TRANSFER_PAYLOAD),
                )
            ),
            self.MAX_GATEWAY_TRANSFER_PAYLOAD,
        )
        self.CHUNK_SIZE = self.max_transfer_payload

    # --------------------------------------------------------
    # Connection
    # --------------------------------------------------------

    def connect(self):

        if self.client is None:

            if self.using_library:

                #
                # ECU logical address here is the gateway.
                # Actual target ECU is supplied in
                # send_diagnostic_to_address().
                #

                self.client = PythonDoIPClient(

                    ecu_ip_address=GATEWAY_IP,

                    ecu_logical_address=0x1001,

                    tcp_port=GATEWAY_PORT,

                    client_logical_address=TESTER_ADDRESS,

                )

            else:

                self.client = CustomDoIPClient()

        demo_log("")
        demo_log("=" * 60)
        demo_log("python-doipclient" if self.using_library else "custom-doipclient fallback")
        demo_log("=" * 60)
        demo_log("Connected Successfully")

        return self.client

    def _ensure_connected(self):

        if self.client is None:
            self.connect()

    def _sync_expected_ecu_address(self, target_address):
        """
        python-doipclient tracks one expected ECU logical address at a time.
        We update it per target so one gateway session can talk to multiple ECUs.
        """

        self._active_target_address = target_address

        if self.using_library and self.client is not None:
            self.client._ecu_logical_address = target_address

    def _receive_raw_diagnostic(self, timeout=None):
        timeout = self.RESPONSE_TIMEOUT if timeout is None else timeout

        if not self.using_library:
            payload = self.client.receive_diagnostic(timeout=timeout)
            if payload is None:
                raise TimeoutError("Timed out waiting for diagnostic response")
            return bytes(payload)

        deadline = time.time() + timeout

        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                raise TimeoutError("Timed out waiting for diagnostic response")

            message = self.client.read_doip(
                timeout=remaining,
                transport=self.client.TransportType.TRANSPORT_TCP,
            )

            if message is None:
                raise TimeoutError("Timed out waiting for diagnostic response")

            name = message.__class__.__name__
            if name == "DiagnosticMessagePositiveAcknowledgement":
                if not self.QUIET_DOIP_ACKS:
                    print("[DoIP] Positive acknowledgement received")
                continue

            if name == "DiagnosticMessageNegativeAcknowledgement":
                nack_code = getattr(message, "nack_code", "UNKNOWN")
                raise IOError(
                    f"DoIP diagnostic request rejected with NACK {nack_code}"
                )

            if name == "DiagnosticMessage":
                expected_source = self._active_target_address
                expected_target = getattr(
                    self.client,
                    "_client_logical_address",
                    TESTER_ADDRESS,
                )
                if (
                    message.source_address == expected_source
                    and message.target_address == expected_target
                ):
                    return bytes(message.user_data)

                if not self.QUIET_DOIP_ACKS:
                    print(
                        "[DoIP] Ignoring diagnostic message with unexpected "
                        f"SA={hex(message.source_address)} TA={hex(message.target_address)}"
                    )
                continue

            if not self.QUIET_DOIP_ACKS:
                print(f"[DoIP] Ignoring unexpected message type {message.__class__}")

    def _expect_positive_response(self, payload: bytes, request_sid: int) -> bytes:

        deadline = time.time() + self.RESPONSE_PENDING_TIMEOUT
        current = payload

        while time.time() < deadline:
            if is_response_pending(current, request_sid):
                current = self._receive_raw_diagnostic(timeout=self.RESPONSE_TIMEOUT)
                continue

            if is_negative_response(current):
                nrc = current[2] if len(current) > 2 else None
                raise RuntimeError(
                    f"UDS request 0x{request_sid:02X} rejected with "
                    f"NRC 0x{nrc:02X} ({nrc_name(nrc)})"
                    if nrc is not None
                    else f"UDS request 0x{request_sid:02X} rejected"
                )

            expected_sid = positive_response_sid(request_sid)

            if len(current) == 0 or current[0] != expected_sid:
                raise RuntimeError(
                    f"Unexpected UDS response for 0x{request_sid:02X}: {current.hex()}"
                )

            return current

        raise TimeoutError(
            f"Timed out waiting for final UDS response for 0x{request_sid:02X}"
        )

    # --------------------------------------------------------
    # Discovery
    # --------------------------------------------------------

    def discover_vehicle(self):

        self._ensure_connected()

        demo_log("")
        demo_log("=" * 60)
        demo_log("DOIP VEHICLE DISCOVERY")
        demo_log("=" * 60)

        if self.using_library:
            try:
                response = self.client.request_vehicle_identification()
                demo_log("Vehicle Identification Successful")
                return response
            except TimeoutError:
                demo_log(
                    "Vehicle Identification timed out over UDP. "
                    "Falling back to direct DoIP gateway session."
                )
                return {
                    "status": "FALLBACK",
                    "gateway_ip": GATEWAY_IP,
                    "gateway_port": GATEWAY_PORT,
                }
        else:
            response = self.client.discover_vehicle()
            demo_log("Vehicle Identification Successful")
            return response

    def read_version_by_address(self, target_address, timeout=None):

        self._ensure_connected()
        self._sync_expected_ecu_address(target_address)

        self.client.send_diagnostic_to_address(
            target_address,
            build_read_data_by_identifier(),
        )
        response = self._receive_raw_diagnostic(timeout=timeout or self.RESPONSE_TIMEOUT)
        response = self._expect_positive_response(response, SID_READ_DATA_BY_IDENTIFIER)
        return parse_software_version(response)

    # --------------------------------------------------------
    # Routing Activation
    # --------------------------------------------------------

    def activate(self):

        #
        # activation_type = 0
        # ISO13400 Default Activation
        #

        self._ensure_connected()

        if self.using_library:
            response = self.client.request_activation(0)
        else:
            response = self.client.activate()

        demo_log("Routing Activation Successful")

        return response

    # --------------------------------------------------------
    # Generic Send
    # --------------------------------------------------------

    def send_message(self, target_address, message):

        self._ensure_connected()
        self._sync_expected_ecu_address(target_address)

        if self.using_library:
            if isinstance(message, bytes):
                payload = message
            else:
                raise TypeError("Library DoIP path expects raw UDS bytes")

            self.client.send_diagnostic_to_address(
                target_address,
                payload,
            )
            return

        payload = OTAApplicationMessage.encode(message)

        self.client.send_diagnostic_to_address(
            target_address,
            payload,
        )

    # --------------------------------------------------------
    # Generic Receive
    # --------------------------------------------------------

    def receive_message(self, timeout=None):

        self._ensure_connected()

        if self._active_target_address is not None:
            self._sync_expected_ecu_address(self._active_target_address)

        payload = self.client.receive_diagnostic(timeout=timeout)

        if self.using_library:
            return bytes(payload) if payload is not None else None

        return OTAApplicationMessage.decode(payload)

    # --------------------------------------------------------
    # UDS Transport Operations
    # --------------------------------------------------------

    def _current_target_address(self):

        ecu_name = self.current_ecu.ecu_name

        return ECU_REGISTRY[ecu_name]["logical_address"]

    def _require_ack(self, operation):

        response = self.receive_message()

        if response != {"status": "ACK"}:
            raise RuntimeError(f"{operation} failed: {response}")

        return True

    def diagnostic_session_control(self):

        self._ensure_connected()

        demo_log("[UDS] DiagnosticSessionControl")
        if self.using_library:
            target_address = self._current_target_address()
            self._sync_expected_ecu_address(target_address)
            self.client.send_diagnostic_to_address(
                target_address,
                build_diagnostic_session_control(),
            )
            response = self._receive_raw_diagnostic()
            self._expect_positive_response(response, SID_DIAGNOSTIC_SESSION_CONTROL)
            return True
        return True

    def tester_present(self):

        demo_log("[UDS] TesterPresent")
        if self.using_library:
            target_address = self._current_target_address()
            self._sync_expected_ecu_address(target_address)
            self.client.send_diagnostic_to_address(
                target_address,
                build_tester_present(),
            )
            response = self._receive_raw_diagnostic()
            self._expect_positive_response(response, SID_TESTER_PRESENT)
            return True
        return True

    def request_download(self, size):

        demo_log(f"[UDS] RequestDownload ({size:,} bytes)")
        # Track total transfer size for progress logging
        self._transfer_total_size = size
        self._transfer_chunk_count = 0

        target_address = self._current_target_address()
        self._sync_expected_ecu_address(target_address)

        if self.using_library:
            self.client.send_diagnostic_to_address(
                target_address,
                build_request_download(size),
            )
            response = self._receive_raw_diagnostic()
            response = self._expect_positive_response(response, SID_REQUEST_DOWNLOAD)
            negotiated_block_length = parse_request_download_max_block_length(response)
            if negotiated_block_length is not None:
                self.max_transfer_payload = min(
                    negotiated_block_length,
                    self.MAX_GATEWAY_TRANSFER_PAYLOAD,
                )
                self.CHUNK_SIZE = self.max_transfer_payload
                demo_log(
                    f"[UDS] RequestDownload negotiated block length="
                    f"{self.max_transfer_payload} bytes"
                )
            return True

        self.send_message(
            target_address,
            {
                "type": "FIRMWARE_START",
                "target_version": self.current_package["target_version"],
                "size": size,
            },
        )

        return self._require_ack("RequestDownload")

    def request_seed(self):

        demo_log("[UDS] SecurityAccess RequestSeed")
        if self.using_library:
            target_address = self._current_target_address()
            self._sync_expected_ecu_address(target_address)
            self.client.send_diagnostic_to_address(
                target_address,
                build_security_access_request_seed(),
            )
            response = self._receive_raw_diagnostic()
            response = self._expect_positive_response(response, SID_SECURITY_ACCESS)
            return response[2:]
        return bytes.fromhex("12345678")

    def send_key(self, seed):

        demo_log("[UDS] SecurityAccess SendKey")
        key = derive_security_key(seed)
        if self.using_library:
            target_address = self._current_target_address()
            self._sync_expected_ecu_address(target_address)
            self.client.send_diagnostic_to_address(
                target_address,
                build_security_access_send_key(key=key),
            )
            response = self._receive_raw_diagnostic()
            self._expect_positive_response(response, SID_SECURITY_ACCESS)
            return True
        return True

    def erase_memory(self, size):

        demo_log(f"[UDS] RoutineControl EraseMemory ({size} bytes)")
        if self.using_library:
            target_address = self._current_target_address()
            self._sync_expected_ecu_address(target_address)
            self.client.send_diagnostic_to_address(
                target_address,
                build_routine_control_start(
                    ROUTINE_ERASE_MEMORY,
                    size.to_bytes(4, "big"),
                ),
            )
            response = self._receive_raw_diagnostic()
            self._expect_positive_response(response, SID_ROUTINE_CONTROL)
            return True
        return True

    def transfer_data(self, sequence, payload):

        self._transfer_chunk_count += 1
        chunk_num = self._transfer_chunk_count

        # Throttle per-chunk logging for large transfers
        if self._transfer_total_size > 1_000_000:
            # Only log every 1000th chunk or first/last
            if chunk_num == 1 or chunk_num % 1000 == 0:
                demo_log(
                    f"[UDS] TransferData chunk={chunk_num:,} "
                    f"seq={sequence & 0xFF} size={len(payload)}"
                )
        else:
            demo_log(
                f"[UDS] TransferData seq={sequence} size={len(payload)}"
            )

        if self.using_library:
            target_address = self._current_target_address()
            self._sync_expected_ecu_address(target_address)
            request = build_transfer_data(sequence, payload)

            for attempt in range(1, self.TRANSFER_RETRY_LIMIT + 1):
                self.client.send_diagnostic_to_address(
                    target_address,
                    request,
                )
                try:
                    response = self._receive_raw_diagnostic()
                except TimeoutError:
                    if attempt >= self.TRANSFER_RETRY_LIMIT:
                        raise
                    demo_log(
                        f"[UDS] TransferData retry chunk={chunk_num:,} "
                        f"seq={sequence & 0xFF} attempt={attempt + 1}"
                    )
                    continue

                if is_negative_response(response):
                    nrc = response[2] if len(response) > 2 else None
                    if nrc == NRC_WRONG_BLOCK_SEQUENCE_COUNTER and attempt > 1:
                        demo_log(
                            f"[UDS] TransferData duplicate accepted chunk={chunk_num:,} "
                            f"seq={sequence & 0xFF}"
                        )
                        return True

                response = self._expect_positive_response(response, SID_TRANSFER_DATA)
                if len(response) < 2 or response[1] != (sequence & 0xFF):
                    raise RuntimeError(
                        f"Unexpected TransferData sequence response: {response.hex()}"
                    )
                return True

        return self._send_chunk(sequence, payload)

    def request_transfer_exit(self):

        demo_log("[UDS] RequestTransferExit")
        if self.using_library:
            target_address = self._current_target_address()
            self._sync_expected_ecu_address(target_address)
            self.client.send_diagnostic_to_address(
                target_address,
                build_request_transfer_exit(),
            )
            response = self._receive_raw_diagnostic()
            self._expect_positive_response(response, SID_REQUEST_TRANSFER_EXIT)
            return True

        return self._finish_download()

    def verify_programming(self):

        demo_log("[UDS] RoutineControl VerifyImage")
        if self.using_library:
            target_address = self._current_target_address()
            self._sync_expected_ecu_address(target_address)
            self.client.send_diagnostic_to_address(
                target_address,
                build_routine_control_start(ROUTINE_VERIFY_IMAGE),
            )
            response = self._receive_raw_diagnostic()
            self._expect_positive_response(response, SID_ROUTINE_CONTROL)
            return True
        return True

    def activate_image(self):

        demo_log("[UDS] RoutineControl ActivateImage")
        if self.using_library:
            target_address = self._current_target_address()
            self._sync_expected_ecu_address(target_address)
            self.client.send_diagnostic_to_address(
                target_address,
                build_routine_control_start(ROUTINE_ACTIVATE_IMAGE),
            )
            response = self._receive_raw_diagnostic()
            self._expect_positive_response(response, SID_ROUTINE_CONTROL)
            return True
        return True

    def ecu_reset(self):

        demo_log("[UDS] ECUReset")
        if self.using_library:
            target_address = self._current_target_address()
            self._sync_expected_ecu_address(target_address)
            self.client.send_diagnostic_to_address(
                target_address,
                build_ecu_reset(),
            )
            response = self._receive_raw_diagnostic()
            self._expect_positive_response(response, SID_ECU_RESET)
            return True
        return True

    def wait_for_boot(self, timeout=30.0):

        demo_log("[UDS] WaitForBoot")

        target_address = self._current_target_address()
        self._sync_expected_ecu_address(target_address)

        if self.using_library:
            import time

            target_version = self.current_package["target_version"]
            deadline = time.time() + timeout

            while time.time() < deadline:
                version = self.read_version_by_address(
                    target_address,
                    timeout=max(0.1, deadline - time.time()),
                )
                if version == target_version:
                    return True
                time.sleep(0.5)

            raise RuntimeError(
                f"Boot confirmation failed: version did not reach {target_version}"
            )

        #
        # Use an explicit health probe after reset so the demo confirms
        # the ECU is alive again instead of assuming success.
        #

        self.send_message(
            target_address,
            {
                "type": "HEALTH_CHECK",
            },
        )

        import time

        deadline = time.time() + timeout

        while time.time() < deadline:

            response = self.receive_message(timeout=max(0.1, deadline - time.time()))

            if response in ({"type": "INSTALL_COMPLETE"}, {"status": "ACK"}):
                continue

            if response == {"status": "HEALTHY"}:
                return True

        raise RuntimeError("Boot confirmation failed: timed out waiting for HEALTHY")

    # --------------------------------------------------------
    # Helper Methods
    # --------------------------------------------------------

    def _send_chunk(self, sequence, payload):
        """
        Existing implementation.

        Move the code that currently sends one firmware chunk
        into this function.
        """

        target_address = self._current_target_address()
        self._sync_expected_ecu_address(target_address)

        self.send_message(
            target_address,
            {
                "type": "FIRMWARE_CHUNK",
                "sequence": sequence,
                "payload": payload.hex(),
            },
        )

        return self._require_ack("TransferData")

    def _finish_download(self):
        """
        Existing FIRMWARE_END implementation.

        Move the current code that sends the
        final message into this function.
        """

        target_address = self._current_target_address()
        self._sync_expected_ecu_address(target_address)

        self.send_message(
            target_address,
            {
                "type": "FIRMWARE_END",
            },
        )

        if self.receive_message() != {"status": "ACK"}:
            raise RuntimeError("RequestTransferExit failed")

        return True

    # --------------------------------------------------------

    def shutdown(self):

        if self.client:

            self.client.close()

            self.client = None
