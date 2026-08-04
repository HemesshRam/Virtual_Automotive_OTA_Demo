import can

from common.message_types import MessageType


class CANProtocol:
    """
    Utility class for encoding and decoding OTA CAN messages.

    CAN Frame Format
    ----------------
    Arbitration ID : Sender ECU ID

    Payload (CAN FD, up to 64 bytes)

    Byte 0 : Message Type
    Byte 1-7 : Payload
    """

    @staticmethod
    def create_message(
        arbitration_id: int,
        message_type: MessageType,
        payload: bytes = b"",
    ) -> can.Message:
        """
        Create a CAN message.
        """

        if len(payload) > 63:
            raise ValueError("CAN FD payload exceeds 63 bytes")

        data = bytearray(1 + len(payload))

        # Byte 0 = Message Type
        data[0] = int(message_type)

        for i, value in enumerate(payload):
            data[i + 1] = value

        return can.Message(
            arbitration_id=arbitration_id,
            data=data,
            is_extended_id=False,
            is_fd=True,
            bitrate_switch=True,
        )

    @staticmethod
    def parse_message(message: can.Message) -> dict:
        """
        Decode a received CAN message.

        Returns
        -------
        sender_id
        message_type
        payload
        version_major
        version_minor
        """

        if len(message.data) == 0:
            raise ValueError("Invalid CAN Frame")

        payload = bytes(message.data[1:])

        return {
            "sender_id": message.arbitration_id,
            "message_type": MessageType(message.data[0]),
            "payload": payload,
            "version_major": payload[0] if len(payload) > 0 else 0,
            "version_minor": payload[1] if len(payload) > 1 else 0,
        }

    @staticmethod
    def build_ack(arbitration_id: int):
        """
        Build ACK message.
        """
        return CANProtocol.create_message(
            arbitration_id,
            MessageType.ACK,
        )

    @staticmethod
    def build_install_complete(arbitration_id: int):
        """
        ECU -> TCU
        Installation completed successfully.
        """
        return CANProtocol.create_message(
            arbitration_id,
            MessageType.INSTALL_COMPLETE,
        )

    @staticmethod
    def build_health_request(arbitration_id: int):
        """
        TCU -> ECU
        Request ECU health.
        """
        return CANProtocol.create_message(
            arbitration_id,
            MessageType.HEALTH_REQUEST,
        )

    @staticmethod
    def build_health_response(arbitration_id: int):
        """
        ECU -> TCU
        Respond ECU is healthy.
        Payload:
            Byte1 = 1 (Healthy)
        """
        return CANProtocol.create_message(
            arbitration_id,
            MessageType.HEALTH_RESPONSE,
            payload=bytes([1]),
        )

    @staticmethod
    def build_version_request(arbitration_id: int):
        """
        TCU -> ECU
        Request running software version.
        """
        return CANProtocol.create_message(
            arbitration_id,
            MessageType.VERSION_REQUEST,
        )

    @staticmethod
    def build_version_response(
        arbitration_id: int,
        major: int,
        minor: int,
    ):
        """
        ECU -> TCU

        Example:
            2.0  -> payload = [2,0]
            2.1  -> payload = [2,1]
        """
        return CANProtocol.create_message(
            arbitration_id,
            MessageType.VERSION_RESPONSE,
            payload=bytes([major, minor]),
        )
