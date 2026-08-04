from common.logical_addresses import *

class UDSRouter:

    def __init__(self):

        self.ecus = {}

    def register(self, logical_address, ecu):

        self.ecus[logical_address] = ecu

    def route(self, target_address, uds_payload):

        if target_address not in self.ecus:

            raise Exception(
                f"Unknown ECU {hex(target_address)}"
            )

        return self.ecus[target_address].handle_uds(
            uds_payload
        )
