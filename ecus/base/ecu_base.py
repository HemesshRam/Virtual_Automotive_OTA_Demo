from pathlib import Path

from ecus.base.config_manager import ConfigManager
from ecus.base.can_interface import CANInterface
from ecus.base.message_handler import MessageHandler
from ecus.base.state_machine import StateMachine, ECUState


class ECUBase:
    """
    Base ECU implementation shared by all ECUs.
    """

    def __init__(self, ecu_directory: Path):
        # Load ECU configuration
        self.config = ConfigManager(str(ecu_directory))

        # Initialize CAN interface
        self.can_interface = CANInterface()

        # Initialize message handler
        self.message_handler = MessageHandler(self.config)

        # Initialize ECU state
        self.state_machine = StateMachine()
        self.state_machine.set_state(ECUState.READY)

        print(f"[{self.config.ecu_name}] Started")
        print(f"ECU ID          : {hex(self.config.ecu_id)}")
        print(f"Version         : {self.config.current_version}")
        print(f"Transport       : {self.config.transport}")
        print("-------------------------------------------")

    def run(self):
        """
        Main receive loop.
        """

        print(f"[{self.config.ecu_name}] Waiting for CAN messages...")

        while True:
            message = self.can_interface.receive(timeout=1.0)

            if message is None:
                continue

            response = self.message_handler.handle_message(message)

            if response is not None:
                self.can_interface.send(response)

                self.state_machine.set_state(ECUState.DISCOVERED)

                print(
                    f"[{self.config.ecu_name}] "
                    f"Discovery Response sent."
                )