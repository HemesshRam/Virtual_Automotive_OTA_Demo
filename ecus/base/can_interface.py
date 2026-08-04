import can

from common.constants import CAN_INTERFACE


class CANInterface:
    """
    SocketCAN interface supporting CAN FD.
    """

    def __init__(self, channel: str = CAN_INTERFACE):

        self.channel = channel

        self.bus = can.interface.Bus(
            channel=self.channel,
            interface="socketcan",
            fd=True,
        )

    def send(self, message: can.Message):

        self.bus.send(message)

    def receive(self, timeout: float = 1.0):

        return self.bus.recv(timeout)

    def shutdown(self):

        if self.bus is not None:
            self.bus.shutdown()
