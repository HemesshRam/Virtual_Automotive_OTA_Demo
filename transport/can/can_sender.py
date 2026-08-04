import time
import os
from pathlib import Path

from ecus.base.can_interface import CANInterface
from common.can_protocol import CANProtocol
from common.message_types import MessageType
from common.constants import ECU_CAN_INTERFACES, CAN_INTERFACE
from transport.can.frame_builder import FrameBuilder
from transport.can.isotp_adapter import IsoTpAdapter, IsoTpReassembler
from transport.uds.security import derive_security_key
from tcu.zone_availability_guard import ZoneAvailabilityGuard
from transport.uds.codec import (
    build_diagnostic_session_control,
    build_ecu_reset,
    build_read_data_by_identifier,
    build_routine_control_start,
    build_request_download,
    build_request_transfer_exit,
    build_security_access_request_seed,
    build_security_access_send_key,
    build_tester_present,
    build_transfer_data,
    is_negative_response,
    is_response_pending,
    nrc_name,
    positive_response_sid,
    SID_DIAGNOSTIC_SESSION_CONTROL,
    SID_ECU_RESET,
    SID_REQUEST_DOWNLOAD,
    SID_REQUEST_TRANSFER_EXIT,
    SID_ROUTINE_CONTROL,
    SID_SECURITY_ACCESS,
    SID_TESTER_PRESENT,
    SID_TRANSFER_DATA,
    SID_READ_DATA_BY_IDENTIFIER,
    ROUTINE_ERASE_MEMORY,
    ROUTINE_VERIFY_IMAGE,
    ROUTINE_ACTIVATE_IMAGE,
    parse_software_version,
)
from zones.zone_transport_client import ZoneTransportClient


