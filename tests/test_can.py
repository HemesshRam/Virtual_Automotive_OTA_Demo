import can

from ecus.base.can_interface import CANInterface

can_bus = CANInterface()

msg = can.Message(
    arbitration_id=0x123,
    data=[1, 2, 3, 4],
    is_extended_id=False,
)

can_bus.send(msg)

print("Message sent successfully.")

can_bus.shutdown()