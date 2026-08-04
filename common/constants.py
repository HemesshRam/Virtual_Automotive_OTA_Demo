# CAN Interfaces
CAN_INTERFACE = "vcan0"
VCAN_GATE = "vcan_gate"
VCAN_BCM = "vcan_bcm"
VCAN_CLUS = "vcan_clus"

# Node IDs
TCU_ID = 0x100

GATEWAY_ID = 0x201
BCM_ID = 0x202
CLUSTER_ID = 0x203

BROADCAST_ID = 0x7FF

CAN_INTERFACES = [
    VCAN_GATE,
    VCAN_BCM,
    VCAN_CLUS,
]

ECU_CAN_INTERFACES = {
    GATEWAY_ID: VCAN_GATE,
    BCM_ID: VCAN_BCM,
    CLUSTER_ID: VCAN_CLUS,
}

# ECU Names
GATEWAY = "gateway"
BCM = "bcm"
CLUSTER = "cluster"

# -----------------------------
# CAN FD
# -----------------------------

CANFD_MAX_DATA = 64

ACK_TIMEOUT = 2.0
INSTALL_TIMEOUT = 30.0

CHUNK_SIZE = 60
