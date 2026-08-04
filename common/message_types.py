from enum import IntEnum


class MessageType(IntEnum):

    # Discovery
    DISCOVERY_REQUEST = 0x01
    DISCOVERY_RESPONSE = 0x02

    # Firmware Transfer
    FIRMWARE_START = 0x10
    FIRMWARE_DATA = 0x11
    FIRMWARE_END = 0x12

    # Generic ACK
    ACK = 0x20

    # OTA Orchestration
    INSTALL_COMPLETE = 0x30

    HEALTH_REQUEST = 0x31
    HEALTH_RESPONSE = 0x32

    VERSION_REQUEST = 0x33
    VERSION_RESPONSE = 0x34

    # Network management / availability
    HEARTBEAT = 0x40
