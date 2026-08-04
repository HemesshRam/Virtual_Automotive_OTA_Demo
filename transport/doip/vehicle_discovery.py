from .packet import build_packet
from .protocol import VEHICLE_IDENT_REQUEST


def vehicle_identification_request():

    return build_packet(
        VEHICLE_IDENT_REQUEST,
        b""
    )
