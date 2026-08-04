import struct

DOIP_VERSION = 0x02
DOIP_INVERSE_VERSION = 0xFD
DOIP_HEADER_SIZE = 8


def build_packet(payload_type, payload):

    header = struct.pack(
        "!BBHI",
        DOIP_VERSION,
        DOIP_INVERSE_VERSION,
        payload_type,
        len(payload)
    )

    return header + payload


def build_diagnostic_packet(
    source_address,
    target_address,
    payload
):
    """
    ISO13400 Diagnostic Message

    -----------------------------------
    Source Logical Address (2 bytes)
    Target Logical Address (2 bytes)
    Diagnostic Payload
    -----------------------------------
    """

    diagnostic_payload = struct.pack(
        "!HH",
        source_address,
        target_address
    ) + payload

    return build_packet(
        0x8001,
        diagnostic_payload
    )


def parse_packet(data):

    if len(data) < DOIP_HEADER_SIZE:
        raise ValueError("Incomplete DoIP header")

    version, inverse, payload_type, length = struct.unpack(
        "!BBHI",
        data[:DOIP_HEADER_SIZE]
    )

    if version != DOIP_VERSION or inverse != DOIP_INVERSE_VERSION:
        raise ValueError("Invalid DoIP protocol version")

    packet_length = DOIP_HEADER_SIZE + length
    if len(data) < packet_length:
        raise ValueError("Incomplete DoIP payload")

    payload = data[DOIP_HEADER_SIZE:packet_length]

    return payload_type, payload


def extract_packets(buffer):
    """
    Extract complete DoIP packets from a TCP byte stream.

    TCP may split one DoIP packet across multiple recv() calls or combine
    several packets in one recv(). This keeps packet framing explicit.
    """

    packets = []

    while len(buffer) >= DOIP_HEADER_SIZE:
        version, inverse, payload_type, length = struct.unpack(
            "!BBHI",
            buffer[:DOIP_HEADER_SIZE]
        )

        if version != DOIP_VERSION or inverse != DOIP_INVERSE_VERSION:
            raise ValueError("Invalid DoIP protocol version")

        packet_length = DOIP_HEADER_SIZE + length

        if len(buffer) < packet_length:
            break

        payload = bytes(buffer[DOIP_HEADER_SIZE:packet_length])
        packets.append((payload_type, payload))
        del buffer[:packet_length]

    return packets


def parse_diagnostic_payload(payload):

    source_address, target_address = struct.unpack(
        "!HH",
        payload[:4]
    )

    diagnostic_data = payload[4:]

    return (
        source_address,
        target_address,
        diagnostic_data
    )
