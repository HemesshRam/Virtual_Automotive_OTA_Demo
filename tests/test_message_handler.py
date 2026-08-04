from ecus.base.config_manager import ConfigManager
from ecus.base.message_handler import MessageHandler

from common.can_protocol import CANProtocol
from common.message_types import MessageType
from common.constants import BROADCAST_ID


def main():
    config = ConfigManager("ecus/gateway")

    handler = MessageHandler(config)

    request = CANProtocol.create_message(
        arbitration_id=BROADCAST_ID,
        message_type=MessageType.DISCOVERY_REQUEST,
    )

    response = handler.handle_message(request)

    decoded = CANProtocol.parse_message(response)

    print("Decoded Discovery Response")
    print("--------------------------")
    print(f"Sender ECU ID : {decoded['sender_id']}")
    print(f"Message Type  : {decoded['message_type'].name}")
    print(f"Version       : {decoded['version_major']}.{decoded['version_minor']}")


if __name__ == "__main__":
    main()