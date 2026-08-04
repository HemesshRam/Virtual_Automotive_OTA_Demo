import socket
import os
from pathlib import Path

from common.ecu_registry import ECU_REGISTRY
from common.logical_addresses import TESTER_ADDRESS

from .message import OTAApplicationMessage
from .packet import (
    parse_packet,
    parse_diagnostic_payload,
    build_diagnostic_packet,
)
from .protocol import DIAGNOSTIC_MESSAGE
from .vehicle_discovery import vehicle_identification_request
from .routing_activation import routing_activation

GATEWAY_IP = os.getenv("DOIP_GATEWAY_HOST", "127.0.0.1")
GATEWAY_PORT = int(os.getenv("DOIP_GATEWAY_PORT", "13400"))


class DoIPClient:

    CHUNK_SIZE = 6

    def __init__(self):

        self.sock = None
        self.current_ecu = None
        self.current_package = None

    # -------------------------------------------------------
    # Connection
    # -------------------------------------------------------

    def connect(self):

        if self.sock:
            return self.sock

        self.sock = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM
        )

        self.sock.connect(
            (GATEWAY_IP, GATEWAY_PORT)
        )

        print()
        print("=" * 60)
        print("DOIP CONNECTION")
        print("=" * 60)
        print(f"Gateway : {GATEWAY_IP}:{GATEWAY_PORT}")
        print("Connected Successfully")

        return self.sock

    # -------------------------------------------------------
    # Generic DoIP Message
    # -------------------------------------------------------

    def send_message(self, target_address, message):

        payload = OTAApplicationMessage.encode(message)

        packet = build_diagnostic_packet(
            source_address=TESTER_ADDRESS,
            target_address=target_address,
            payload=payload,
        )

        self.sock.sendall(packet)

    def receive_message(self):

        data = self.sock.recv(4096)

        payload_type, payload = parse_packet(data)

        if payload_type != DIAGNOSTIC_MESSAGE:
            return None

        source_address, target_address, diagnostic_payload = (
            parse_diagnostic_payload(payload)
        )

        return OTAApplicationMessage.decode(
            diagnostic_payload
        )

    # -------------------------------------------------------
    # Vehicle Discovery
    # -------------------------------------------------------

    def discover_vehicle(self):

        print()
        print("=" * 60)
        print("DOIP VEHICLE DISCOVERY")
        print("=" * 60)

        self.connect()

        packet = vehicle_identification_request()

        self.sock.sendall(packet)

        response = self.sock.recv(1024)

        print("Vehicle Identification Successful")

        return response

    # -------------------------------------------------------
    # Routing Activation
    # -------------------------------------------------------

    def activate(self):

        packet = routing_activation()

        self.sock.sendall(packet)

        response = self.sock.recv(1024)

        print("Routing Activation Successful")

        return response

    # -------------------------------------------------------
    # OTA Transfer
    # -------------------------------------------------------

    def send_firmware(self, ecu, package):

        ecu_name = ecu.ecu_name

        target_address = ECU_REGISTRY[ecu_name]["logical_address"]

        firmware_path = Path(
            package.get(
                "path",
                package.get("file")
            )
        )

        print()
        print("=" * 60)
        print("OTA FIRMWARE TRANSFER")
        print("=" * 60)
        print(f"Target ECU      : {ecu_name}")
        print(f"Logical Address : {hex(target_address)}")
        print("=" * 60)

        try:

            self.discover_vehicle()

            self.activate()

            # --------------------------
            # Start Download
            # --------------------------

            self.send_message(
                target_address,
                {
                    "type": "FIRMWARE_START",
                    "target_version": package["target_version"],
                }
            )

            response = self.receive_message()

            if response != {"status": "ACK"}:

                print("FIRMWARE_START Failed")

                return False

            # --------------------------
            # Transfer Data
            # --------------------------

            sequence = 0

            with open(firmware_path, "rb") as file:

                while True:

                    chunk = file.read(self.CHUNK_SIZE)

                    if not chunk:
                        break

                    self.send_message(
                        target_address,
                        {
                            "type": "FIRMWARE_CHUNK",
                            "sequence": sequence,
                            "payload": chunk.hex(),
                        }
                    )

                    response = self.receive_message()

                    if response != {"status": "ACK"}:

                        print(
                            f"Chunk {sequence} Failed"
                        )

                        return False

                    sequence = (
                        sequence + 1
                    ) % 256

            # --------------------------
            # Transfer Exit
            # --------------------------

            self.send_message(
                target_address,
                {
                    "type": "FIRMWARE_END",
                }
            )

            response = self.receive_message()

            if response != {"status": "ACK"}:

                print("FIRMWARE_END Failed")

                return False

            response = self.receive_message()

            if response and response.get("status") == "FAILED":

                print(
                    "OTA Update Failed : "
                    f"{response.get('reason', 'UNKNOWN_REASON')}"
                )

                return False

            if response != {

                "type": "INSTALL_COMPLETE"

            }:

                print("INSTALL_COMPLETE Missing")

                return False

            print()

            print("OTA Update Successful")

            return True

        except Exception as e:

            print()

            print(f"[DoIP ERROR] {e}")

            return False

    # -------------------------------------------------------
    # Future UDS APIs
    # -------------------------------------------------------

    def _current_target_address(self):

        ecu_name = self.current_ecu.ecu_name

        return ECU_REGISTRY[ecu_name]["logical_address"]

    def _require_ack(self, operation):

        response = self.receive_message()

        if response != {"status": "ACK"}:
            raise RuntimeError(f"{operation} failed: {response}")

        return True

    def diagnostic_session_control(self):

        self.discover_vehicle()

        self.activate()

        return True

    def tester_present(self):

        return True

    def request_download(self, size):

        target_address = self._current_target_address()

        self.send_message(
            target_address,
            {
                "type": "FIRMWARE_START",
                "target_version": self.current_package["target_version"],
                "size": size,
            }
        )

        return self._require_ack("RequestDownload")

    def transfer_data(self, seq, data):

        target_address = self._current_target_address()

        self.send_message(
            target_address,
            {
                "type": "FIRMWARE_CHUNK",
                "sequence": seq,
                "payload": data.hex(),
            }
        )

        return self._require_ack("TransferData")

    def request_transfer_exit(self):

        target_address = self._current_target_address()

        self.send_message(
            target_address,
            {
                "type": "FIRMWARE_END",
            }
        )

        return self._require_ack("RequestTransferExit")

    def ecu_reset(self):

        response = self.receive_message()

        if response and response.get("status") == "FAILED":
            raise RuntimeError(
                "ECUReset failed: "
                f"{response.get('reason', 'UNKNOWN_REASON')}"
            )

        if response != {"type": "INSTALL_COMPLETE"}:
            raise RuntimeError(f"INSTALL_COMPLETE missing: {response}")

        return True

    def send_start(self, ecu):
        pass

    def send_chunk(self, ecu, seq, data):
        pass

    def send_end(self, ecu):
        pass

    def health_check(self, ecu):
        pass

    def get_version(self, ecu):
        pass

    # -------------------------------------------------------
    # Shutdown
    # -------------------------------------------------------

    def shutdown(self):

        if self.sock:

            try:

                self.sock.close()

            except Exception:

                pass

            self.sock = None
