from ecus.base.can_interface import CANInterface

from common.can_protocol import CANProtocol
from common.message_types import MessageType

from ecus.base.installer import FirmwareInstaller
from ecus.base.version_manager import VersionManager
from ecus.base.ecu_state import ECUState
from ecus.base.uds_can_programmer import UDSCanProgrammer
from ecus.base.heartbeat import ECUHeartbeatPublisher

from common.constants import (
    GATEWAY_ID,
    BROADCAST_ID,
    ECU_CAN_INTERFACES,
)
import os

from ecus.gateway.firmware_receiver import FirmwareReceiver


ECU_NAME = "Gateway ECU"

FIRMWARE_FILE = "gateway_v2.bin"

ORIGINAL_PATH = "firmware/releases/2.0.0/gateway_v2.bin"


class GatewayReceiver:

    def __init__(self):

        self.can = CANInterface(
            os.getenv("OTA_ECU_GATEWAY_CAN_CHANNEL", ECU_CAN_INTERFACES[GATEWAY_ID])
        )

        self.firmware_receiver = FirmwareReceiver(
            "ecus/gateway/downloads"
        )
        self.version_manager = VersionManager("gateway")
        self.uds_programmer = UDSCanProgrammer(
            self.can,
            GATEWAY_ID,
            "gateway",
            self.version_manager,
            self.firmware_receiver,
            FIRMWARE_FILE,
            ORIGINAL_PATH,
            "2.0.0",
        )
        self.heartbeat = ECUHeartbeatPublisher(
            self.can,
            GATEWAY_ID,
            "gateway",
            ECU_NAME,
        )

    def start(self):

        print(f"\n{ECU_NAME} Ready...\n")
        self.heartbeat.start()

        while True:

            message = self.can.receive(timeout=1)

            if message is None:
                continue

            if message.arbitration_id not in (GATEWAY_ID, BROADCAST_ID):
                continue

            if self.uds_programmer.feed(message):
                continue

            try:
                message_type = MessageType(message.data[0])
            except ValueError:
                continue

            if message_type == MessageType.HEARTBEAT:
                continue

            # ======================================================
            # DISCOVERY REQUEST
            # ======================================================

            if message_type == MessageType.DISCOVERY_REQUEST:

                print("--------------------------------")
                print(ECU_NAME)
                print("Received : DISCOVERY_REQUEST")

                version = self.version_manager.get_current_version()

                major, minor, patch = map(int, version.split("."))

                response = CANProtocol.create_message(
                    arbitration_id=GATEWAY_ID,
                    message_type=MessageType.DISCOVERY_RESPONSE,
                    payload=bytes([major, minor]),
                )

                self.can.send(response)

                print("Discovery Response Sent")
                print("--------------------------------")

                continue

            # ======================================================
            # HEALTH REQUEST
            # ======================================================

            if message_type == MessageType.HEALTH_REQUEST:

                print()
                print("Health Check Requested")

                response = CANProtocol.build_health_response(
                    GATEWAY_ID
                )

                self.can.send(response)

                print("Health Response Sent")

                continue

            # ======================================================
            # VERSION REQUEST
            # ======================================================

            if message_type == MessageType.VERSION_REQUEST:

                print()
                print("Version Request Received")

                version = VersionManager("gateway").get_current_version()

                major, minor, _ = version.split(".")

                response = CANProtocol.build_version_response(
                    GATEWAY_ID,
                    int(major),
                    int(minor),
                )

                self.can.send(response)

                print(f"Current Version : {version}")

                continue

            # ======================================================
            # FIRMWARE START
            # ======================================================

            if message_type == MessageType.FIRMWARE_START:

                print()
                print("=" * 50)
                print(f"{ECU_NAME} — FIRMWARE DOWNLOAD")
                print("=" * 50)

                print()
                print("Received : FIRMWARE_START")
                print("Creating download session...")

                self.firmware_receiver.clear()
                if len(message.data) >= 6:
                    self.firmware_receiver.set_expected_size(
                        int.from_bytes(message.data[2:6], "big")
                    )

                ack = CANProtocol.create_message(
                    arbitration_id=GATEWAY_ID,
                    message_type=MessageType.ACK,
                )

                self.can.send(ack)

                print("RAM buffer allocated")
                print("ACK Sent")
                print()
                print("Receiving firmware...")
                print()

                continue

            # ======================================================
            # FIRMWARE DATA
            # ======================================================

            if message_type == MessageType.FIRMWARE_DATA:

                sequence, payload = self.firmware_receiver.append_chunk(
                    message.data
                )

                chunk_num = self.firmware_receiver.chunk_count

                print(f"Chunk {chunk_num} received")
                print(f"  Sequence : {sequence}")
                print(f"  Payload  : {payload.hex(' ').upper()}")
                print(f"  Stored   : {self.firmware_receiver.downloaded_size()} bytes")

                ack = CANProtocol.create_message(
                    arbitration_id=GATEWAY_ID,
                    message_type=MessageType.ACK,
                )

                self.can.send(ack)

                print("  ACK Sent")

                continue

            # ======================================================
            # FIRMWARE END
            # ======================================================

            if message_type == MessageType.FIRMWARE_END:

                print()
                print("-" * 50)
                print("Received : FIRMWARE_END")
                print()
                print("Reconstructing firmware...")

                output = self.firmware_receiver.save(FIRMWARE_FILE)

                print()
                print(f"File : {output}")
                print(f"Downloaded Size : {self.firmware_receiver.downloaded_size()} bytes")

                #
                # SHA-256 Verification
                #

                print()
                print("Verifying integrity...")

                passed, expected, actual, exp_size, act_size = (
                    self.firmware_receiver.verify(ORIGINAL_PATH)
                )

                print()
                print(f"Original Size   : {exp_size} bytes")
                print(f"Downloaded Size : {act_size} bytes")
                print()
                print(f"Expected SHA256 : {expected[:16]}...")
                print(f"Actual SHA256   : {actual[:16]}...")
                print()

                #
                # Send ACK immediately after verification
                #

                ack = CANProtocol.create_message(
                    arbitration_id=GATEWAY_ID,
                    message_type=MessageType.ACK,
                )

                self.can.send(ack)

                print("✓ Final ACK Sent to TCU")

                #
                # Installation starts after ACK
                #

                if passed:

                    print()
                    print("Starting Firmware Installation...")

                    FirmwareInstaller.install(
                        "gateway",
                        "gateway_v2.bin",
                    )

                    #
                    # Installation completed
                    #

                    install_complete = CANProtocol.build_install_complete(
                        GATEWAY_ID
                    )

                    self.can.send(install_complete)

                    print("INSTALL_COMPLETE Sent")

                else:

                    print("✗ Integrity Check FAILED")
                    print("Installation Aborted")

                print()
                print("=" * 50)
                print(f"{ECU_NAME} — DOWNLOAD COMPLETE")
                print("=" * 50)

                continue
