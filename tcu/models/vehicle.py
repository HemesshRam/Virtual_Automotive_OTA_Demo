from typing import Dict

from tcu.models.ecu import ECU


class Vehicle:
    """
    Vehicle Digital Twin.

    Holds runtime information about every ECU
    participating in the OTA campaign.
    """

    def __init__(self):

        self.vehicle_name = "Virtual Vehicle"

        self.ecus: Dict[int, ECU] = {}

    def add_ecu(self, ecu: ECU):

        self.ecus[ecu.ecu_id] = ecu

    def get_ecu(self, ecu_id: int):

        return self.ecus.get(ecu_id)

    def get_all_ecus(self):

        return list(self.ecus.values())

    def total_ecus(self):

        return len(self.ecus)

    def print_inventory(self):

        print()

        print("=" * 45)

        print("VEHICLE INVENTORY")

        print("=" * 45)

        print()

        print(f"Vehicle : {self.vehicle_name}")

        print(f"Total ECUs : {self.total_ecus()}")

        print()

        for ecu in self.get_all_ecus():

            print("-" * 45)

            print(f"ECU ID           : 0x{ecu.ecu_id:X}")

            print(f"ECU Name         : {ecu.ecu_name}")

            print(f"Current Version  : {ecu.current_version}")

            print(f"Transport        : {ecu.transport}")

            print(
                f"Dependencies     : "
                f"{', '.join(ecu.dependencies) if ecu.dependencies else 'None'}"
            )

            print(f"State            : {ecu.state}")

            print(f"Health           : {ecu.health}")

            print("-" * 45)

            print()