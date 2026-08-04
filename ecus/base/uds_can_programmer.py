import time
import threading

from ecus.base.installer import FirmwareInstaller
from ecus.base.runtime_control import load_runtime_control
from transport.can.isotp_adapter import IsoTpAdapter, IsoTpReassembler
from transport.uds.codec import (
    DID_SOFTWARE_VERSION,
    DEFAULT_SESSION_PROGRAMMING,
    NRC_CONDITIONS_NOT_CORRECT,
    NRC_EXCEED_NUMBER_OF_ATTEMPTS,
    NRC_INCORRECT_LENGTH_OR_FORMAT,
    NRC_INVALID_KEY,
    SID_DIAGNOSTIC_SESSION_CONTROL,
    SID_ECU_RESET,
    SID_READ_DATA_BY_IDENTIFIER,
    SID_ROUTINE_CONTROL,
    SID_SECURITY_ACCESS,
    SID_REQUEST_DOWNLOAD,
    SID_REQUEST_TRANSFER_EXIT,
    SID_TESTER_PRESENT,
    SID_TRANSFER_DATA,
    NRC_REQUEST_OUT_OF_RANGE,
    NRC_REQUEST_SEQUENCE_ERROR,
    ROUTINE_ACTIVATE_IMAGE,
    ROUTINE_CONTROL_START,
    ROUTINE_ERASE_MEMORY,
    ROUTINE_VERIFY_IMAGE,
    NRC_SECURITY_ACCESS_DENIED,
    NRC_SERVICE_NOT_SUPPORTED_IN_ACTIVE_SESSION,
    NRC_WRONG_BLOCK_SEQUENCE_COUNTER,
    SECURITY_ACCESS_REQUEST_SEED,
    SECURITY_ACCESS_SEND_KEY,
    NRC_RESPONSE_PENDING,
    positive_response_sid,
)
from transport.uds.security import derive_security_key


