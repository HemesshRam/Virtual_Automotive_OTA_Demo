class RoutingActivation:

    def activate(self, source_address):

        print(f"Routing activated for {hex(source_address)}")

        return {

            "status": 0x10
        }
