import os
import socket
import struct
import threading
import time

from common.constants import (
    GATEWAY_ID,
    BCM_ID,
    CLUSTER_ID,
    ECU_CAN_INTERFACES,
)
from common.message_types import MessageType
from common.logical_addresses import (
    GATEWAY_ADDRESS,
    BCM_ADDRESS,
    CLUSTER_ADDRESS,
)
from ecus.base.can_interface import CANInterface
from ecus.base.installer import FirmwareInstaller
from ecus.gateway.ecu_context import ECUContext
from transport.can.isotp_adapter import IsoTpAdapter, IsoTpReassembler
from transport.uds.codec import (
    DEFAULT_SESSION_PROGRAMMING,
    DID_SOFTWARE_VERSION,
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
    SID_TRANSFER_DATA,
    SID_TESTER_PRESENT,
    NRC_REQUEST_OUT_OF_RANGE,
    NRC_REQUEST_SEQUENCE_ERROR,
    ROUTINE_ACTIVATE_IMAGE,
    ROUTINE_CONTROL_START,
    ROUTINE_ERASE_MEMORY,
    ROUTINE_VERIFY_IMAGE,
    NRC_REQUIRED_TIME_DELAY_NOT_EXPIRED,
    SECURITY_ACCESS_REQUEST_SEED,
    SECURITY_ACCESS_SEND_KEY,
    NRC_SECURITY_ACCESS_DENIED,
    NRC_SERVICE_NOT_SUPPORTED_IN_ACTIVE_SESSION,
    NRC_WRONG_BLOCK_SEQUENCE_COUNTER,
    NRC_RESPONSE_PENDING,
    is_negative_response,
    is_response_pending,
    positive_response_sid,
)
from transport.uds.security import derive_security_key

from .message import OTAApplicationMessage
from .packet import (
    parse_packet,
    parse_diagnostic_payload,
    build_packet,
    build_diagnostic_packet,
    extract_packets,
)
from .protocol import (
    VEHICLE_IDENT_REQUEST,
    VEHICLE_IDENT_RESPONSE,
    ROUTING_ACTIVATION_REQUEST,
    ROUTING_ACTIVATION_RESPONSE,
    DIAGNOSTIC_MESSAGE,
    ALIVE_CHECK_REQUEST,
    ALIVE_CHECK_RESPONSE,
)

HOST = "0.0.0.0"
ALLOW_LEGACY_JSON_ENV = "OTA_DOIP_ALLOW_LEGACY_JSON"


