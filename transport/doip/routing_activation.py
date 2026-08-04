from .packet import build_packet
from .protocol import ROUTING_ACTIVATION_REQUEST


def routing_activation():

    tester_address = b"\x0E\x80"

    activation_type = b"\x00"

    reserved = b"\x00\x00\x00\x00"

    payload = tester_address + activation_type + reserved

    return build_packet(
        ROUTING_ACTIVATION_REQUEST,
        payload
    )