class UDSCanProgrammer:
    """
    Handles UDS programming services carried over ISO-TP/CAN FD.
    """

    ROUTINE_DELAY_SECONDS = 0.15
    VERIFY_DELAY_SECONDS = 0.15
    ACTIVATE_DELAY_SECONDS = 0.15
    # Flash programming runs for a long time and can legitimately pause while
    # the gateway, zone controller, or tester waits on transport retries.
    # Keep the programming session alive long enough for large OTA jobs.
    SESSION_TIMEOUT_SECONDS = 120.0
    SECURITY_ATTEMPT_LIMIT = 3
    SECURITY_LOCKOUT_SECONDS = 30.0

    def __init__(
        self,
        can_interface,
        ecu_id,
        ecu_key,
        version_manager,
        firmware_receiver,
        firmware_file,
        original_path,
        target_version,
    ):
        self.can = can_interface
        self.ecu_id = ecu_id
        self.ecu_key = ecu_key
        self.version_manager = version_manager
        self.receiver = firmware_receiver
        self.firmware_file = firmware_file
        self.original_path = original_path
        self.target_version = target_version
        self.reassembler = IsoTpReassembler()
        self.expected_size = 0
        self.received_size = 0
        self.install_pending = False
        self.install_started = False
        self.download_requested = False
        self.security_unlocked = False
        self.pending_seed = b""
        self.seed_counter = 0
        self.erase_completed = False
        self.activation_marked = False
        self.current_session = 0x00
        self.session_started_at = 0.0
        self.security_failures = 0
        self.security_locked_until = 0.0
        self.expected_transfer_sequence = 1

    def feed(self, message):
        frame = bytes(message.data)

        if not self._is_isotp_candidate(frame):
            return False

        payload = self.reassembler.feed(frame)
        flow_control = self.reassembler.pop_flow_control_frame()
        if flow_control is not None:
            self.can.send(
                IsoTpAdapter._wrap_frame(self.ecu_id, flow_control)
            )

        if payload is None:
            return True

        self._handle_uds(payload)
        return True

    @staticmethod
    def _is_isotp_candidate(frame):
        if not frame:
            return False

        frame_type = frame[0] >> 4

        if frame_type == 0x0:
            length = frame[0] & 0x0F
            if length == 0:
                return len(frame) >= 2 and len(frame) >= 2 + frame[1]
            return len(frame) >= 1 + length

        return frame_type in (0x1, 0x2)

    def _send(self, payload):
        adapter = IsoTpAdapter(self.can.bus)
        adapter.send(self.ecu_id, payload)

    def _negative(self, service_id, code):
        self._send(bytes([0x7F, service_id, code]))

    def _response_pending(self, service_id):
        self._send(bytes([0x7F, service_id, NRC_RESPONSE_PENDING]))

    def _reset_programming_state(self):
        self.security_unlocked = False
        self.pending_seed = b""
        self.erase_completed = False
        self.activation_marked = False
        self.install_pending = False
        self.install_started = False
        self.download_requested = False
        self.expected_size = 0
        self.received_size = 0
        self.expected_transfer_sequence = 1

    def _touch_session(self):
        self.session_started_at = time.monotonic()

    def _expire_session_if_needed(self):
        if self.current_session != DEFAULT_SESSION_PROGRAMMING:
            return
        if not self.session_started_at:
            return
        if (time.monotonic() - self.session_started_at) <= self.SESSION_TIMEOUT_SECONDS:
            return

        self.current_session = 0x00
        self._reset_programming_state()

    def _require_programming_session(self, service_id):
        self._expire_session_if_needed()
        if self.current_session != DEFAULT_SESSION_PROGRAMMING:
            self._negative(service_id, NRC_SERVICE_NOT_SUPPORTED_IN_ACTIVE_SESSION)
            return False
        self._touch_session()
        return True

    def _security_delay_active(self):
        return time.monotonic() < self.security_locked_until

    def _generate_seed(self):
        self.seed_counter = (self.seed_counter + 1) & 0xFFFFFFFF
        return (
            ((self.ecu_id & 0xFFFF) << 16) | self.seed_counter
        ).to_bytes(4, "big")

    def _handle_uds(self, payload):
        if not payload:
            return

        service_id = payload[0]
        control = load_runtime_control(self.ecu_key)
        if not control["diagnostics_enabled"]:
            self._negative(service_id, NRC_CONDITIONS_NOT_CORRECT)
            return

        programming_services = {
            SID_SECURITY_ACCESS,
            SID_ROUTINE_CONTROL,
            SID_REQUEST_DOWNLOAD,
            SID_TRANSFER_DATA,
            SID_REQUEST_TRANSFER_EXIT,
            SID_ECU_RESET,
        }
        if service_id in programming_services and not control["programming_enabled"]:
            self._negative(service_id, NRC_CONDITIONS_NOT_CORRECT)
            return

        if service_id == SID_DIAGNOSTIC_SESSION_CONTROL:
            session = payload[1] if len(payload) > 1 else 0x00
            self.current_session = session
            self._reset_programming_state()
            self._touch_session()
            self._send(bytes([positive_response_sid(service_id), session]))
            return

        if service_id == SID_TESTER_PRESENT:
            subfunction = payload[1] if len(payload) > 1 else 0x00
            self._expire_session_if_needed()
            if self.current_session == DEFAULT_SESSION_PROGRAMMING:
                self._touch_session()
            self._send(bytes([positive_response_sid(service_id), subfunction]))
            return

        if service_id == SID_READ_DATA_BY_IDENTIFIER:
            if len(payload) < 3:
                self._negative(service_id, 0x13)
                return

            did = int.from_bytes(payload[1:3], "big")
            if did != DID_SOFTWARE_VERSION:
                self._negative(service_id, 0x31)
                return

            version = self.version_manager.get_current_version().encode("utf-8")
            self._send(bytes([positive_response_sid(service_id)]) + payload[1:3] + version)
            return

        if service_id == SID_SECURITY_ACCESS:
            if not self._require_programming_session(service_id):
                return
            if len(payload) < 2:
                self._negative(service_id, NRC_INCORRECT_LENGTH_OR_FORMAT)
                return

            subfunction = payload[1]

            if subfunction == SECURITY_ACCESS_REQUEST_SEED:
                if self._security_delay_active():
                    self._negative(service_id, 0x37)
                    return
                self.pending_seed = self._generate_seed()
                self.security_unlocked = False
                self._send(
                    bytes([positive_response_sid(service_id), subfunction])
                    + self.pending_seed
                )
                return

            if subfunction == SECURITY_ACCESS_SEND_KEY:
                if not self.pending_seed:
                    self._negative(service_id, NRC_REQUEST_SEQUENCE_ERROR)
                    return

                expected_key = derive_security_key(self.pending_seed)
                if payload[2:] != expected_key:
                    self.security_unlocked = False
                    self.security_failures += 1
                    self.pending_seed = b""
                    if self.security_failures >= self.SECURITY_ATTEMPT_LIMIT:
                        self.security_locked_until = (
                            time.monotonic() + self.SECURITY_LOCKOUT_SECONDS
                        )
                        self._negative(service_id, NRC_EXCEED_NUMBER_OF_ATTEMPTS)
                        return
                    self._negative(service_id, NRC_INVALID_KEY)
                    return

                self.security_unlocked = True
                self.security_failures = 0
                self.pending_seed = b""
                self._send(bytes([positive_response_sid(service_id), subfunction]))
                return

            self._negative(service_id, 0x12)
            return

        if service_id == SID_ROUTINE_CONTROL:
            if not self._require_programming_session(service_id):
                return
            if len(payload) < 4:
                self._negative(service_id, NRC_INCORRECT_LENGTH_OR_FORMAT)
                return

            if not self.security_unlocked:
                self._negative(service_id, NRC_SECURITY_ACCESS_DENIED)
                return

            control_type = payload[1]
            routine_id = int.from_bytes(payload[2:4], "big")
            routine_data = payload[4:]

            if control_type != ROUTINE_CONTROL_START:
                self._negative(service_id, 0x12)
                return

            if routine_id == ROUTINE_ERASE_MEMORY:
                self._response_pending(service_id)
                time.sleep(self.ROUTINE_DELAY_SECONDS)
                self.receiver.clear()
                self.expected_size = int.from_bytes(routine_data[:4], "big") if len(routine_data) >= 4 else 0
                self.received_size = 0
                self.install_pending = False
                self.erase_completed = True
                self.activation_marked = False
                self.expected_transfer_sequence = 1
                self.receiver.set_expected_size(self.expected_size)
                self._send(
                    bytes([positive_response_sid(service_id), control_type]) + payload[2:4]
                )
                return

            if routine_id == ROUTINE_VERIFY_IMAGE:
                if not self.install_pending:
                    self._negative(service_id, 0x72)
                    return
                self._response_pending(service_id)
                time.sleep(self.VERIFY_DELAY_SECONDS)
                self._send(
                    bytes([positive_response_sid(service_id), control_type]) + payload[2:4]
                )
                return

            if routine_id == ROUTINE_ACTIVATE_IMAGE:
                if not self.install_pending:
                    self._negative(service_id, 0x72)
                    return
                self._response_pending(service_id)
                time.sleep(self.ACTIVATE_DELAY_SECONDS)
                self.activation_marked = True
                self._send(
                    bytes([positive_response_sid(service_id), control_type]) + payload[2:4]
                )
                return

            self._negative(service_id, 0x31)
            return

        if service_id == SID_REQUEST_DOWNLOAD:
            if not self._require_programming_session(service_id):
                return
            if not self.security_unlocked or not self.erase_completed:
                self._negative(service_id, NRC_CONDITIONS_NOT_CORRECT)
                return
            if len(payload) < 11:
                self._negative(service_id, NRC_INCORRECT_LENGTH_OR_FORMAT)
                return
            if payload[1] != 0x00 or payload[2] != 0x44:
                self._negative(service_id, NRC_REQUEST_OUT_OF_RANGE)
                return

            self.receiver.clear()
            self.expected_size = int.from_bytes(payload[-4:], "big")
            self.received_size = 0
            self.install_pending = False
            self.install_started = False
            self.download_requested = True
            self.expected_transfer_sequence = 1
            self.receiver.set_expected_size(self.expected_size)
            self._send(bytes([positive_response_sid(service_id), 0x00, 0x44, 0x00, 0x40]))
            return

        if service_id == SID_TRANSFER_DATA:
            if not self._require_programming_session(service_id):
                return
            if len(payload) < 2:
                self._negative(service_id, NRC_INCORRECT_LENGTH_OR_FORMAT)
                return

            if not self.security_unlocked:
                self._negative(service_id, NRC_SECURITY_ACCESS_DENIED)
                return
            if not self.download_requested:
                self._negative(service_id, NRC_REQUEST_SEQUENCE_ERROR)
                return

            sequence = payload[1]
            if sequence != (self.expected_transfer_sequence & 0xFF):
                self._negative(service_id, NRC_WRONG_BLOCK_SEQUENCE_COUNTER)
                return

            data = payload[2:]
            remaining = max(0, self.expected_size - self.received_size)
            chunk = data[:remaining]
            if not chunk and self.expected_size:
                self._negative(service_id, NRC_REQUEST_OUT_OF_RANGE)
                return
            self.receiver.buffer.extend(chunk)
            self.receiver.chunk_count += 1
            self.received_size += len(chunk)
            self.expected_transfer_sequence = (self.expected_transfer_sequence + 1) & 0xFF
            if self.expected_transfer_sequence == 0:
                self.expected_transfer_sequence = 0
            self._send(bytes([positive_response_sid(service_id), sequence]))
            return

        if service_id == SID_REQUEST_TRANSFER_EXIT:
            if not self._require_programming_session(service_id):
                return
            if not self.security_unlocked:
                self._negative(service_id, NRC_SECURITY_ACCESS_DENIED)
                return
            if not self.download_requested:
                self._negative(service_id, NRC_REQUEST_SEQUENCE_ERROR)
                return

            if self.expected_size and self.received_size != self.expected_size:
                self._negative(service_id, NRC_INCORRECT_LENGTH_OR_FORMAT)
                return

            self._response_pending(service_id)
            time.sleep(self.VERIFY_DELAY_SECONDS)
            self.receiver.save(self.firmware_file)
            passed, *_ = self.receiver.verify(self.original_path)
            self.install_pending = passed

            if passed:
                self.download_requested = False
                self._send(bytes([positive_response_sid(service_id)]))
            else:
                self._negative(service_id, 0x72)
            return

        if service_id == SID_ECU_RESET:
            if not self._require_programming_session(service_id):
                return
            reset_type = payload[1] if len(payload) > 1 else 0x01

            self._send(bytes([positive_response_sid(service_id), reset_type]))

            if (
                self.install_pending
                and self.activation_marked
                and not self.install_started
            ):
                self.install_started = True
                threading.Thread(
                    target=self._install,
                    daemon=True,
                ).start()

            self.current_session = 0x00
            self._reset_programming_state()
            return

        self._negative(service_id, 0x11)

    def _install(self):
        FirmwareInstaller.install(
            self.ecu_key,
            self.firmware_file,
            self.target_version,
        )
