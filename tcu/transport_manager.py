"""
Transport Manager

Responsible for selecting the communication transport.

Supported transports
--------------------
1. VCAN (SocketCAN)
2. DoIP (Automotive Ethernet) - uses python-doipclient library via LibraryDoIPClient

The transport implementation itself is responsible for
handling its own protocol (CAN or DoIP).
"""

from common.utils import normalize_transport


class TransportManager:

    def __init__(self, mode):

        self.mode = normalize_transport(mode)
        self.transport_name = self.mode

        if self.mode in ("CAN", "VCAN"):

            from transport.can.can_sender import CANSender

            self.transport = CANSender()

        elif self.mode == "DOIP":

            from transport.doip.library_client import LibraryDoIPClient

            self.transport = LibraryDoIPClient()

        else:

            raise RuntimeError(
                f"Unsupported transport: {mode}"
            )

    # ----------------------------------------------------
    # Generic Message API
    # ----------------------------------------------------

    def send(self, ecu, message):

        if self.mode in ("CAN", "VCAN"):

            return self.transport.send_message(
                ecu,
                message,
            )

        raise NotImplementedError(
            "Generic send() is not used for DoIP."
        )

    def receive(self, ecu=None, timeout=2.0):

        if self.mode in ("CAN", "VCAN"):

            return self.transport.receive_message(
                ecu,
                timeout=timeout,
            )

        return self.transport.receive_message()

    # ----------------------------------------------------
    # Firmware Transfer
    # ----------------------------------------------------

    def send_firmware(self, ecu, firmware):

        print()

        print("=" * 60)
        print("TRANSPORT MANAGER")
        print("=" * 60)
        print(f"Transport : {self.transport_name}")
        
        # Show library implementation for DoIP
        if self.mode == "DOIP":
            print(f"Implementation : python-doipclient library")
        
        print(f"Target ECU: {ecu.ecu_name}")
        print("=" * 60)

        from transport.uds.client import UDSClient

        firmware_path = firmware["path"]

        self.transport.current_ecu = ecu
        self.transport.current_package = firmware

        with open(firmware_path, "rb") as file:
            firmware_data = file.read()

        try:
            if hasattr(self.transport, "connect"):
                self.transport.connect()

            uds = UDSClient(self.transport)

            success = uds.flash_firmware(firmware_data)
            return bool(success)

        except Exception as e:
            print(f"[TransportManager ERROR] {e}")
            return False

    # ----------------------------------------------------
    # Shutdown
    # ----------------------------------------------------

    def shutdown(self):

        if hasattr(self.transport, "shutdown"):

            self.transport.shutdown()