class DoIPServer:

    ROUTINE_DELAY_SECONDS = 0.15
    VERIFY_DELAY_SECONDS = 0.15
    ACTIVATE_DELAY_SECONDS = 0.15
    # Flash programming runs for a long time and can legitimately pause while
    # the gateway, zone controller, or tester waits on transport retries.
    # Keep the programming session alive long enough for large OTA jobs.
    SESSION_TIMEOUT_SECONDS = 120.0
    SECURITY_ATTEMPT_LIMIT = 3
    SECURITY_LOCKOUT_SECONDS = 30.0
    CAN_RESPONSE_TIMEOUT_SECONDS = 5.0
    GATEWAY_REQUEST_DOWNLOAD_BLOCK_LENGTH = min(
        int(os.getenv("OTA_DOIP_GATEWAY_BLOCK_LENGTH", "8192")),
        16384,
    )
    GATEWAY_PROXY_FLASH_ENABLED = os.getenv(
        "OTA_DOIP_GATEWAY_PROXY_FLASH",
        "1",
    ).lower() in {"1", "true", "yes", "on"}

    def __init__(self, ecu_name, port=13400):

        self.ecu_name = ecu_name
        self.port = port
        self.allow_legacy_ota_payloads = os.getenv(ALLOW_LEGACY_JSON_ENV, "0") == "1"
        self.ecus = {
            GATEWAY_ADDRESS: ECUContext(
                "gateway",
                "Gateway ECU",
                GATEWAY_ADDRESS,
                self._profile("Gateway ECU"),
            ),
            BCM_ADDRESS: ECUContext(
                "bcm",
                "BCM ECU",
                BCM_ADDRESS,
                self._profile("BCM ECU"),
            ),
            CLUSTER_ADDRESS: ECUContext(
                "cluster",
                "Cluster ECU",
                CLUSTER_ADDRESS,
                self._profile("Cluster ECU"),
            ),
        }
        self._transfer_chunk_counters = {}

        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        self.server.bind((HOST, self.port))

        self.server.listen(5)
        self.udp_server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.udp_server.bind((HOST, self.port))
        self._can_interfaces = {}
        self.use_zonal_controllers = os.getenv("OTA_USE_ZONAL_CONTROLLERS", "0") == "1"
        self.zone_transport = os.getenv("OTA_ZONE_TRANSPORT", "in_process").lower()
        self.zone_router = None
        if self.use_zonal_controllers:
            if self.zone_transport == "tcp":
                from zones.zone_transport_client import ZoneTransportClient

                self.zone_router = ZoneTransportClient()
                print("Zonal routing enabled via TCP zone services")
            else:
                from zones.zone_router import ZoneRouter

                self.zone_router = ZoneRouter()
                print("Zonal routing enabled in-process")
        self._routes = {
            GATEWAY_ADDRESS: {
                "ecu_name": "Gateway ECU",
                "can_id": GATEWAY_ID,
                "channel": ECU_CAN_INTERFACES[GATEWAY_ID],
            },
            BCM_ADDRESS: {
                "ecu_name": "BCM ECU",
                "can_id": BCM_ID,
                "channel": ECU_CAN_INTERFACES[BCM_ID],
            },
            CLUSTER_ADDRESS: {
                "ecu_name": "Cluster ECU",
                "can_id": CLUSTER_ID,
                "channel": ECU_CAN_INTERFACES[CLUSTER_ID],
            },
        }

    @staticmethod
    def _generate_seed(ecu):
        ecu.seed_counter = (getattr(ecu, "seed_counter", 0) + 1) & 0xFFFFFFFF
        return (
            ((ecu.logical_address & 0xFFFF) << 16) | ecu.seed_counter
        ).to_bytes(4, "big")

    @staticmethod
    def _reset_programming_state(ecu):
        ecu.security_unlocked = False
        ecu.pending_seed = b""
        ecu.erase_completed = False
        ecu.activation_marked = False
        ecu.install_pending = False
        ecu.expected_download_size = 0
        ecu.download_received_size = 0
        ecu.expected_transfer_sequence = 1

    @staticmethod
    def _touch_session(ecu):
        ecu.session_started_at = time.monotonic()

    def _expire_session_if_needed(self, ecu):
        if getattr(ecu, "current_session", 0x00) != DEFAULT_SESSION_PROGRAMMING:
            return
        if not getattr(ecu, "session_started_at", 0.0):
            return
        if (time.monotonic() - ecu.session_started_at) <= self.SESSION_TIMEOUT_SECONDS:
            return

        ecu.current_session = 0x00
        self._reset_programming_state(ecu)

    def _require_programming_session(self, client, ecu, source_address, service_id):
        self._expire_session_if_needed(ecu)
        if getattr(ecu, "current_session", 0x00) != DEFAULT_SESSION_PROGRAMMING:
            self._send_raw_uds_response(
                client,
                ecu,
                source_address,
                bytes([0x7F, service_id, NRC_SERVICE_NOT_SUPPORTED_IN_ACTIVE_SESSION]),
            )
            return False

        self._touch_session(ecu)
        return True

    def start(self):

        print("\n===================================")
        print("DOIP SERVER")
        print("===================================")
        print(f"{self.ecu_name} listening on {HOST}:{self.port}")
        print("ECU Contexts")

        for address, ecu in self.ecus.items():
            print(
                f"  {hex(address)} -> "
                f"{ecu.ecu_name} "
                f"({ecu.profile['download_directory']})"
            )

        threading.Thread(
            target=self._serve_udp_vehicle_identification,
            daemon=True,
        ).start()

        while True:

            client, address = self.server.accept()

            print(f"\nConnection from {address}")

            threading.Thread(
                target=self.handle_client,
                args=(client,),
                daemon=True
            ).start()

    def _serve_udp_vehicle_identification(self):
        while True:
            try:
                data, address = self.udp_server.recvfrom(4096)
                payload_type, payload = parse_packet(data)
            except Exception:
                continue

            if payload_type != VEHICLE_IDENT_REQUEST:
                continue

            print(f"\nVehicle Identification Request (UDP) from {address}")
            self.udp_server.sendto(
                self._build_vehicle_identification_response(),
                address,
            )
            print("Vehicle Identification Response Sent (UDP)")

    def handle_client(self, client):

        buffer = bytearray()

        while True:

            data = client.recv(65536)

            if not data:
                break

            buffer.extend(data)

            try:
                packets = extract_packets(buffer)
            except ValueError as exc:
                print(f"Invalid DoIP packet stream: {exc}")
                break

            for payload_type, payload in packets:
                self.process(client, payload_type, payload)

        client.close()

    def process(self, client, payload_type, payload):

        if payload_type == VEHICLE_IDENT_REQUEST:

            print("\nVehicle Identification Request")
            client.sendall(self._build_vehicle_identification_response())

            print("Vehicle Identification Response Sent")

        elif payload_type == ROUTING_ACTIVATION_REQUEST:

            print("\nRouting Activation Request")

            #
            # Parse the tester's source address from the request
            #

            tester_address = struct.unpack("!H", payload[:2])[0]

            #
            # ISO 13400 Routing Activation Response
            # Client Address (2B) + Entity Address (2B) +
            # Response Code (1B) + Reserved (4B)
            #

            response_payload = struct.pack(
                "!HHBL",
                tester_address,      # Client logical address
                GATEWAY_ADDRESS,     # DoIP entity logical address
                0x10,                # Success
                0x00000000,          # Reserved
            )

            response = build_packet(
                ROUTING_ACTIVATION_RESPONSE,
                response_payload
            )

            client.sendall(response)

            print("Routing Activation Accepted")

        elif payload_type == ALIVE_CHECK_REQUEST:

            print("Alive Check")

            response = build_packet(
                ALIVE_CHECK_RESPONSE,
                b"\x00"
            )

            client.sendall(response)

        elif payload_type == DIAGNOSTIC_MESSAGE:

            (
                source_address,
                target_address,
                diagnostic_payload,
            ) = parse_diagnostic_payload(payload)

            print()
            print("=" * 60)
            print("DOIP DIAGNOSTIC MESSAGE")
            print("=" * 60)
            print(f"Source Address : {hex(source_address)}")
            print(f"Target Address : {hex(target_address)}")
            request_sid = diagnostic_payload[0] if diagnostic_payload else None

            route = self._routes.get(target_address)
            if route is None:
                print(f"Unknown Logical Address : {hex(target_address)}")
                return

            if self._is_raw_uds_payload(diagnostic_payload):
                ecu = self.ecus.get(target_address)
                if ecu is None:
                    print(f"Unknown ECU context for logical address {hex(target_address)}")
                    return

                if self.GATEWAY_PROXY_FLASH_ENABLED:
                    handled = self._handle_raw_uds_message(
                        client,
                        ecu,
                        source_address,
                        diagnostic_payload,
                    )
                    if handled:
                        return

                try:
                    if self.use_zonal_controllers and self.zone_router is not None:
                        response_payloads = self.zone_router.forward_uds(
                            target_address,
                            diagnostic_payload,
                        )
                    else:
                        response_payloads = self._forward_uds_over_can(
                            target_address,
                            diagnostic_payload,
                        )
                except Exception as exc:
                    print(f"Gateway forwarding failed: {exc}")
                    return

                for response_payload in response_payloads:
                    if request_sid == SID_REQUEST_DOWNLOAD:
                        response_payload = self._rewrite_request_download_response(
                            response_payload
                        )
                    self._send_forwarded_uds_response(
                        client,
                        target_address,
                        source_address,
                        response_payload,
                    )
                return

            ecu = self.ecus.get(target_address)
            if ecu is None:
                print("Raw UDS forwarding unavailable and no legacy ECU context found")
                return

            if not self.allow_legacy_ota_payloads:
                print(
                    "Rejected non-UDS DoIP diagnostic payload. "
                    f"Set {ALLOW_LEGACY_JSON_ENV}=1 only for legacy demo mode."
                )
                return

            try:
                message = OTAApplicationMessage.decode(
                    diagnostic_payload
                )
            except Exception:
                print("Unable to decode diagnostic payload")
                return

            self.handle_ota_message(
                client,
                ecu,
                source_address,
                message,
            )

        else:

            print(f"Unknown Payload Type : {hex(payload_type)}")

    @staticmethod
    def _build_vehicle_identification_response():
        #
        # ISO 13400 Vehicle Identification Response
        # VIN (17B) + Logical Address (2B) + EID (6B) +
        # GID (6B) + Further Action (1B)
        #
        vin = b"TESTVIN1234567890"
        logical_address = struct.pack("!H", GATEWAY_ADDRESS)
        eid = b"\x00" * 6
        gid = b"\x00" * 6
        further_action = b"\x00"

        return build_packet(
            VEHICLE_IDENT_RESPONSE,
            vin + logical_address + eid + gid + further_action,
        )

    @staticmethod
    def _is_raw_uds_payload(payload: bytes) -> bool:
        if not payload:
            return False
        service_id = payload[0]
        return service_id in {
            SID_DIAGNOSTIC_SESSION_CONTROL,
            SID_ECU_RESET,
            SID_READ_DATA_BY_IDENTIFIER,
            SID_ROUTINE_CONTROL,
            SID_SECURITY_ACCESS,
            SID_REQUEST_DOWNLOAD,
            SID_REQUEST_TRANSFER_EXIT,
            SID_TRANSFER_DATA,
            SID_TESTER_PRESENT,
        }

    def _can_interface_for(self, logical_address: int):
        route = self._routes[logical_address]
        channel = route["channel"]
        if channel not in self._can_interfaces:
            self._can_interfaces[channel] = CANInterface(channel)
        return self._can_interfaces[channel]

    def _forward_uds_over_can(self, logical_address: int, payload: bytes) -> list[bytes]:
        route = self._routes[logical_address]
        can_interface = self._can_interface_for(logical_address)
        IsoTpAdapter(can_interface.bus).send(route["can_id"], payload)

        deadline = time.time() + self.CAN_RESPONSE_TIMEOUT_SECONDS
        request_sid = payload[0] if payload else None
        responses: list[bytes] = []
        reassembler = IsoTpReassembler()

        while time.time() < deadline:
            response = can_interface.receive(timeout=max(0.05, deadline - time.time()))
            if response is None:
                continue
            if response.arbitration_id != route["can_id"]:
                continue

            assembled = reassembler.feed(bytes(response.data))
            if assembled is not None:
                if not self._is_response_for_request(assembled, request_sid):
                    continue
                responses.append(assembled)
                if request_sid is not None and is_response_pending(assembled, request_sid):
                    continue
                return responses

        raise TimeoutError(
            f"Timed out waiting for CAN response from {route['ecu_name']}"
        )

    @staticmethod
    def _is_response_for_request(payload: bytes, request_sid: int | None) -> bool:
        if request_sid is None or not payload:
            return False

        if payload[0] == positive_response_sid(request_sid):
            return True

        return is_negative_response(payload) and len(payload) >= 3 and payload[1] == request_sid

    def _send_forwarded_uds_response(self, client, source_logical_address, tester_address, payload):
        ack_payload = struct.pack(
            "!HHB",
            source_logical_address,
            tester_address,
            0x00,
        )

        try:
            client.sendall(build_packet(0x8002, ack_payload))
            client.sendall(
                build_diagnostic_packet(
                    source_address=source_logical_address,
                    target_address=tester_address,
                    payload=payload,
                )
            )
        except (BrokenPipeError, ConnectionResetError):
            print("Client disconnected before forwarded diagnostic response could be sent")

    def _rewrite_request_download_response(self, payload: bytes) -> bytes:
        if not payload:
            return payload
        if payload[0] != positive_response_sid(SID_REQUEST_DOWNLOAD):
            return payload
        if len(payload) < 5:
            return payload

        block_length = self.GATEWAY_REQUEST_DOWNLOAD_BLOCK_LENGTH
        return bytes([payload[0], payload[1], payload[2]]) + block_length.to_bytes(2, "big")

    def handle_ota_message(
        self,
        client,
        ecu,
        source_address,
        message,
    ):

        print("\n==============================")
        print("OTA MESSAGE")
        print("==============================")

        print(message)
        print(f"Routing : {ecu.ecu_name}")

        if message.get("type") == "FIRMWARE_END":
            self._handle_firmware_end(
                client,
                ecu,
                source_address,
            )
            return

        response = self._response_for(
            ecu,
            message,
        )

        self._send_ota_response(client, ecu, source_address, response)

    def _send_ota_response(self, client, ecu, tester_address, response):

        #
        # ISO 13400 requires a DiagnosticMessagePositiveAcknowledgement
        # (0x8002) before sending the actual diagnostic response.
        # Format: Source(2B) + Target(2B) + AckCode(1B)
        #

        ack_payload = struct.pack(
            "!HHB",
            ecu.logical_address, # Source (responding ECU)
            tester_address,      # Target (original sender / tester)
            0x00,                # ACK code
        )

        ack_packet = build_packet(0x8002, ack_payload)

        try:
            client.sendall(ack_packet)
        except (BrokenPipeError, ConnectionResetError):
            print("Client disconnected before ACK could be sent")
            return

        #
        # Now send the actual diagnostic response
        #

        packet = build_diagnostic_packet(
            source_address=ecu.logical_address,
            target_address=tester_address,
            payload=OTAApplicationMessage.encode(response),
        )

        try:
            client.sendall(packet)
        except (BrokenPipeError, ConnectionResetError):
            print("Client disconnected before diagnostic response could be sent")

    def _send_raw_uds_response(self, client, ecu, tester_address, payload):

        ack_payload = struct.pack(
            "!HHB",
            ecu.logical_address,
            tester_address,
            0x00,
        )

        try:
            client.sendall(build_packet(0x8002, ack_payload))
        except (BrokenPipeError, ConnectionResetError):
            print("Client disconnected before ACK could be sent")
            return

        try:
            client.sendall(
                build_diagnostic_packet(
                    source_address=ecu.logical_address,
                    target_address=tester_address,
                    payload=payload,
                )
            )
        except (BrokenPipeError, ConnectionResetError):
            print("Client disconnected before diagnostic response could be sent")

    def _send_response_pending(self, client, ecu, tester_address, service_id):
        self._send_raw_uds_response(
            client,
            ecu,
            tester_address,
            bytes([0x7F, service_id, NRC_RESPONSE_PENDING]),
        )

    def _handle_raw_uds_message(self, client, ecu, source_address, payload):

        if not payload:
            return False

        service_id = payload[0]

        if service_id == SID_DIAGNOSTIC_SESSION_CONTROL:
            session = payload[1] if len(payload) > 1 else 0x00
            ecu.current_session = session
            self._reset_programming_state(ecu)
            self._touch_session(ecu)
            print(f"UDS DiagnosticSessionControl session=0x{session:02X}")
            self._send_raw_uds_response(
                client,
                ecu,
                source_address,
                bytes([positive_response_sid(service_id), session]),
            )
            return True

        if service_id == SID_TESTER_PRESENT:
            subfunction = payload[1] if len(payload) > 1 else 0x00
            self._expire_session_if_needed(ecu)
            if getattr(ecu, "current_session", 0x00) == DEFAULT_SESSION_PROGRAMMING:
                self._touch_session(ecu)
            print(f"UDS TesterPresent subfunction=0x{subfunction:02X}")
            self._send_raw_uds_response(
                client,
                ecu,
                source_address,
                bytes([positive_response_sid(service_id), subfunction]),
            )
            return True

        if service_id == SID_READ_DATA_BY_IDENTIFIER:
            if len(payload) < 3:
                self._send_raw_uds_response(
                    client,
                    ecu,
                    source_address,
                    bytes([0x7F, service_id, 0x13]),
                )
                return True

            did = int.from_bytes(payload[1:3], "big")
            print(f"UDS ReadDataByIdentifier did=0x{did:04X}")

            if did == DID_SOFTWARE_VERSION:
                version = ecu.version_manager.get_current_version().encode("utf-8")
                response = bytes([positive_response_sid(service_id)]) + payload[1:3] + version
                self._send_raw_uds_response(client, ecu, source_address, response)
                return True

            self._send_raw_uds_response(
                client,
                ecu,
                source_address,
                bytes([0x7F, service_id, 0x31]),
            )
            return True

        if service_id == SID_SECURITY_ACCESS:
            if not self._require_programming_session(client, ecu, source_address, service_id):
                return True
            if len(payload) < 2:
                self._send_raw_uds_response(
                    client,
                    ecu,
                    source_address,
                    bytes([0x7F, service_id, NRC_INCORRECT_LENGTH_OR_FORMAT]),
                )
                return True

            subfunction = payload[1]
            print(f"UDS SecurityAccess subfunction=0x{subfunction:02X}")

            if subfunction == SECURITY_ACCESS_REQUEST_SEED:
                if time.monotonic() < getattr(ecu, "security_locked_until", 0.0):
                    self._send_raw_uds_response(
                        client,
                        ecu,
                        source_address,
                        bytes([0x7F, service_id, NRC_REQUIRED_TIME_DELAY_NOT_EXPIRED]),
                    )
                    return True
                ecu.pending_seed = self._generate_seed(ecu)
                ecu.security_unlocked = False
                self._send_raw_uds_response(
                    client,
                    ecu,
                    source_address,
                    bytes([positive_response_sid(service_id), subfunction]) + ecu.pending_seed,
                )
                return True

            if subfunction == SECURITY_ACCESS_SEND_KEY:
                if not getattr(ecu, "pending_seed", b""):
                    self._send_raw_uds_response(
                        client,
                        ecu,
                        source_address,
                        bytes([0x7F, service_id, NRC_REQUEST_SEQUENCE_ERROR]),
                    )
                    return True

                expected_key = derive_security_key(ecu.pending_seed)
                if payload[2:] != expected_key:
                    ecu.security_unlocked = False
                    ecu.security_failures = getattr(ecu, "security_failures", 0) + 1
                    ecu.pending_seed = b""
                    if ecu.security_failures >= self.SECURITY_ATTEMPT_LIMIT:
                        ecu.security_locked_until = (
                            time.monotonic() + self.SECURITY_LOCKOUT_SECONDS
                        )
                        self._send_raw_uds_response(
                            client,
                            ecu,
                            source_address,
                            bytes([0x7F, service_id, NRC_EXCEED_NUMBER_OF_ATTEMPTS]),
                        )
                        return True
                    self._send_raw_uds_response(
                        client,
                        ecu,
                        source_address,
                        bytes([0x7F, service_id, NRC_INVALID_KEY]),
                    )
                    return True

                ecu.security_unlocked = True
                ecu.security_failures = 0
                ecu.pending_seed = b""
                self._send_raw_uds_response(
                    client,
                    ecu,
                    source_address,
                    bytes([positive_response_sid(service_id), subfunction]),
                )
                return True

            self._send_raw_uds_response(
                client,
                ecu,
                source_address,
                bytes([0x7F, service_id, 0x12]),
            )
            return True

        if service_id == SID_ROUTINE_CONTROL:
            if not self._require_programming_session(client, ecu, source_address, service_id):
                return True
            if len(payload) < 4:
                self._send_raw_uds_response(
                    client,
                    ecu,
                    source_address,
                    bytes([0x7F, service_id, NRC_INCORRECT_LENGTH_OR_FORMAT]),
                )
                return True

            if not getattr(ecu, "security_unlocked", False):
                self._send_raw_uds_response(
                    client,
                    ecu,
                    source_address,
                    bytes([0x7F, service_id, NRC_SECURITY_ACCESS_DENIED]),
                )
                return True

            control_type = payload[1]
            routine_id = int.from_bytes(payload[2:4], "big")
            routine_data = payload[4:]
            print(
                f"UDS RoutineControl control=0x{control_type:02X} "
                f"routine=0x{routine_id:04X}"
            )

            if control_type != ROUTINE_CONTROL_START:
                self._send_raw_uds_response(
                    client,
                    ecu,
                    source_address,
                    bytes([0x7F, service_id, 0x12]),
                )
                return True

            if routine_id == ROUTINE_ERASE_MEMORY:
                self._send_response_pending(client, ecu, source_address, service_id)
                time.sleep(self.ROUTINE_DELAY_SECONDS)
                ecu.receiver.clear()
                ecu.expected_download_size = (
                    int.from_bytes(routine_data[:4], "big")
                    if len(routine_data) >= 4
                    else 0
                )
                ecu.download_received_size = 0
                ecu.download_verified = False
                ecu.install_pending = False
                ecu.install_started = False
                ecu.erase_completed = True
                ecu.activation_marked = False
                ecu.expected_transfer_sequence = 1
                print(f"Erase prepared for {ecu.expected_download_size} bytes")
                self._send_raw_uds_response(
                    client,
                    ecu,
                    source_address,
                    bytes([positive_response_sid(service_id), control_type]) + payload[2:4],
                )
                return True

            if routine_id == ROUTINE_VERIFY_IMAGE:
                if not getattr(ecu, "install_pending", False):
                    self._send_raw_uds_response(
                        client,
                        ecu,
                        source_address,
                        bytes([0x7F, service_id, 0x72]),
                    )
                    return True

                self._send_response_pending(client, ecu, source_address, service_id)
                time.sleep(self.VERIFY_DELAY_SECONDS)
                self._send_raw_uds_response(
                    client,
                    ecu,
                    source_address,
                    bytes([positive_response_sid(service_id), control_type]) + payload[2:4],
                )
                return True

            if routine_id == ROUTINE_ACTIVATE_IMAGE:
                if not getattr(ecu, "install_pending", False):
                    self._send_raw_uds_response(
                        client,
                        ecu,
                        source_address,
                        bytes([0x7F, service_id, 0x72]),
                    )
                    return True

                self._send_response_pending(client, ecu, source_address, service_id)
                time.sleep(self.ACTIVATE_DELAY_SECONDS)
                ecu.activation_marked = True
                self._send_raw_uds_response(
                    client,
                    ecu,
                    source_address,
                    bytes([positive_response_sid(service_id), control_type]) + payload[2:4],
                )
                return True

            self._send_raw_uds_response(
                client,
                ecu,
                source_address,
                bytes([0x7F, service_id, 0x31]),
            )
            return True

        if service_id == SID_REQUEST_DOWNLOAD:
            print("UDS RequestDownload")
            if not self._require_programming_session(client, ecu, source_address, service_id):
                return True
            if not getattr(ecu, "security_unlocked", False) or not getattr(ecu, "erase_completed", False):
                self._send_raw_uds_response(
                    client,
                    ecu,
                    source_address,
                    bytes([0x7F, service_id, NRC_CONDITIONS_NOT_CORRECT]),
                )
                return True
            ecu.receiver.clear()
            ecu.expected_download_size = int.from_bytes(payload[-4:], "big")
            ecu.download_received_size = 0
            ecu.download_verified = False
            ecu.install_pending = False
            ecu.install_started = False
            ecu.target_version = ecu.profile["target_version"]
            ecu.expected_transfer_sequence = 1
            self._transfer_chunk_counters[ecu.logical_address] = 0
            print(f"Expected Download Size : {ecu.expected_download_size:,} bytes")
            self._send_raw_uds_response(
                client,
                ecu,
                source_address,
                bytes([positive_response_sid(service_id), 0x00, 0x44])
                + self.GATEWAY_REQUEST_DOWNLOAD_BLOCK_LENGTH.to_bytes(2, "big"),
            )
            return True

        if service_id == SID_TRANSFER_DATA:
            if not self._require_programming_session(client, ecu, source_address, service_id):
                return True
            if len(payload) < 2:
                self._send_raw_uds_response(
                    client,
                    ecu,
                    source_address,
                    bytes([0x7F, service_id, NRC_INCORRECT_LENGTH_OR_FORMAT]),
                )
                return True

            if not getattr(ecu, "security_unlocked", False):
                self._send_raw_uds_response(
                    client,
                    ecu,
                    source_address,
                    bytes([0x7F, service_id, NRC_SECURITY_ACCESS_DENIED]),
                )
                return True

            sequence = payload[1]
            if sequence != (getattr(ecu, "expected_transfer_sequence", 1) & 0xFF):
                self._send_raw_uds_response(
                    client,
                    ecu,
                    source_address,
                    bytes([0x7F, service_id, NRC_WRONG_BLOCK_SEQUENCE_COUNTER]),
                )
                return True
            data = payload[2:]
            remaining = max(0, ecu.expected_download_size - ecu.download_received_size)
            if remaining == 0:
                trimmed = b""
            else:
                trimmed = data[:remaining]

            if not trimmed and ecu.expected_download_size:
                self._send_raw_uds_response(
                    client,
                    ecu,
                    source_address,
                    bytes([0x7F, service_id, NRC_REQUEST_OUT_OF_RANGE]),
                )
                return True

            ecu.receiver.buffer.extend(trimmed)
            ecu.download_received_size += len(trimmed)
            ecu.receiver.chunk_count += 1
            ecu.expected_transfer_sequence = (
                getattr(ecu, "expected_transfer_sequence", 1) + 1
            ) & 0xFF
            # Throttle per-chunk logging for large transfers
            chunk_num = self._transfer_chunk_counters.get(ecu.logical_address, 0) + 1
            self._transfer_chunk_counters[ecu.logical_address] = chunk_num
            total_expected = ecu.expected_download_size
            if total_expected > 1_000_000:
                if chunk_num == 1 or chunk_num % 1000 == 0:
                    print(
                        f"UDS TransferData chunk={chunk_num:,} seq={sequence} "
                        f"bytes={len(trimmed)} "
                        f"({ecu.download_received_size:,}/{total_expected:,})"
                    )
            else:
                print(
                    f"UDS TransferData seq={sequence} bytes={len(trimmed)} "
                    f"(raw={len(data)})"
                )
            self._send_raw_uds_response(
                client,
                ecu,
                source_address,
                bytes([positive_response_sid(service_id), sequence]),
            )
            return True

        if service_id == SID_REQUEST_TRANSFER_EXIT:
            print("UDS RequestTransferExit")
            if not self._require_programming_session(client, ecu, source_address, service_id):
                return True
            if not getattr(ecu, "security_unlocked", False):
                self._send_raw_uds_response(
                    client,
                    ecu,
                    source_address,
                    bytes([0x7F, service_id, NRC_SECURITY_ACCESS_DENIED]),
                )
                return True
            if ecu.expected_download_size and ecu.download_received_size != ecu.expected_download_size:
                print(
                    "Download length mismatch: "
                    f"expected {ecu.expected_download_size}, "
                    f"received {ecu.download_received_size}"
                )
                self._send_raw_uds_response(
                    client,
                    ecu,
                    source_address,
                    bytes([0x7F, service_id, NRC_INCORRECT_LENGTH_OR_FORMAT]),
                )
                return True

            self._send_response_pending(client, ecu, source_address, service_id)
            time.sleep(self.VERIFY_DELAY_SECONDS)
            output = ecu.receiver.save(ecu.profile["firmware_file"])
            print(f"File : {output}")
            print(f"Downloaded Size : {ecu.receiver.downloaded_size()} bytes")
            passed, expected, actual, exp_size, act_size = (
                ecu.receiver.verify(ecu.profile["original_path"])
            )
            ecu.download_verified = passed
            ecu.install_pending = passed
            ecu.install_started = False
            print(f"Verification: {'PASS' if passed else 'FAIL'}")
            if passed:
                self._send_raw_uds_response(
                    client,
                    ecu,
                    source_address,
                    bytes([positive_response_sid(service_id)]),
                )
            else:
                self._send_raw_uds_response(
                    client,
                    ecu,
                    source_address,
                    bytes([0x7F, service_id, 0x72]),
                )
            return True

        if service_id == SID_ECU_RESET:
            if not self._require_programming_session(client, ecu, source_address, service_id):
                return True
            reset_type = payload[1] if len(payload) > 1 else 0x01
            print(f"UDS ECUReset reset_type=0x{reset_type:02X}")
            self._send_raw_uds_response(
                client,
                ecu,
                source_address,
                bytes([positive_response_sid(service_id), reset_type]),
            )

            if (
                getattr(ecu, "install_pending", False)
                and getattr(ecu, "activation_marked", False)
                and not getattr(ecu, "install_started", False)
            ):
                ecu.install_started = True
                threading.Thread(
                    target=self._perform_install,
                    args=(ecu,),
                    daemon=True,
                ).start()

            ecu.current_session = 0x00
            self._reset_programming_state(ecu)
            return True

        return False

    def _perform_install(self, ecu):

        try:
            FirmwareInstaller.install(
                ecu.ecu_key,
                ecu.profile["firmware_file"],
                ecu.target_version,
            )
        except Exception as exc:
            print(f"Firmware install failed for {ecu.ecu_name}: {exc}")

    def _response_for(self, ecu, message):

        message_type = message.get("type")

        if message_type == "DISCOVERY_REQUEST":

            return {
                "type": "DISCOVERY_RESPONSE",
                "ecu_name": ecu.ecu_name,
                "version": ecu.version_manager.get_current_version(),
                "status": "READY",
            }

        if message_type in ("HEALTH_CHECK", "HEALTH_REQUEST"):

            return {
                "status": "HEALTHY"
            }

        if message_type == "VERSION_REQUEST":

            return {
                "version": ecu.version_manager.get_current_version()
            }

        if message_type == "FIRMWARE_START":

            print()
            print("=" * 50)
            print(f"{ecu.ecu_name} - FIRMWARE DOWNLOAD")
            print("=" * 50)
            print()
            print("Received : FIRMWARE_START")
            print("Creating download session...")

            ecu.receiver.clear()
            ecu.target_version = message.get(
                "target_version",
                ecu.profile["target_version"]
            )

            print("RAM buffer allocated")
            print("ACK Sent")
            print()
            print("Receiving firmware...")
            print()

            return {
                "status": "ACK"
            }

        if message_type == "FIRMWARE_CHUNK":

            sequence = message["sequence"]
            payload = bytes.fromhex(message["payload"])
            frame = bytes([MessageType.FIRMWARE_DATA, sequence]) + payload

            sequence, payload = ecu.receiver.append_chunk(frame)

            chunk_num = ecu.receiver.chunk_count

            print(f"Chunk {chunk_num} received")
            print(f"  Sequence : {sequence}")
            print(f"  Payload  : {payload.hex(' ').upper()}")
            print(f"  Stored   : {ecu.receiver.downloaded_size()} bytes")
            print("  ACK Sent")

            return {
                "status": "ACK"
            }

        return {
            "status": "ACK"
        }

    def _handle_firmware_end(self, client, ecu, source_address):

        print()
        print("-" * 50)
        print("Received : FIRMWARE_END")
        print()
        print("Reconstructing firmware...")

        output = ecu.receiver.save(ecu.profile["firmware_file"])

        print()
        print(f"File : {output}")
        print(f"Downloaded Size : {ecu.receiver.downloaded_size()} bytes")

        print()
        print("Verifying integrity...")

        passed, expected, actual, exp_size, act_size = (
            ecu.receiver.verify(ecu.profile["original_path"])
        )

        print()
        print(f"Original Size   : {exp_size} bytes")
        print(f"Downloaded Size : {act_size} bytes")
        print()
        print(f"Expected SHA256 : {expected[:16]}...")
        print(f"Actual SHA256   : {actual[:16]}...")
        print()

        self._send_ota_response(client, ecu, source_address, {"status": "ACK"})

        print("Final ACK Sent to TCU")

        if passed:

            print()
            print("Starting Firmware Installation...")

            FirmwareInstaller.install(
                ecu.ecu_key,
                ecu.profile["firmware_file"],
                ecu.target_version,
            )

            self._send_ota_response(
                client,
                ecu,
                source_address,
                {"type": "INSTALL_COMPLETE"},
            )

            print("INSTALL_COMPLETE Sent")

        else:

            self._send_ota_response(
                client,
                ecu,
                source_address,
                {
                    "status": "FAILED",
                    "reason": "INTEGRITY_CHECK_FAILED",
                }
            )

            print("Integrity Check FAILED")
            print("Installation Aborted")

        print()
        print("=" * 50)
        print(f"{ecu.ecu_name} - DOWNLOAD COMPLETE")
        print("=" * 50)

    @staticmethod
    def _profile(ecu_name):

        profiles = {
            "Gateway ECU": {
                "download_directory": "ecus/gateway/downloads",
                "firmware_file": "gateway_v2.bin",
                "original_path": "firmware/releases/2.0.0/gateway_v2.bin",
                "target_version": "2.0.0",
            },
            "BCM ECU": {
                "download_directory": "ecus/bcm/downloads",
                "firmware_file": "bcm_v2.bin",
                "original_path": "firmware/releases/2.0.0/bcm_v2.bin",
                "target_version": "2.0.0",
            },
            "Cluster ECU": {
                "download_directory": "ecus/cluster/downloads",
                "firmware_file": "cluster_v2.bin",
                "original_path": "firmware/releases/2.0.0/cluster_v2.bin",
                "target_version": "2.0.0",
            },
        }

        return profiles[ecu_name]
