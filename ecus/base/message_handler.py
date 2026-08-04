from common.can_protocol import CANProtocol
from common.message_types import MessageType


class MessageHandler:
    """
    Handles incoming CAN protocol messages for an ECU.
    """

    def __init__(self, config_manager):
        self.config = config_manager

    def handle_message(self, message):
        """
        Process a received CAN message.

        Returns:
            can.Message | None
        """

        decoded = CANProtocol.parse_message(message)

        message_type = decoded["message_type"]

        if message_type == MessageType.DISCOVERY_REQUEST:
            return self._handle_discovery_request()

        if message_type == MessageType.HEALTH_REQUEST:
            return self._handle_health_request()

        if message_type == MessageType.VERSION_REQUEST:
            return self._handle_version_request()

        return None

    def _handle_discovery_request(self):
        """
        Create a Discovery Response message.
        """

        version = self.config.current_version.split(".")

        major = int(version[0])
        minor = int(version[1])

        response = CANProtocol.create_message(
            arbitration_id=self.config.ecu_id,
            message_type=MessageType.DISCOVERY_RESPONSE,
            version_major=major,
            version_minor=minor,
        )

        return response

    def _handle_health_request(self):

        return CANProtocol.build_health_response(
            self.config.ecu_id,
        )

    def _handle_version_request(self):

        version = self.config.current_version.split(".")
        major = int(version[0])
        minor = int(version[1])

        return CANProtocol.build_version_response(
            self.config.ecu_id,
            major=major,
            minor=minor,
        )
