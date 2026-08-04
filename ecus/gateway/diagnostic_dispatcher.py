from transport.doip.constants import *

class DiagnosticDispatcher:

    def __init__(self,
                 vehicle_identification,
                 routing_activation,
                 uds_router):

        self.vehicle_identification = vehicle_identification
        self.routing_activation = routing_activation
        self.uds_router = uds_router

    def dispatch(self,
                 payload_type,
                 message):

        if payload_type == VEHICLE_IDENTIFICATION_REQUEST:

            return self.vehicle_identification.create_response()

        elif payload_type == ROUTING_ACTIVATION_REQUEST:

            return self.routing_activation.activate(
                message["source_address"]
            )

        elif payload_type == DIAGNOSTIC_MESSAGE:

            return self.uds_router.route(
                message["target_address"],
                message["uds"]
            )

        else:

            raise Exception("Unsupported DoIP Payload")