class CANSender:

    # Production-style default for CAN FD flashing. ISO-TP segments below this.
    DEFAULT_TRANSFER_PAYLOAD = 1024
    DEFAULT_BOOT_CONFIRM_TIMEOUT = 120.0
    RESPONSE_TIMEOUT = 10.0
    RESPONSE_PENDING_TIMEOUT = 30.0

    def __init__(self):
        self._interfaces = {}
        self.current_ecu = None
        self.current_package = None
        self.zone_guard = ZoneAvailabilityGuard()
        self.zone_client = ZoneTransportClient()
        self._pending_zone_responses = []
        self.max_transfer_payload = int(
            os.getenv("OTA_VCAN_TRANSFER_PAYLOAD", str(self.DEFAULT_TRANSFER_PAYLOAD))
        )

    def shutdown(self):
        for can_interface in self._interfaces.values():
            can_interface.shutdown()

    def _channel_for(self, ecu):

        return (
            getattr(ecu, "can_channel", "")
            or ECU_CAN_INTERFACES.get(ecu.ecu_id)
            or CAN_INTERFACE
        )

    def _interface_for(self, ecu):

        channel = self._channel_for(ecu)

        if channel not in self._interfaces:
            self._interfaces[channel] = CANInterface(channel)

        return self._interfaces[channel]

    def _send_uds_request(self, ecu, payload):
        self.zone_guard.require_ecu_online(ecu.ecu_name)
        if self._use_zone_transport():
            logical_address = self._logical_address_for(ecu)
            self._pending_zone_responses = self.zone_client.forward_uds(
                logical_address,
                payload,
            )
            return

        can_interface = self._interface_for(ecu)
        IsoTpAdapter(can_interface.bus).send(ecu.ecu_id, payload)

    def _receive_uds_response(self, ecu, timeout=5.0, request_sid=None):
        if self._use_zone_transport():
            if self._pending_zone_responses:
                return self._pending_zone_responses.pop(0)
            raise TimeoutError("Timed out waiting for zonal UDS response")

        can_interface = self._interface_for(ecu)
        reassembler = IsoTpReassembler()
        start = time.time()

        while time.time() - start < timeout:
            rx = can_interface.receive(timeout=0.5)

            if rx is None:
                continue

            if rx.arbitration_id != ecu.ecu_id:
                continue

            payload = reassembler.feed(bytes(rx.data))
            if payload is not None and self._is_response_for_request(payload, request_sid):
                return payload

        raise TimeoutError("Timed out waiting for UDS response over ISO-TP")

    @staticmethod
    def _use_zone_transport() -> bool:
        if os.getenv("OTA_USE_ZONAL_CONTROLLERS", "0").lower() not in {
            "1",
            "true",
            "yes",
            "on",
        }:
            return False
        return os.getenv("OTA_ZONE_TRANSPORT", "").lower() == "tcp"

    @staticmethod
    def _logical_address_for(ecu) -> int:
        from vehicle.topology_loader import VehicleTopology

        registry = VehicleTopology().ecu_registry()
        return int(registry[ecu.ecu_name]["logical_address"])

    def _expect_positive_response(self, ecu, request_sid, timeout=None):

        response_timeout = timeout or self.RESPONSE_TIMEOUT
        deadline = time.time() + self.RESPONSE_PENDING_TIMEOUT

        while time.time() < deadline:
            response = self._receive_uds_response(
                ecu,
                timeout=response_timeout,
                request_sid=request_sid,
            )

            if is_response_pending(response, request_sid):
                continue

            if is_negative_response(response):
                nrc = response[2] if len(response) > 2 else 0x00
                raise RuntimeError(
                    f"UDS request 0x{request_sid:02X} rejected with "
                    f"NRC 0x{nrc:02X} ({nrc_name(nrc)})"
                )

            expected_sid = positive_response_sid(request_sid)
            if not response or response[0] != expected_sid:
                raise RuntimeError(
                    f"Unexpected UDS response for 0x{request_sid:02X}: {response.hex()}"
                )

            return response

        raise TimeoutError(
            f"Timed out waiting for final UDS response for 0x{request_sid:02X}"
        )

    @staticmethod
    def _is_response_for_request(payload: bytes, request_sid: int | None) -> bool:
        if request_sid is None:
            return payload is not None

        if not payload:
            return False

        if payload[0] == positive_response_sid(request_sid):
            return True

        return is_negative_response(payload) and len(payload) >= 3 and payload[1] == request_sid

    def send_message(self, ecu, message):
        """
        Translates a transport-agnostic OTA dictionary message
        into a CAN frame and sends it.
        """
        msg_type = message.get("type")
        ecu_id = ecu.ecu_id
        can_interface = self._interface_for(ecu)

        if msg_type == "FIRMWARE_START":
            size = int(message.get("size", 0))
            payload = (
                bytes([MessageType.FIRMWARE_START, 0x00])
                + size.to_bytes(4, "big")
            )
            frame = FrameBuilder.build(arbitration_id=ecu_id, payload=payload)
            can_interface.send(frame)

        elif msg_type == "FIRMWARE_CHUNK":
            seq = message["sequence"]
            data = bytes.fromhex(message["payload"])
            payload = bytes([MessageType.FIRMWARE_DATA, seq]) + data
            frame = FrameBuilder.build(arbitration_id=ecu_id, payload=payload)
            can_interface.send(frame)

        elif msg_type == "FIRMWARE_END":
            payload = bytes([MessageType.FIRMWARE_END, 0x00])
            frame = FrameBuilder.build(arbitration_id=ecu_id, payload=payload)
            can_interface.send(frame)

        elif msg_type == "HEALTH_CHECK":
            frame = CANProtocol.build_health_request(ecu_id)
            can_interface.send(frame)

        elif msg_type == "VERSION_REQUEST":
            frame = CANProtocol.build_version_request(ecu_id)
            can_interface.send(frame)

        else:
            print(f"[CANSender] Unknown message type: {msg_type}")

    def receive_message(self, ecu, timeout=2.0):
        """
        Waits for a CAN frame from the ECU and translates it
        back into an OTA dictionary message.
        """
        start = time.time()
        can_interface = self._interface_for(ecu)
        
        # We need a slightly longer wait for INSTALL_COMPLETE
        # It's passed in from Distributor if needed
        # (Though Distributor passes it via the timeout arg)
        
        while time.time() - start < timeout:

            rx = can_interface.receive(timeout=0.5)

            if rx is None:
                continue

            decoded = CANProtocol.parse_message(rx)

            if decoded["sender_id"] != ecu.ecu_id:
                continue

            msg_type = decoded["message_type"]

            if msg_type == MessageType.ACK:
                return {"status": "ACK"}

            elif msg_type == MessageType.INSTALL_COMPLETE:
                return {"type": "INSTALL_COMPLETE"}

            elif msg_type == MessageType.HEALTH_RESPONSE:
                return {"status": "HEALTHY"}

            elif msg_type == MessageType.VERSION_RESPONSE:
                major = decoded["version_major"]
                minor = decoded["version_minor"]
                return {"version": f"{major}.{minor}.0"}

        return None

    def _require_ack(self, operation, timeout=2.0):

        response = self.receive_message(
            self.current_ecu,
            timeout=timeout,
        )

        if response != {"status": "ACK"}:
            raise RuntimeError(f"{operation} failed: {response}")

        return True

    def diagnostic_session_control(self):

        self._send_uds_request(
            self.current_ecu,
            build_diagnostic_session_control(),
        )
        self._expect_positive_response(
            self.current_ecu,
            SID_DIAGNOSTIC_SESSION_CONTROL,
        )
        return True

    def tester_present(self):

        self._send_uds_request(
            self.current_ecu,
            build_tester_present(),
        )
        self._expect_positive_response(
            self.current_ecu,
            SID_TESTER_PRESENT,
        )
        return True

    def request_download(self, size):

        self._send_uds_request(
            self.current_ecu,
            build_request_download(size),
        )
        self._expect_positive_response(
            self.current_ecu,
            SID_REQUEST_DOWNLOAD,
        )
        return True

    def request_seed(self):

        self._send_uds_request(
            self.current_ecu,
            build_security_access_request_seed(),
        )
        response = self._expect_positive_response(
            self.current_ecu,
            SID_SECURITY_ACCESS,
        )
        return response[2:]

    def send_key(self, seed):

        key = derive_security_key(seed)
        self._send_uds_request(
            self.current_ecu,
            build_security_access_send_key(key=key),
        )
        self._expect_positive_response(
            self.current_ecu,
            SID_SECURITY_ACCESS,
        )
        return True

    def erase_memory(self, size):

        self._send_uds_request(
            self.current_ecu,
            build_routine_control_start(
                ROUTINE_ERASE_MEMORY,
                size.to_bytes(4, "big"),
            ),
        )
        self._expect_positive_response(
            self.current_ecu,
            SID_ROUTINE_CONTROL,
        )
        return True

    def transfer_data(self, seq, data):

        self._send_uds_request(
            self.current_ecu,
            build_transfer_data(seq, data),
        )
        self._expect_positive_response(
            self.current_ecu,
            SID_TRANSFER_DATA,
        )
        return True

    def request_transfer_exit(self):

        self._send_uds_request(
            self.current_ecu,
            build_request_transfer_exit(),
        )
        self._expect_positive_response(
            self.current_ecu,
            SID_REQUEST_TRANSFER_EXIT,
        )
        return True

    def verify_programming(self):

        self._send_uds_request(
            self.current_ecu,
            build_routine_control_start(ROUTINE_VERIFY_IMAGE),
        )
        self._expect_positive_response(
            self.current_ecu,
            SID_ROUTINE_CONTROL,
        )
        return True

    def activate_image(self):

        self._send_uds_request(
            self.current_ecu,
            build_routine_control_start(ROUTINE_ACTIVATE_IMAGE),
        )
        self._expect_positive_response(
            self.current_ecu,
            SID_ROUTINE_CONTROL,
        )
        return True

    def ecu_reset(self):

        self._send_uds_request(
            self.current_ecu,
            build_ecu_reset(),
        )
        self._expect_positive_response(
            self.current_ecu,
            SID_ECU_RESET,
            timeout=30.0,
        )
        return True

    def wait_for_boot(self, timeout=30.0):

        if self.current_ecu is None:
            raise RuntimeError("Current ECU is not set")

        timeout = float(
            os.getenv(
                "OTA_BOOT_CONFIRM_TIMEOUT_SECONDS",
                str(timeout or self.DEFAULT_BOOT_CONFIRM_TIMEOUT),
            )
        )
        start = time.time()
        target_version = self.current_package["target_version"]

        if self._use_zone_transport():
            while time.time() - start < timeout:
                try:
                    version = self.read_software_version(timeout=2.0)
                    if version == target_version:
                        return True
                except Exception:
                    local_version = self._read_local_ecu_version()
                    if local_version == target_version:
                        return True
                    time.sleep(0.5)
                    continue

                time.sleep(0.2)

            raise RuntimeError(
                "Boot confirmation failed: timed out waiting for UDS version confirmation"
            )

        while time.time() - start < timeout:
            self.send_message(
                self.current_ecu,
                {
                    "type": "HEALTH_CHECK",
                }
            )

            response = self.receive_message(
                self.current_ecu,
                timeout=0.5,
            )

            if response in ({"type": "INSTALL_COMPLETE"}, {"status": "ACK"}):
                continue

            if response == {"status": "HEALTHY"}:
                version = self.read_software_version(timeout=2.0)
                if version == target_version:
                    return True

            time.sleep(0.2)

        raise RuntimeError("Boot confirmation failed: timed out waiting for HEALTHY")

    def read_software_version(self, timeout=5.0):

        self._send_uds_request(
            self.current_ecu,
            build_read_data_by_identifier(),
        )
        response = self._expect_positive_response(
            self.current_ecu,
            SID_READ_DATA_BY_IDENTIFIER,
            timeout=timeout,
        )
        return parse_software_version(response)

    def _read_local_ecu_version(self) -> str:
        if self.current_ecu is None:
            return ""

        ecu_key = getattr(self.current_ecu, "name", "") or getattr(self.current_ecu, "ecu_name", "")
        ecu_key = str(ecu_key).strip().lower().replace(" ecu", "")
        if not ecu_key:
            return ""

        version_path = Path("ecus") / ecu_key / "version.json"
        if not version_path.exists():
            return ""

        try:
            import json

            with open(version_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            return str(data.get("current_version", "")).strip()
        except Exception:
            return ""
